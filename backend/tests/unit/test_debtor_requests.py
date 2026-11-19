"""Función 7 (disputas y "no llamar") sin base de datos."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from cobranza.application.use_cases.debtor_requests import MarkDoNotCall, RecordCollectionHold, RecordDispute
from cobranza.application.use_cases.register_call import EndCall
from cobranza.domain.arrangement import ArrangementRuleError, RuleViolation as R
from cobranza.domain.call import CallDirection, CallOutcome, CallRecord
from cobranza.domain.debtor import AccountSummary, CollectionHold, DebtorSummary
from cobranza.domain.identity import CallVerificationState

NOW = datetime(2026, 11, 4, 15, 0, tzinfo=timezone.utc)


class FixedClock:
    def now(self):
        return NOW


class FakeSummarizer:
    def summarize(self, transcript, identity_verified=True):
        return "Debtor says the payment went through."


class FakeCalls:
    def __init__(self, direction=CallDirection.INBOUND, debtor_id="deb-1", consent=True, verified=True):
        self.record = CallRecord("c1", direction, debtor_id, None, consent, None)
        self.state = CallVerificationState(debtor_id, 1 if verified else 0, verified)
        self.linked = None
        self.closed = None

    def get(self, call_id):
        return self.record if call_id == "c1" else None

    def get_verification_state(self, call_id):
        return self.state if call_id == "c1" else None

    def link_account(self, call_id, account_id):
        self.linked = account_id

    def close(self, call_id, outcome, summary, ended_at):
        self.record = replace(self.record, ended_at=ended_at)
        self.closed = (outcome, summary)


class FakeDebtors:
    def __init__(self):
        self.disputed = []
        self.do_not_call = []
        self.holds = []

    def get_by_account(self, account_external_id):
        if account_external_id != "ACC-1":
            return None
        account = AccountSummary(
            id="acc-1", external_id="ACC-1", creditor_name="Acme", account_number_masked="****0001",
            current_balance_cents=10000, status="NSF", payment_method="ACH", nsf_amount_cents=None,
            nsf_fee_cents=0, nsf_date=None, nsf_return_code=None, is_disputed=False,
        )
        return DebtorSummary(
            id="deb-1", external_id="DEB-1", first_name="Jane", last_name="Doe",
            phone_primary="+12125550100", us_state="NY", timezone="America/New_York",
            timezone_inferred=False, do_not_call=False, accounts=(account,),
        )

    def mark_disputed(self, account_id, status):
        self.disputed.append(account_id)
        self.dispute_status = status

    def set_collection_hold(self, debtor_id, hold, details, at):
        self.holds.append((debtor_id, hold, details, at))

    def mark_do_not_call(self, debtor_id):
        self.do_not_call.append(debtor_id)


def _build(use_case, calls=None):
    calls = calls or FakeCalls()
    debtors = FakeDebtors()
    return use_case(calls, debtors, EndCall(calls, FakeSummarizer(), FixedClock())), calls, debtors


def _violation(fn, *args):
    with pytest.raises(ArrangementRuleError) as e:
        fn(*args)
    return e.value.violation


# --- disputas -----------------------------------------------------------------

def test_dispute_marks_the_account_links_it_and_closes_the_call():
    dispute, calls, debtors = _build(RecordDispute)
    summary = dispute.execute("c1", "ACC-1", "Debtor: I did pay that.")
    assert debtors.disputed == ["acc-1"] and debtors.dispute_status == "DISPUTE"   # N11
    assert calls.linked == "acc-1"
    assert calls.closed == (CallOutcome.DISPUTE, summary)
    assert summary == "Debtor says the payment went through."


@pytest.mark.parametrize("calls, violation", [
    (FakeCalls(consent=None), R.RECORDING_CONSENT_MISSING),
    (FakeCalls(consent=False), R.RECORDING_CONSENT_MISSING),
    (FakeCalls(verified=False), R.IDENTITY_NOT_VERIFIED),
    (FakeCalls(debtor_id="someone-else"), R.IDENTITY_NOT_VERIFIED),
])
def test_dispute_needs_recording_and_the_verified_owner(calls, violation):
    dispute, calls, debtors = _build(RecordDispute, calls)
    assert _violation(dispute.execute, "c1", "ACC-1") is violation
    assert debtors.disputed == []
    assert calls.closed is None


def test_dispute_on_unknown_call_or_account_raises():
    dispute, *_ = _build(RecordDispute)
    with pytest.raises(ValueError):
        dispute.execute("missing", "ACC-1")
    with pytest.raises(ValueError):
        dispute.execute("c1", "ACC-MISSING")


def test_call_cannot_be_disputed_after_closing():
    dispute, *_ = _build(RecordDispute)
    dispute.execute("c1", "ACC-1")
    with pytest.raises(ValueError):
        dispute.execute("c1", "ACC-1")


# --- no llamar ----------------------------------------------------------------

def test_do_not_call_marks_the_debtor_and_closes_the_call():
    mark, calls, debtors = _build(MarkDoNotCall)
    mark.execute("c1")
    assert debtors.do_not_call == ["deb-1"]
    assert calls.closed == (CallOutcome.DO_NOT_CALL, None)


def test_outbound_request_is_honored_without_verification():
    mark, _, debtors = _build(MarkDoNotCall, FakeCalls(CallDirection.OUTBOUND, verified=False))
    mark.execute("c1")
    assert debtors.do_not_call == ["deb-1"]


def test_inbound_request_needs_verification():
    mark, calls, debtors = _build(MarkDoNotCall, FakeCalls(verified=False))
    assert _violation(mark.execute, "c1") is R.IDENTITY_NOT_VERIFIED
    assert debtors.do_not_call == []
    assert calls.closed is None


def test_request_needs_a_known_debtor():
    mark, *_ = _build(MarkDoNotCall, FakeCalls(debtor_id=None, verified=False))
    assert _violation(mark.execute, "c1") is R.IDENTITY_NOT_VERIFIED


def test_request_after_refusing_the_recording_is_saved_and_closes_as_refused():
    mark, calls, debtors = _build(MarkDoNotCall, FakeCalls(CallDirection.OUTBOUND, consent=False, verified=False))
    mark.execute("c1")
    assert debtors.do_not_call == ["deb-1"]
    assert calls.closed == (CallOutcome.RECORDING_REFUSED, None)


# --- prueba de ataque: abogado, bancarrota o fallecido frenan la cobranza ------------------

def _build_hold(calls=None):
    calls = calls or FakeCalls()
    debtors = FakeDebtors()
    return RecordCollectionHold(calls, debtors, EndCall(calls, FakeSummarizer(), FixedClock()), FixedClock()), \
        calls, debtors


@pytest.mark.parametrize("hold", list(CollectionHold))
def test_a_legal_hold_is_saved_and_closes_the_call(hold):
    record, calls, debtors = _build_hold()
    record.execute("c1", hold, "  Mark Davis, 305 555 0199  ")
    assert debtors.holds == [("deb-1", hold, "Mark Davis, 305 555 0199", NOW)]
    assert calls.closed == (CallOutcome.COLLECTION_HOLD, None)


def test_a_relative_can_report_the_death_on_an_outbound_call_without_verification():
    record, _, debtors = _build_hold(FakeCalls(CallDirection.OUTBOUND, verified=False))
    record.execute("c1", CollectionHold.DECEASED, "Her son, Tom")
    assert debtors.holds[0][1] is CollectionHold.DECEASED


def test_an_inbound_hold_needs_verification():
    record, calls, debtors = _build_hold(FakeCalls(verified=False))
    assert _violation(record.execute, "c1", CollectionHold.ATTORNEY) is R.IDENTITY_NOT_VERIFIED
    assert debtors.holds == [] and calls.closed is None


def test_a_held_debtor_cannot_be_collected():
    debtor = FakeDebtors().get_by_account("ACC-1")
    assert debtor.collectable_accounts
    held = replace(debtor, collection_hold=CollectionHold.BANKRUPTCY)
    assert held.collectable_accounts == ()
