"""Función 3 (registrar la llamada) sin base de datos ni API de Claude."""

from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from cobranza.application.interfaces.call_summarizer import SummarizationError
from cobranza.application.use_cases.register_call import EndCall, RecordRecordingConsent, StartCall
from cobranza.domain.call import CallDirection, CallOutcome, CallRecord
from cobranza.domain.debtor import AccountSummary, DebtorSummary
from cobranza.infrastructure.services.claude_call_summarizer import ClaudeCallSummarizer
from cobranza.infrastructure.services.fallback_call_summarizer import FallbackCallSummarizer
from cobranza.infrastructure.services.phonenumbers_phone_service import PhonenumbersPhoneService

NOW = datetime(2026, 11, 1, 15, 0, tzinfo=timezone.utc)


class FixedClock:
    def now(self):
        return NOW


class FakeCalls:
    def __init__(self):
        self.calls: dict[str, CallRecord] = {}
        self.phones: dict[str, str] = {}
        self.closed: dict[str, tuple] = {}

    def create(self, direction, caller_phone, started_at, debtor_id, account_id):
        call_id = f"call-{len(self.calls) + 1}"
        self.calls[call_id] = CallRecord(call_id, direction, debtor_id, account_id, None, None)
        self.phones[call_id] = caller_phone
        return call_id

    def get(self, call_id):
        return self.calls.get(call_id)

    def set_recording_consent(self, call_id, accepted):
        self.calls[call_id] = replace(self.calls[call_id], recording_consent=accepted)

    def close(self, call_id, outcome, summary, ended_at):
        self.calls[call_id] = replace(self.calls[call_id], ended_at=ended_at)
        self.closed[call_id] = (outcome, summary)


def _debtor():
    account = AccountSummary(
        id="acc-uuid", external_id="ACC-1", creditor_name="Acme", account_number_masked="****0001",
        current_balance_cents=10000, status="NSF", payment_method="ACH", nsf_amount_cents=9000,
        nsf_fee_cents=1000, nsf_date=None, nsf_return_code="R01", is_disputed=False,
    )
    return DebtorSummary(
        id="deb-uuid", external_id="DEB-1", first_name="Jane", last_name="Doe",
        phone_primary="+12125550100", us_state="NY", timezone="America/New_York",
        timezone_inferred=False, do_not_call=False, accounts=(account,),
    )


class FakeDebtors:
    def get_by_account(self, account_external_id):
        return _debtor() if account_external_id == "ACC-1" else None


class FakeSummarizer:
    def __init__(self, fail=False):
        self.fail = fail
        self.transcripts = []

    def summarize(self, transcript):
        self.transcripts.append(transcript)
        if self.fail:
            raise SummarizationError("api down")
        return "Debtor agreed to pay in full."


def _start(calls):
    return StartCall(calls, FakeDebtors(), PhonenumbersPhoneService(), FixedClock())


# --- StartCall ----------------------------------------------------------------

def test_inbound_call_starts_without_debtor_and_normalizes_phone():
    calls = FakeCalls()
    call_id = _start(calls).execute(CallDirection.INBOUND, "(212) 555-0100")
    assert calls.calls[call_id].debtor_id is None
    assert calls.phones[call_id] == "+12125550100"


def test_outbound_call_is_linked_to_the_job_account():
    calls = FakeCalls()
    call_id = _start(calls).execute(CallDirection.OUTBOUND, "+12125550100", "ACC-1")
    assert (calls.calls[call_id].debtor_id, calls.calls[call_id].account_id) == ("deb-uuid", "acc-uuid")


def test_outbound_call_needs_a_known_account():
    with pytest.raises(ValueError):
        _start(FakeCalls()).execute(CallDirection.OUTBOUND, "+12125550100")
    with pytest.raises(ValueError):
        _start(FakeCalls()).execute(CallDirection.OUTBOUND, "+12125550100", "ACC-MISSING")


# --- consentimiento de grabación ----------------------------------------------

def test_recording_consent_is_stored():
    calls = FakeCalls()
    call_id = _start(calls).execute(CallDirection.INBOUND, "+12125550100")
    assert RecordRecordingConsent(calls).execute(call_id, True) is True
    assert calls.calls[call_id].recording_consent is True


def test_refused_recording_only_allows_recording_refused_outcome():
    calls = FakeCalls()
    call_id = _start(calls).execute(CallDirection.INBOUND, "+12125550100")
    assert RecordRecordingConsent(calls).execute(call_id, False) is False
    end = EndCall(calls, FakeSummarizer(), FixedClock())
    with pytest.raises(ValueError):
        end.execute(call_id, CallOutcome.ARRANGEMENT_MADE)
    end.execute(call_id, CallOutcome.RECORDING_REFUSED)
    assert calls.closed[call_id][0] is CallOutcome.RECORDING_REFUSED


# --- EndCall ------------------------------------------------------------------

def test_end_call_saves_outcome_and_ai_summary():
    calls, summarizer = FakeCalls(), FakeSummarizer()
    call_id = _start(calls).execute(CallDirection.INBOUND, "+12125550100")
    summary = EndCall(calls, summarizer, FixedClock()).execute(
        call_id, CallOutcome.PAYMENT_TAKEN, "Agent: ...\nDebtor: I'll pay it all.")
    assert summary == "Debtor agreed to pay in full."
    assert calls.closed[call_id] == (CallOutcome.PAYMENT_TAKEN, summary)
    assert calls.calls[call_id].ended_at == NOW


