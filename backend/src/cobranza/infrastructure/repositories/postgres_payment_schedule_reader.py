"""Implementación PostgreSQL de PaymentScheduleReader."""

from datetime import date, datetime

from psycopg_pool import ConnectionPool

from cobranza.application.interfaces.payment_schedule import (
    ArrangementView,
    PaymentDue,
    ScheduledPaymentView,
)


class PostgresPaymentScheduleReader:
    def __init__(self, pool: ConnectionPool):
        self._pool = pool

    def active_arrangements_created_since(self, since: datetime) -> list[ArrangementView]:
        with self._pool.connection() as conn:
            arrangements = conn.execute(
                """SELECT pa.id::text, a.debtor_id::text, d.phone_primary, pa.created_at
                   FROM payment_arrangements pa
                   JOIN accounts a ON a.id = pa.account_id
                   JOIN debtors d ON d.id = a.debtor_id
                   WHERE pa.status = 'active' AND pa.created_at >= %s
                   ORDER BY pa.created_at""",
                (since,),
            ).fetchall()
            payments = conn.execute(
                """SELECT arrangement_id::text, id::text, sequence, amount_cents, due_date, status
                   FROM scheduled_payments
                   WHERE arrangement_id = ANY(%s::uuid[])
                   ORDER BY arrangement_id, sequence""",
                ([row[0] for row in arrangements],),
            ).fetchall()
        by_arrangement: dict[str, list[ScheduledPaymentView]] = {}
        for arrangement_id, *payment in payments:
            by_arrangement.setdefault(arrangement_id, []).append(ScheduledPaymentView(*payment))
        return [
            ArrangementView(arrangement_id, debtor_id, phone, created_at,
                            tuple(by_arrangement.get(arrangement_id, ())))
            for arrangement_id, debtor_id, phone, created_at in arrangements
        ]

    def pending_payments_due(self, as_of: date) -> list[PaymentDue]:
        return self._pending("sp.due_date <= %s", as_of)

    def pending_payments_due_on(self, day: date) -> list[PaymentDue]:
        return self._pending("sp.due_date = %s", day)

    def _pending(self, due_condition: str, day: date) -> list[PaymentDue]:
        with self._pool.connection() as conn:
            rows = conn.execute(
                f"""SELECT sp.id::text, pa.id::text, a.debtor_id::text, d.phone_primary,
                           sp.sequence, sp.amount_cents, sp.due_date
                    FROM scheduled_payments sp
                    JOIN payment_arrangements pa ON pa.id = sp.arrangement_id
                    JOIN accounts a ON a.id = pa.account_id
                    JOIN debtors d ON d.id = a.debtor_id
                    WHERE sp.status = 'pending' AND pa.status = 'active' AND {due_condition}
                    ORDER BY sp.due_date, pa.id, sp.sequence""",
                (day,),
            ).fetchall()
        return [PaymentDue(*row) for row in rows]
