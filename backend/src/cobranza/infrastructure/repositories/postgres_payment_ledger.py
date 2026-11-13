"""Implementación PostgreSQL de PaymentLedger (tablas payment_results, scheduled_payments,
payment_arrangements y accounts)."""

from datetime import date, datetime

from psycopg_pool import ConnectionPool

from cobranza.application.interfaces.payment_ledger import RecordedPayment


class PostgresPaymentLedger:
    def __init__(self, pool: ConnectionPool):
        self._pool = pool

    def record_result(self, scheduled_payment_id: str, reference: str, amount_cents: int,
                      status: str, processed_at: datetime) -> RecordedPayment | None:
        # Todo en una transacción: el resultado, la cuota y el acuerdo.
        with self._pool.connection() as conn:
            payment = conn.execute(
                "SELECT arrangement_id::text FROM scheduled_payments WHERE id = %s",
                (scheduled_payment_id,),
            ).fetchone()
            if payment is None:
                raise ValueError(f"Cuota desconocida: {scheduled_payment_id}")
            arrangement_id = payment[0]
            # ivr_reference guarda la referencia del procesador (IVR o página de pago).
            inserted = conn.execute(
                """INSERT INTO payment_results
                       (arrangement_id, scheduled_payment_id, ivr_reference, amount_cents, status, processed_at)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (ivr_reference) DO NOTHING
                   RETURNING id""",
                (arrangement_id, scheduled_payment_id, reference, amount_cents, status, processed_at),
            ).fetchone()
            if inserted is None:
                return None
            completed = False
            if status == "approved":
                conn.execute(
                    """UPDATE scheduled_payments SET status = 'paid', paid_at = %s
                       WHERE id = %s AND status IN ('pending', 'failed')""",
                    (processed_at, scheduled_payment_id),
                )
                completed = conn.execute(
                    """UPDATE payment_arrangements SET status = 'completed'
                       WHERE id = %s AND status = 'active'
                         AND NOT EXISTS (SELECT 1 FROM scheduled_payments
                                         WHERE arrangement_id = %s AND status <> 'paid')
                       RETURNING id""",
                    (arrangement_id, arrangement_id),
                ).fetchone() is not None
        return RecordedPayment(arrangement_id, completed)

    def break_overdue(self, due_on_or_before: date, account_status: str) -> list[str]:
        with self._pool.connection() as conn:
            broken = conn.execute(
                """UPDATE payment_arrangements pa SET status = 'broken'
                   WHERE pa.status = 'active'
                     AND EXISTS (SELECT 1 FROM scheduled_payments sp
                                 WHERE sp.arrangement_id = pa.id AND sp.status = 'pending'
                                   AND sp.due_date <= %s)
                   RETURNING pa.id, pa.account_id""",
                (due_on_or_before,),
            ).fetchall()
            ids = [row[0] for row in broken]
            if ids:
                conn.execute(
                    """UPDATE scheduled_payments SET status = 'cancelled'
                       WHERE arrangement_id = ANY(%s) AND status = 'pending'""",
                    (ids,),
                )
                conn.execute(
                    """UPDATE accounts SET status = %s, status_updated_at = now()
                       WHERE id = ANY(%s)""",
                    (account_status, [row[1] for row in broken]),
                )
        return [str(i) for i in ids]
