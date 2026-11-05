"""Función 2 de punta a punta contra PostgreSQL (HMAC de pgcrypto en el seed vs. HMAC de Python)."""

from datetime import date

from cobranza.domain.identity import VerificationOutcome as V

JANE_DOB = date(1985, 3, 14)  # TEST-001, SSN 1234


def test_jane_verifies_with_correct_data(use_cases, new_call, debtor_id, pool):
    call = new_call()
    jane = debtor_id("TEST-001")
    result = use_cases.verify_identity.execute(call, jane, "Jane Carter", "1234", JANE_DOB)
    assert result is V.VERIFIED
    with pool.connection() as conn:
        row = conn.execute("SELECT debtor_id, verification_attempts, identity_verified FROM calls WHERE id = %s",
                           (call,)).fetchone()
    assert (str(row[0]), row[1], row[2]) == (jane, 1, True)


def test_two_failures_close_the_call(use_cases, new_call, debtor_id):
    call, jane = new_call(), debtor_id("TEST-001")
    verify = use_cases.verify_identity.execute
    assert verify(call, jane, "Jane Carter", "0000", JANE_DOB) is V.FAILED
    assert verify(call, jane, "Jane Carter", "1234", date(2000, 1, 1)) is V.MAX_ATTEMPTS_REACHED


def test_name_retry_does_not_touch_the_call(use_cases, new_call, debtor_id, pool):
    call = new_call()
    result = use_cases.verify_identity.execute(call, debtor_id("TEST-001"), "Jane Karter", "1234", JANE_DOB)
    assert result is V.NAME_RETRY
    with pool.connection() as conn:
        assert conn.execute("SELECT verification_attempts FROM calls WHERE id = %s", (call,)).fetchone()[0] == 0


def test_lockout_after_five_failures_in_24h(use_cases, new_call, debtor_id):
    new_call("TEST-009", failed=2, hours_ago=3)
    new_call("TEST-009", failed=2, hours_ago=10)
    grace = debtor_id("TEST-009")  # dob 1995-04-18, SSN 6666
    call = new_call()
    assert use_cases.verify_identity.execute(call, grace, "Grace Liu", "0000", date(1995, 4, 18)) is V.LOCKED


def test_old_failures_do_not_lock(use_cases, new_call, debtor_id):
    new_call("TEST-009", failed=2, hours_ago=30)
    new_call("TEST-009", failed=2, hours_ago=40)
    grace = debtor_id("TEST-009")
    call = new_call()
    assert use_cases.verify_identity.execute(call, grace, "Grace Liu", "6666", date(1995, 4, 18)) is V.VERIFIED


def test_shared_phone_verifies_the_right_person(use_cases, new_call, debtor_id):
    call = new_call()
    luis = debtor_id("TEST-008")  # comparte teléfono con Ana; dob 1989-02-28, SSN 5555
    assert use_cases.verify_identity.execute(call, luis, "Luis Reyes", "5555", date(1989, 2, 28)) is V.VERIFIED
