"""Dominio y caso de uso de la Función 2, sin base de datos."""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import pytest

from cobranza.infrastructure.services.hmac_pii_hasher import HmacSha256PiiHasher
from cobranza.application.use_cases.verify_identity import VerifyIdentity
from cobranza.domain.identity import (
    CallVerificationState,
    IdentityRecord,
    VerificationOutcome as V,
    names_match,
)

NOW = datetime(2026, 10, 29, 15, 0, tzinfo=timezone.utc)
hasher = HmacSha256PiiHasher("test-key")
JANE = IdentityRecord("jane", "Jane", "Carter",
                      dob_hash=hasher.hash("1985-03-14"), ssn_last4_hash=hasher.hash("1234"))


# --- nombres ------------------------------------------------------------------

@pytest.mark.parametrize("spoken", [
    "Jane Carter", "jane carter", "  JANE   CARTER ", "Jane Marie Carter", "Jáne Cárter",
])
def test_names_that_match(spoken):
    assert names_match(spoken, "Jane", "Carter")


@pytest.mark.parametrize("spoken", ["Jane", "Carter", "Jane Smith", "Janet Carter", "Carter Jane", ""])
def test_names_that_do_not_match(spoken):
    assert not names_match(spoken, "Jane", "Carter")


def test_compound_last_names_and_apostrophes():
    assert names_match("Mary Smith-Jones", "Mary", "Smith Jones")
    assert names_match("Sean O'Brien", "Sean", "OBrien")


# --- caso de uso con dobles en memoria ----------------------------------------

@dataclass
class FakeCall:
    debtor_id: str | None = None
    attempts: int = 0
    verified: bool = False
    started_at: datetime = NOW


@dataclass
class FakeCalls:
    calls: dict = field(default_factory=dict)

    def get_verification_state(self, call_id):
        c = self.calls.get(call_id)
        return CallVerificationState(c.debtor_id, c.attempts, c.verified) if c else None

    def record_verification_attempt(self, call_id, debtor_id, succeeded):
        c = self.calls[call_id]
        c.attempts += 1
        c.verified = c.verified or succeeded
        c.debtor_id = debtor_id

    def count_failed_verifications_since(self, debtor_id, since):
        return sum(c.attempts - c.verified for c in self.calls.values()
                   if c.debtor_id == debtor_id and c.started_at >= since)


class FakeIdentities:
    def get_identity(self, debtor_id):
        return JANE if debtor_id == "jane" else None


class FixedClock:
    def now(self):
        return NOW


def _setup(**calls):
    fake_calls = FakeCalls({"c1": FakeCall(), **calls})
    return VerifyIdentity(FakeIdentities(), fake_calls, hasher, FixedClock()), fake_calls


def _verify(uc, name="Jane Carter", ssn="1234", dob=date(1985, 3, 14), call="c1", spelled=False):
    return uc.execute(call, "jane", name, ssn, dob, name_was_spelled=spelled)


def test_correct_data_verifies():
    uc, calls = _setup()
    assert _verify(uc) is V.VERIFIED
    assert calls.calls["c1"].verified and calls.calls["c1"].debtor_id == "jane"


def test_wrong_ssn_or_dob_fails_without_saying_which():
    uc, _ = _setup()
    assert _verify(uc, ssn="9999") is V.FAILED
    uc, _ = _setup()
    assert _verify(uc, dob=date(1985, 3, 15)) is V.FAILED


def test_malformed_ssn_counts_as_failure():
    uc, calls = _setup()
    assert _verify(uc, ssn="12a4") is V.FAILED
    assert calls.calls["c1"].attempts == 1


def test_second_failure_in_call_ends_verification():
    uc, _ = _setup()
    assert _verify(uc, ssn="0000") is V.FAILED
    assert _verify(uc, ssn="0000") is V.MAX_ATTEMPTS_REACHED
    assert _verify(uc) is V.MAX_ATTEMPTS_REACHED  # ni con los datos correctos


def test_wrong_name_asks_to_spell_without_counting():
    uc, calls = _setup()
    assert _verify(uc, name="Jane Karter") is V.NAME_RETRY
    assert calls.calls["c1"].attempts == 0
    assert _verify(uc, name="Jane Carter", spelled=True) is V.VERIFIED


def test_wrong_name_after_spelling_counts_as_failure():
    uc, calls = _setup()
    assert _verify(uc, name="Jane Karter", spelled=True) is V.FAILED
    assert calls.calls["c1"].attempts == 1


def test_five_failures_in_24h_locks_across_calls():
    old = FakeCall(debtor_id="jane", attempts=2, started_at=NOW - timedelta(hours=5))
    older = FakeCall(debtor_id="jane", attempts=2, started_at=NOW - timedelta(hours=20))
    uc, calls = _setup(old=old, older=older)
    assert _verify(uc, ssn="0000") is V.LOCKED      # 5.º fallo
    calls.calls["c2"] = FakeCall()                  # llama otra vez
    assert _verify(uc, call="c2") is V.LOCKED       # bloqueado aunque ahora acierte


def test_failures_older_than_24h_do_not_count():
    ancient = FakeCall(debtor_id="jane", attempts=2, started_at=NOW - timedelta(hours=25))
    ancient2 = FakeCall(debtor_id="jane", attempts=2, started_at=NOW - timedelta(hours=30))
    uc, _ = _setup(a=ancient, b=ancient2)
    assert _verify(uc, ssn="0000") is V.FAILED


def test_already_verified_call_stays_verified_for_same_debtor():
    uc, _ = _setup(c1=FakeCall(debtor_id="jane", attempts=1, verified=True))
    assert _verify(uc) is V.VERIFIED


def test_call_verified_for_another_debtor_is_rejected():
    uc, _ = _setup(c1=FakeCall(debtor_id="ana", attempts=1, verified=True))
    with pytest.raises(ValueError):
        _verify(uc)


def test_unknown_call_or_debtor_raises():
    uc, _ = _setup()
    with pytest.raises(ValueError):
        _verify(uc, call="missing")
    with pytest.raises(ValueError):
        uc.execute("c1", "nobody", "Jane Carter", "1234", date(1985, 3, 14))
