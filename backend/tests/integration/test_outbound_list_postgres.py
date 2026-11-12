"""Lista diaria de salientes contra PostgreSQL, con los casos TEST-xxx de db/init/002_seed_mock.sql."""

from datetime import date, datetime, timedelta, timezone
from itertools import count

import pytest

from cobranza.domain.call import CallDirection
from cobranza.domain.identity import VerificationOutcome

JANE_DOB = date(1985, 3, 14)
_dates = count()


@pytest.fixture
def list_date(pool, started_calls):
    """Un día de lista que no usa nadie más; sus filas se borran antes que las llamadas de prueba."""
    day = date(2099, 1, 1) + timedelta(days=next(_dates))
    yield day
    with pool.connection() as conn:
        conn.execute("DELETE FROM outbound_call_list WHERE list_date = %s", (day,))


def _test_accounts(use_cases, day):
    return {e.account_external_id: e for e in use_cases.get_outbound_calls.execute(day)
            if e.account_external_id.startswith("ACC-T")}


def _verified_call(use_cases, started_calls, direction):
    account = "ACC-T001" if direction is CallDirection.OUTBOUND else None
    call = use_cases.start_call.execute(direction, "+13055550001", account)
    started_calls.append(call)
    use_cases.record_recording_consent.execute(call, True)
    jane = use_cases.find_debtors_by_phone.execute("+13055550001")[0]
    assert use_cases.verify_identity.execute(
        call, jane.id, "Jane Carter", "1234", JANE_DOB) is VerificationOutcome.VERIFIED
    return call


def test_list_has_only_callable_nsf_accounts(use_cases, list_date):
    assert use_cases.build_daily_outbound_list.execute(list_date) > 0
    # Fuera: T004 en disputa, T005 "no llamar", T006 pagada, T008 y T009 no están en NSF.
    assert set(_test_accounts(use_cases, list_date)) == {
        "ACC-T001", "ACC-T002a", "ACC-T002b", "ACC-T003", "ACC-T007"}
    assert use_cases.build_daily_outbound_list.execute(list_date) == 0  # no repite


def test_inbound_call_with_verified_identity_removes_the_debtor(use_cases, started_calls, pool, list_date):
    use_cases.build_daily_outbound_list.execute(list_date)
    call = _verified_call(use_cases, started_calls, CallDirection.INBOUND)
    assert "ACC-T001" not in _test_accounts(use_cases, list_date)
    with pool.connection() as conn:
        row = conn.execute(
            """SELECT o.status, o.removed_reason, o.removed_by_call_id::text FROM outbound_call_list o
               JOIN accounts a ON a.id = o.account_id WHERE o.list_date = %s AND a.external_id = 'ACC-T001'""",
            (list_date,),
        ).fetchone()
    assert row == ("removed", "inbound_call", call)


def test_inbound_call_without_verification_keeps_the_debtor(use_cases, started_calls, list_date):
    use_cases.build_daily_outbound_list.execute(list_date)
    call = use_cases.start_call.execute(CallDirection.INBOUND, "+13055550001")
    started_calls.append(call)
    use_cases.record_recording_consent.execute(call, True)
    jane = use_cases.find_debtors_by_phone.execute("+13055550001")[0]
    use_cases.verify_identity.execute(call, jane.id, "Jane Carter", "0000", JANE_DOB)
    assert "ACC-T001" in _test_accounts(use_cases, list_date)


def test_outbound_call_is_marked_called_not_removed(use_cases, started_calls, list_date):
    use_cases.build_daily_outbound_list.execute(list_date)
    entry = _test_accounts(use_cases, list_date)["ACC-T001"]
    call = _verified_call(use_cases, started_calls, CallDirection.OUTBOUND)
    assert "ACC-T001" in _test_accounts(use_cases, list_date)   # verificar en saliente no la saca
    use_cases.mark_outbound_called.execute(entry.id, call)
    assert "ACC-T001" not in _test_accounts(use_cases, list_date)


def test_reg_f_seven_outbound_attempts_in_seven_days_leaves_the_account_out(
        use_cases, started_calls, list_date):
    for _ in range(7):
        started_calls.append(use_cases.start_call.execute(CallDirection.OUTBOUND, "+13055550001", "ACC-T001"))
    use_cases.build_daily_outbound_list.execute(list_date)
    accounts = _test_accounts(use_cases, list_date)
    assert "ACC-T001" not in accounts and "ACC-T002a" in accounts


def test_reg_f_no_call_for_seven_days_after_a_conversation(use_cases, started_calls, list_date):
    _verified_call(use_cases, started_calls, CallDirection.INBOUND)  # Jane habló hoy
    use_cases.build_daily_outbound_list.execute(list_date)
    assert "ACC-T001" not in _test_accounts(use_cases, list_date)
