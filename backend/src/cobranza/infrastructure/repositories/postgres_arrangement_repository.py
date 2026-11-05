"""Implementación PostgreSQL de ArrangementRepository."""

import psycopg
from psycopg_pool import ConnectionPool

from cobranza.domain.arrangement import ArrangementProposal, ArrangementRuleError, RuleViolation


class PostgresArrangementRepository:
    def __init__(self, pool: ConnectionPool):
        self._pool = pool

    def has_active_arrangement(self, account_id: str) -> bool:
        with self._pool.connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM payment_arrangements WHERE account_id = %s AND status = 'active'",
                (account_id,),
            ).fetchone()
        return row is not None

    def create(self, call_id: str, account_id: str, proposal: ArrangementProposal,
               new_account_status: str) -> str:
        # El bloque es una transacción: se guarda todo (acuerdo, pagos y estado) o nada.
        try:
            with self._pool.connection() as conn:
                row = conn.execute(
                    """INSERT INTO payment_arrangements (call_id, account_id, type, total_amount_cents)
                       VALUES (%s, %s, %s, %s) RETURNING id""",
                    (call_id, account_id, proposal.type.value, proposal.total_amount_cents),
                ).fetchone()
                with conn.cursor() as cur:
                    cur.executemany(
                        """INSERT INTO scheduled_payments (arrangement_id, sequence, amount_cents, due_date)
                           VALUES (%s, %s, %s, %s)""",
                        [(row[0], p.sequence, p.amount_cents, p.due_date) for p in proposal.payments],
                    )
                conn.execute(
                    "UPDATE accounts SET status = %s, status_updated_at = now() WHERE id = %s",
                    (new_account_status, account_id),
                )
        except psycopg.errors.UniqueViolation as e:
            raise ArrangementRuleError(RuleViolation.ACTIVE_ARRANGEMENT_EXISTS) from e
        return str(row[0])
