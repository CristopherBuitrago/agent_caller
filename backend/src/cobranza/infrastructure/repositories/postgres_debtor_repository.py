"""Adaptador de DebtorRepository sobre PostgreSQL (modelo provisional, datos simulados).

Solo traduce filas a objetos del dominio; las reglas de negocio viven en el dominio
y en los casos de uso.
"""

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from cobranza.domain.debtor import AccountSummary, DebtorSummary

# Columnas explícitas: dob_hmac y ssn_last4_hmac nunca se leen aquí.
_DEBTOR_WITH_ACCOUNTS_SQL = """
    SELECT d.id AS debtor_id, d.external_id AS debtor_external_id,
           d.first_name, d.last_name, d.phone_primary, d.us_state, d.timezone, d.do_not_call,
           a.id AS account_id, a.external_id AS account_external_id,
           a.creditor_name, a.account_number_masked, a.current_balance_cents, a.status,
           a.payment_method, a.nsf_amount_cents, a.nsf_fee_cents, a.nsf_date,
           a.nsf_return_code, a.is_disputed
    FROM debtors d
    LEFT JOIN accounts a ON a.debtor_id = d.id
    WHERE d.id = ANY(%(debtor_ids)s)
    ORDER BY d.last_name, d.first_name, d.id, a.created_at, a.id
"""


class PostgresDebtorRepository:
    def __init__(self, pool: ConnectionPool):
        self._pool = pool

    def find_by_phone(self, phone_e164: str) -> list[DebtorSummary]:
        with self._pool.connection() as conn:
            ids = conn.execute(
                "SELECT id FROM debtors WHERE phone_primary = %(p)s OR phone_secondary = %(p)s",
                {"p": phone_e164},
            ).fetchall()
            return self._load_debtors(conn, [row[0] for row in ids])

    def get_by_account(self, account_external_id: str) -> DebtorSummary | None:
        with self._pool.connection() as conn:
            row = conn.execute(
                "SELECT debtor_id FROM accounts WHERE external_id = %s",
                (account_external_id,),
            ).fetchone()
            if row is None:
                return None
            debtors = self._load_debtors(conn, [row[0]])
            return debtors[0] if debtors else None

    def _load_debtors(self, conn, debtor_ids) -> list[DebtorSummary]:
        if not debtor_ids:
            return []
        with conn.cursor(row_factory=dict_row) as cur:
            rows = cur.execute(_DEBTOR_WITH_ACCOUNTS_SQL, {"debtor_ids": debtor_ids}).fetchall()

        grouped: dict = {}
        for r in rows:
            entry = grouped.setdefault(r["debtor_id"], {"row": r, "accounts": []})
            if r["account_id"] is not None:
                entry["accounts"].append(_to_account(r))
        return [_to_debtor(e["row"], e["accounts"]) for e in grouped.values()]


def _to_account(r) -> AccountSummary:
    return AccountSummary(
        id=str(r["account_id"]),
        external_id=r["account_external_id"],
        creditor_name=r["creditor_name"],
        account_number_masked=r["account_number_masked"],
        current_balance_cents=r["current_balance_cents"],
        status=r["status"],
        payment_method=r["payment_method"],
        nsf_amount_cents=r["nsf_amount_cents"],
        nsf_fee_cents=r["nsf_fee_cents"],
        nsf_date=r["nsf_date"],
        nsf_return_code=r["nsf_return_code"],
        is_disputed=r["is_disputed"],
    )


def _to_debtor(r, accounts: list[AccountSummary]) -> DebtorSummary:
    return DebtorSummary(
        id=str(r["debtor_id"]),
        external_id=r["debtor_external_id"],
        first_name=r["first_name"],
        last_name=r["last_name"],
        phone_primary=r["phone_primary"],
        us_state=r["us_state"].strip() if r["us_state"] else None,
        timezone=r["timezone"],
        timezone_inferred=False,
        do_not_call=r["do_not_call"],
        accounts=tuple(accounts),
    )
