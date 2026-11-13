"""Función 3 de punta a punta contra PostgreSQL (resumen con un resumidor fijo, sin API)."""

from datetime import date

import pytest

from cobranza.domain.call import CallDirection, CallOutcome
from cobranza.domain.identity import VerificationOutcome


def _row(pool, call_id):
    with pool.connection() as conn:
        return conn.execute(
            """SELECT c.direction, c.caller_phone, d.external_id, a.external_id,
                      c.recording_consent, c.outcome, c.summary, c.ended_at IS NOT NULL
               FROM calls c
               LEFT JOIN debtors d ON d.id = c.debtor_id
               LEFT JOIN accounts a ON a.id = c.account_id
               WHERE c.id = %s""",
            (call_id,),
        ).fetchone()


def test_full_inbound_call(use_cases, pool, started_calls):
    call = use_cases.start_call.execute(CallDirection.INBOUND, "(305) 555-0001")
    started_calls.append(call)
    assert use_cases.record_recording_consent.execute(call, True)

    jane = use_cases.find_debtors_by_phone.execute("+13055550001")[0]
    assert use_cases.verify_identity.execute(
        call, jane.id, "Jane Carter", "1234", date(1985, 3, 14)) is VerificationOutcome.VERIFIED

    summary = use_cases.end_call.execute(call, CallOutcome.PAYMENT_TAKEN, "x" * 40)
    assert summary == "Summary of 40 chars."
    assert _row(pool, call) == ("inbound", "+13055550001", "TEST-001", None,
                                True, "payment_taken", summary, True)


def test_outbound_call_is_linked_to_the_account(use_cases, pool, started_calls):
    call = use_cases.start_call.execute(CallDirection.OUTBOUND, "+15125550002", "ACC-T002b")
    started_calls.append(call)
    direction, _, debtor_ext, account_ext, *_ = _row(pool, call)
    assert (direction, debtor_ext, account_ext) == ("outbound", "TEST-002", "ACC-T002b")


def test_recording_refused_closes_without_other_outcomes(use_cases, pool, started_calls):
    call = use_cases.start_call.execute(CallDirection.INBOUND, "+14155550005")
    started_calls.append(call)
    assert use_cases.record_recording_consent.execute(call, False) is False
    with pytest.raises(ValueError):
        use_cases.end_call.execute(call, CallOutcome.ARRANGEMENT_MADE)
    use_cases.end_call.execute(call, CallOutcome.RECORDING_REFUSED)
    row = _row(pool, call)
    assert (row[4], row[5], row[6], row[7]) == (False, "recording_refused", None, True)


# --- N13: última llamada saliente al deudor ---------------------------------------------------

def test_last_outbound_call_to_the_debtor(use_cases, started_calls, pool):
    from datetime import datetime, timedelta, timezone
    jane = use_cases.find_debtors_by_phone.execute("+13055550001")[0]
    older = use_cases.start_call.execute(CallDirection.OUTBOUND, "+13055550001", "ACC-T001")
    newer = use_cases.start_call.execute(CallDirection.OUTBOUND, "+13055550001", "ACC-T001")
    current = use_cases.start_call.execute(CallDirection.INBOUND, "+13055550001")
    started_calls.extend([older, newer, current])
    two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
    with pool.connection() as conn:
        conn.execute("UPDATE calls SET started_at = %s WHERE id = %s", (two_days_ago - timedelta(days=1), older))
        conn.execute("UPDATE calls SET started_at = %s, outcome = 'arrangement_made' WHERE id = %s",
                     (two_days_ago, newer))
    contact = use_cases.get_last_contact.execute(jane.id, current)
    assert abs(contact.started_at - two_days_ago) < timedelta(seconds=1) and contact.arrangement_made
    # La llamada en curso no cuenta, aunque sea saliente.
    assert use_cases.get_last_contact.execute(jane.id, newer).arrangement_made is False


# --- B3 / B4 -------------------------------------------------------------------------------------

def test_transfer_reason_and_debtor_unavailable_are_saved(use_cases, started_calls, pool):
    transferred = use_cases.start_call.execute(CallDirection.INBOUND, "+13055550001")
    unavailable = use_cases.start_call.execute(CallDirection.OUTBOUND, "+13055550001", "ACC-T001")
    started_calls.extend([transferred, unavailable])
    use_cases.end_call.execute(transferred, CallOutcome.TRANSFERRED_TO_HUMAN, transfer_reason="Asked for a person")
    use_cases.end_call.execute(unavailable, CallOutcome.DEBTOR_UNAVAILABLE)
    with pool.connection() as conn:
        rows = dict(conn.execute("SELECT id::text, (outcome, transfer_reason) FROM calls WHERE id = ANY(%s::uuid[])",
                                 ([transferred, unavailable],)).fetchall())
    assert rows[transferred] == ("transferred_to_human", "Asked for a person")
    assert rows[unavailable] == ("debtor_unavailable", None)
