"""N10 contra PostgreSQL: resultados de pago y acuerdos rotos con el acuerdo de Jane (TEST-001)."""

from datetime import date, datetime, timedelta, timezone

import pytest

from cobranza.domain.call import CallDirection
from cobranza.domain.identity import VerificationOutcome

NOW = datetime(2026, 11, 13, 15, 0, tzinfo=timezone.utc)


@pytest.fixture
def jane_partial(use_cases, started_calls):
    """Jane acepta USD 90 hoy y USD 395 a los 30 días. Devuelve (acuerdo, [(cuota, fecha)])."""
    call = use_cases.start_call.execute(CallDirection.INBOUND, "+13055550001")
    started_calls.append(call)
    use_cases.record_recording_consent.execute(call, True)
    jane = use_cases.find_debtors_by_phone.execute("+13055550001")[0]
    assert use_cases.verify_identity.execute(
        call, jane.id, "Jane Carter", "1234", date(1985, 3, 14)) is VerificationOutcome.VERIFIED
    partial = use_cases.propose_partial_payment.execute(call, "ACC-T001", 9000)
    arrangement_id = use_cases.record_offer_response.execute(call, partial.id, accepted=True)
    return arrangement_id


def _state(pool, arrangement_id):
    with pool.connection() as conn:
        arrangement = conn.execute(
            "SELECT pa.status, a.status FROM payment_arrangements pa JOIN accounts a ON a.id = pa.account_id "
            "WHERE pa.id = %s", (arrangement_id,)).fetchone()
        payments = conn.execute(
            "SELECT id::text, status, due_date FROM scheduled_payments WHERE arrangement_id = %s ORDER BY sequence",
            (arrangement_id,)).fetchall()
    return arrangement, payments


def test_paying_every_installment_completes_the_arrangement(use_cases, pool, jane_partial):
    (_, _), [(first, _, _), (second, _, _)] = _state(pool, jane_partial)
    first_result = use_cases.record_payment_result.execute(first, "REF-A", 9000, "approved", NOW)
    assert first_result.arrangement_completed is False
    assert use_cases.record_payment_result.execute(first, "REF-A", 9000, "approved", NOW) is None  # aviso repetido
    assert use_cases.record_payment_result.execute(second, "REF-B", 39500, "approved", NOW).arrangement_completed
    (arrangement_status, account_status), payments = _state(pool, jane_partial)
    assert arrangement_status == "completed" and [p[1] for p in payments] == ["paid", "paid"]
    assert account_status == "PTP"   # el estado al pagar todo está por definir con el jefe


def test_a_declined_payment_does_not_mark_the_installment_paid(use_cases, pool, jane_partial):
    (_, _), [(first, _, _), _] = _state(pool, jane_partial)
    use_cases.record_payment_result.execute(first, "REF-D", 9000, "declined", NOW)
    assert [p[1] for p in _state(pool, jane_partial)[1]] == ["pending", "pending"]


def test_unpaid_installment_breaks_the_arrangement_after_five_days(use_cases, pool, jane_partial):
    (_, _), [(_, _, first_due), _] = _state(pool, jane_partial)
    assert jane_partial not in use_cases.break_overdue_arrangements.execute(first_due + timedelta(days=4))
    assert jane_partial in use_cases.break_overdue_arrangements.execute(first_due + timedelta(days=5))
    (arrangement_status, account_status), payments = _state(pool, jane_partial)
    assert (arrangement_status, account_status) == ("broken", "NSF")      # vuelve a la lista diaria
    assert [p[1] for p in payments] == ["cancelled", "cancelled"]         # no salen más SMS


def test_paid_installments_do_not_break_the_arrangement(use_cases, pool, jane_partial):
    (_, _), [(first, _, first_due), (_, _, second_due)] = _state(pool, jane_partial)
    use_cases.record_payment_result.execute(first, "REF-P", 9000, "approved", NOW)
    assert jane_partial not in use_cases.break_overdue_arrangements.execute(first_due + timedelta(days=10))
    assert jane_partial in use_cases.break_overdue_arrangements.execute(second_due + timedelta(days=5))
    assert [p[1] for p in _state(pool, jane_partial)[1]] == ["paid", "cancelled"]