def test_summary_failure_still_closes_the_call():
    calls = FakeCalls()
    call_id = _start(calls).execute(CallDirection.INBOUND, "+12125550100")
    EndCall(calls, FakeSummarizer(fail=True), FixedClock()).execute(
        call_id, CallOutcome.CALLBACK_REQUESTED, "some transcript")
    assert calls.closed[call_id] == (CallOutcome.CALLBACK_REQUESTED, None)


def test_no_transcript_means_no_summarizer_call():
    calls, summarizer = FakeCalls(), FakeSummarizer()
    call_id = _start(calls).execute(CallDirection.INBOUND, "+12125550100")
    EndCall(calls, summarizer, FixedClock()).execute(call_id, CallOutcome.NO_ANSWER, "   ")
    assert summarizer.transcripts == []


def test_call_cannot_be_closed_twice_or_get_consent_after_closing():
    calls = FakeCalls()
    call_id = _start(calls).execute(CallDirection.INBOUND, "+12125550100")
    end = EndCall(calls, FakeSummarizer(), FixedClock())
    end.execute(call_id, CallOutcome.WRONG_PARTY)
    with pytest.raises(ValueError):
        end.execute(call_id, CallOutcome.WRONG_PARTY)
    with pytest.raises(ValueError):
        RecordRecordingConsent(calls).execute(call_id, True)


# --- adaptador de Claude con cliente falso (sin red) --------------------------

class FakeAnthropic:
    def __init__(self, response):
        self.requests = []
        self.messages = SimpleNamespace(create=self._create)
        self._response = response

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        return self._response


def _response(stop_reason="end_turn", texts=("Summary.",)):
    blocks = [SimpleNamespace(type="thinking", thinking="")] + [
        SimpleNamespace(type="text", text=t) for t in texts
    ]
    return SimpleNamespace(stop_reason=stop_reason, content=blocks)


def test_claude_summarizer_request_and_text():
    client = FakeAnthropic(_response(texts=("Debtor verified. ", "Paid in full.")))
    assert ClaudeCallSummarizer(client).summarize("transcript") == "Debtor verified. Paid in full."
    request = client.requests[0]
    assert request["model"] == "claude-haiku-5-5"
    assert request["output_config"] == {"effort": "low"}
    assert "fallbacks" not in request  # Haiku no tiene respaldo del servidor; usamos el propio
    assert "Social Security" in request["system"]


def test_claude_summarizer_refusal_or_empty_raises():
    with pytest.raises(SummarizationError):
        ClaudeCallSummarizer(FakeAnthropic(_response(stop_reason="refusal"))).summarize("t")
    with pytest.raises(SummarizationError):
        ClaudeCallSummarizer(FakeAnthropic(_response(texts=()))).summarize("t")


# --- respaldo propio ----------------------------------------------------------

class NamedSummarizer:
    def __init__(self, name, fail=False):
        self.name, self.fail, self.calls = name, fail, 0

    def summarize(self, transcript):
        self.calls += 1
        if self.fail:
            raise SummarizationError(f"{self.name} failed")
        return f"by {self.name}"


def test_fallback_uses_primary_when_it_works():
    primary, backup = NamedSummarizer("haiku"), NamedSummarizer("sonnet")
    assert FallbackCallSummarizer(primary, backup).summarize("t") == "by haiku"
    assert backup.calls == 0


def test_fallback_uses_backup_when_primary_refuses_or_fails():
    primary, backup = NamedSummarizer("haiku", fail=True), NamedSummarizer("sonnet")
    assert FallbackCallSummarizer(primary, backup).summarize("t") == "by sonnet"


def test_both_failing_still_closes_the_call_without_summary():
    calls = FakeCalls()
    call_id = _start(calls).execute(CallDirection.INBOUND, "+12125550100")
    both_fail = FallbackCallSummarizer(NamedSummarizer("a", fail=True), NamedSummarizer("b", fail=True))
    EndCall(calls, both_fail, FixedClock()).execute(call_id, CallOutcome.NO_ANSWER, "transcript")
    assert calls.closed[call_id] == (CallOutcome.NO_ANSWER, None)


def test_real_claude_pair_falls_back_from_haiku_to_sonnet():
    haiku = ClaudeCallSummarizer(FakeAnthropic(_response(stop_reason="refusal")), "claude-haiku-5-5")
    sonnet_client = FakeAnthropic(_response(texts=("Summary by Sonnet.",)))
    sonnet = ClaudeCallSummarizer(sonnet_client, "claude-sonnet-5-5")
    assert FallbackCallSummarizer(haiku, sonnet).summarize("t") == "Summary by Sonnet."
    assert sonnet_client.requests[0]["model"] == "claude-sonnet-5-5"


# --- N3: la grabación empieza con el "sí" del deudor ----------------------------

class FakeRecorder:
    def __init__(self):
        self.started = []

    def start(self, call_id):
        self.started.append(call_id)


@pytest.mark.parametrize("accepted, started", [(True, 1), (False, 0)])
def test_recording_starts_only_after_consent(accepted, started):
    calls, recorder = FakeCalls(), FakeRecorder()
    call_id = _start(calls).execute(CallDirection.INBOUND, "+12125550100")
    RecordRecordingConsent(calls, recorder).execute(call_id, accepted)
    assert recorder.started == [call_id] * started
