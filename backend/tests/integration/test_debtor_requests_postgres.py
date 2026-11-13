"""Función 7 de punta a punta contra PostgreSQL. Usa los casos TEST-xxx de db/init/002_seed_mock.sql."""

from datetime import date

import pytest

from cobranza.domain.arrangement import ArrangementRuleError, RuleViolation as R
from cobranza.domain.call import CallDirection
from cobranza.domain.identity import VerificationOutcome


@pytest.fixture
def verified_jane(use_cases, started_calls):
    call = use_cases.start_call.execute(CallDirection.INBOUND, "+13055550001")
    started_calls.append(call)
    use_cases.record_recording_consent.execute(call, True)
    jane = use_cases.find_debtors_by_phone.execute("+13055550001")[0]
    assert use_cases.verify_identity.execute(
        call, jane.id, "Jane Carter", "1234", date(1985, 3, 14)) is VerificationOutcome.VERIFIED
    return call


def _call(pool, call_id):
    with pool.connection() as conn:
        return conn.execute(
            """SELECT c.outcome, c.summary, a.external_id, c.ended_at IS NOT NULL
               FROM calls c LEFT JOIN accounts a ON a.id = c.account_id WHERE c.id = %s""",
            (call_id,),
        ).fetchone()


def test_dispute_blocks_further_collection(use_cases, verified_jane, pool):
    summary = use_cases.record_dispute.execute(verified_jane, "ACC-T001", "x" * 20)
    assert _call(pool, verified_jane) == ("dispute", summary, "ACC-T001", True)

    jane = use_cases.find_debtors_by_phone.execute("+13055550001")[0]
    assert jane.accounts[0].is_disputed
    assert jane.accounts[0].status == "DISPUTE"   # N11: estado nuevo de la cuenta
    assert jane.collectable_accounts == ()


def test_dispute_only_marks_the_disputed_account(use_cases, started_calls):
    call = use_cases.start_call.execute(CallDirection.OUTBOUND, "+15125550002", "ACC-T002a")
    started_calls.append(call)
    use_cases.record_recording_consent.execute(call, True)
    mark = use_cases.get_debtor_by_account.execute("ACC-T002a")
    assert use_cases.verify_identity.execute(
        call, mark.id, "Mark Holloway", "5678", date(1979, 11, 2)) is VerificationOutcome.VERIFIED
    use_cases.record_dispute.execute(call, "ACC-T002a")

    mark = use_cases.get_debtor_by_account.execute("ACC-T002a")
    assert {a.external_id: a.is_disputed for a in mark.accounts} == {"ACC-T002a": True, "ACC-T002b": False}
    assert [a.external_id for a in mark.collectable_accounts] == ["ACC-T002b"]


def test_cannot_dispute_the_account_of_another_debtor(use_cases, verified_jane):
    with pytest.raises(ArrangementRuleError) as e:
        use_cases.record_dispute.execute(verified_jane, "ACC-T002a")
    assert e.value.violation is R.IDENTITY_NOT_VERIFIED


def test_do_not_call_blocks_all_accounts_of_the_debtor(use_cases, started_calls, pool):
    call = use_cases.start_call.execute(CallDirection.OUTBOUND, "+15125550002", "ACC-T002a")
    started_calls.append(call)
    use_cases.mark_do_not_call.execute(call)
    assert _call(pool, call)[0] == "do_not_call"

    mark = use_cases.get_debtor_by_account.execute("ACC-T002a")
    assert mark.do_not_call
    assert mark.collectable_accounts == ()


def test_unverified_inbound_cannot_block_calls(use_cases, started_calls):
    call = use_cases.start_call.execute(CallDirection.INBOUND, "+13055550001")
    started_calls.append(call)
    with pytest.raises(ArrangementRuleError) as e:
        use_cases.mark_do_not_call.execute(call)
    assert e.value.violation is R.IDENTITY_NOT_VERIFIED
    assert not use_cases.find_debtors_by_phone.execute("+13055550001")[0].do_not_call
