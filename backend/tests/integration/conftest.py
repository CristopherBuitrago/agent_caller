import os

import pytest
from psycopg_pool import ConnectionPool

from cobranza.infrastructure.config.container import build_use_cases


@pytest.fixture(scope="session")
def pool():
    with ConnectionPool(os.environ["DATABASE_URL"], min_size=1, max_size=2) as p:
        yield p


class StaticSummarizer:
    """Las pruebas de integración no llaman a la API de Claude."""

    def summarize(self, transcript):
        return f"Summary of {len(transcript)} chars."


@pytest.fixture(scope="session")
def use_cases(pool):
    return build_use_cases(pool, os.environ["PII_HMAC_KEY"], summarizer=StaticSummarizer())


@pytest.fixture
def started_calls(pool):
    """Lista donde las pruebas anotan los ids de llamadas que crean; se borran al terminar."""
    ids = []
    with pool.connection() as conn:
        accounts = conn.execute(
            "SELECT id, status, is_disputed FROM accounts WHERE external_id LIKE 'ACC-T%'").fetchall()
        debtors = conn.execute("SELECT id, do_not_call FROM debtors WHERE external_id LIKE 'TEST-%'").fetchall()
    yield ids
    with pool.connection() as conn:
        # Los casos de uso cambian estas marcas; se restauran para las demás pruebas.
        for account_id, status, is_disputed in accounts:
            conn.execute("UPDATE accounts SET status = %s, is_disputed = %s WHERE id = %s",
                         (status, is_disputed, account_id))
        for debtor_id, do_not_call in debtors:
            conn.execute("UPDATE debtors SET do_not_call = %s WHERE id = %s", (do_not_call, debtor_id))
        conn.execute("DELETE FROM hardship_assessments WHERE call_id = ANY(%s::uuid[])", (ids,))
        conn.execute(
            """DELETE FROM payment_results WHERE arrangement_id IN
               (SELECT id FROM payment_arrangements WHERE call_id = ANY(%s::uuid[]))""",
            (ids,),
        )
        conn.execute(
            """DELETE FROM sms_messages WHERE arrangement_id IN
               (SELECT id FROM payment_arrangements WHERE call_id = ANY(%s::uuid[]))""",
            (ids,),
        )
        conn.execute(
            """DELETE FROM scheduled_payments WHERE arrangement_id IN
               (SELECT id FROM payment_arrangements WHERE call_id = ANY(%s::uuid[]))""",
            (ids,),
        )
        conn.execute("DELETE FROM payment_arrangements WHERE call_id = ANY(%s::uuid[])", (ids,))
        conn.execute("DELETE FROM calls WHERE id = ANY(%s::uuid[])", (ids,))


@pytest.fixture
def new_call(pool):
    """Crea llamadas de prueba y las borra al terminar.

    new_call()                         -> llamada nueva, sin intentos
    new_call(debtor_ext, failed=2, hours_ago=3) -> llamada vieja con fallos previos
    """
    created = []

    def make(debtor_ext=None, failed=0, hours_ago=0):
        with pool.connection() as conn:
            row = conn.execute(
                """INSERT INTO calls (debtor_id, direction, caller_phone, started_at, verification_attempts)
                   VALUES ((SELECT id FROM debtors WHERE external_id = %s), 'inbound', '+10000000000',
                           now() - make_interval(hours => %s), %s)
                   RETURNING id""",
                (debtor_ext, hours_ago, failed),
            ).fetchone()
        created.append(row[0])
        return str(row[0])

    yield make
    with pool.connection() as conn:
        conn.execute("DELETE FROM calls WHERE id = ANY(%s)", (created,))


@pytest.fixture
def debtor_id(pool):
    def lookup(external_id):
        with pool.connection() as conn:
            return str(conn.execute("SELECT id FROM debtors WHERE external_id = %s",
                                    (external_id,)).fetchone()[0])
    return lookup


@pytest.fixture
def find_by_phone(use_cases):
    return use_cases.find_debtors_by_phone.execute


@pytest.fixture
def get_by_account(use_cases):
    return use_cases.get_debtor_by_account.execute
