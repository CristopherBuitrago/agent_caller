"""Lista diaria de salientes: armado y salida del deudor que llama y se verifica, sin base de datos."""

from datetime import date, datetime, timedelta, timezone

import pytest

from cobranza.application.use_cases.outbound_list import (
    ATTEMPTS_WINDOW,
    MAX_CALL_ATTEMPTS,
    BuildDailyOutboundList,
)
from cobranza.application.use_cases.verify_identity import VerifyIdentity
from cobranza.domain.call import CallDirection, CallRecord
from cobranza.domain.identity import CallVerificationState, IdentityRecord, VerificationOutcome as V
from cobranza.infrastructure.services.hmac_pii_hasher import HmacSha256PiiHasher

NOW = datetime(2026, 11, 12, 15, 0, tzinfo=timezone.utc)
hasher = HmacSha256PiiHasher("test-key")
JANE = IdentityRecord("jane", "Jane", "Carter", dob_hash=hasher.hash("1985-03-14"),
                      ssn_last4_hash=hasher.hash("1234"))


class FixedClock:
    def now(self):
        return NOW


class FakeOutbound:
    def __init__(self):
        self.removed = []
        self.built = []

    def build(self, list_date, attempts_since, max_attempts, conversation_since):
        self.built.append((list_date, attempts_since, max_attempts, conversation_since))
        return 3

    def remove_debtor(self, debtor_id, reason, call_id):
        self.removed.append((debtor_id, reason, call_id))
        return 1


class FakeCalls:
    def __init__(self, direction):
        self.direction = direction
        self.attempts = 0
        self.verified = False

    def get(self, call_id):
        return CallRecord(call_id, self.direction, None, None, True, None)

    def get_verification_state(self, call_id):
        return CallVerificationState("jane" if self.attempts else None, self.attempts, self.verified)

    def record_verification_attempt(self, call_id, debtor_id, succeeded):
        self.attempts += 1
        self.verified = self.verified or succeeded

    def count_failed_verifications_since(self, debtor_id, since):
        return 0


class FakeIdentities:
    def get_identity(self, debtor_id):
        return JANE


def _verify(direction, ssn="1234"):
    outbound = FakeOutbound()
    uc = VerifyIdentity(FakeIdentities(), FakeCalls(direction), hasher, FixedClock(), outbound)
    outcome = uc.execute("c1", "jane", "Jane Carter", ssn, date(1985, 3, 14))
    return outcome, outbound.removed


def test_inbound_caller_who_verifies_leaves_the_outbound_list():
    assert _verify(CallDirection.INBOUND) == (V.VERIFIED, [("jane", "inbound_call", "c1")])


@pytest.mark.parametrize("direction, ssn", [
    (CallDirection.OUTBOUND, "1234"),  # la llamada la hizo el agente: la lista la marca quien llama
    (CallDirection.INBOUND, "9999"),   # no se verificó: sigue en la lista (opción A)
])
def test_only_a_verified_inbound_call_removes_the_debtor(direction, ssn):
    assert _verify(direction, ssn)[1] == []


def test_build_uses_the_reg_f_windows():
    outbound = FakeOutbound()
    assert BuildDailyOutboundList(outbound, FixedClock()).execute(date(2026, 11, 13)) == 3
    assert outbound.built == [(date(2026, 11, 13), NOW - ATTEMPTS_WINDOW, MAX_CALL_ATTEMPTS,
                               NOW - timedelta(days=7))]
