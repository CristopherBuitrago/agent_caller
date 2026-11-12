"""Implementación PostgreSQL de SmsRepository (tabla sms_messages, propia de la mensajería)."""

from datetime import datetime

from psycopg_pool import ConnectionPool

from cobranza.messaging.application.ports import SmsKind

# Cada tipo de mensaje tiene su propio índice único parcial (ver 001_schema.sql).
_CONFLICT_TARGET = {
    SmsKind.ARRANGEMENT_CONFIRMATION: "(arrangement_id) WHERE kind = 'arrangement_confirmation'",
    SmsKind.PAYMENT_LINK: "(scheduled_payment_id) WHERE kind = 'payment_link'",
    SmsKind.PAYMENT_REMINDER: "(scheduled_payment_id) WHERE kind = 'payment_reminder'",
}


class PostgresSmsRepository:
    def __init__(self, pool: ConnectionPool):
        self._pool = pool

    def claim(self, kind: SmsKind, debtor_id: str, arrangement_id: str,
              scheduled_payment_id: str | None, to_phone: str, body: str) -> str | None:
        # Si ya existe: solo se vuelve a reservar si falló (reintento). Enviado o en curso -> None.
        with self._pool.connection() as conn:
            row = conn.execute(
                f"""INSERT INTO sms_messages AS s
                        (debtor_id, arrangement_id, scheduled_payment_id, kind, to_phone, body)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT {_CONFLICT_TARGET[kind]} DO UPDATE
                        SET status = 'pending', error = NULL, to_phone = EXCLUDED.to_phone,
                            body = EXCLUDED.body
                        WHERE s.status = 'failed'
                    RETURNING id::text""",
                (debtor_id, arrangement_id, scheduled_payment_id, kind.value, to_phone, body),
            ).fetchone()
        return row[0] if row else None

    def mark_sent(self, sms_id: str, provider_message_id: str, sent_at: datetime) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                """UPDATE sms_messages SET status = 'sent', provider_message_id = %s, sent_at = %s
                   WHERE id = %s""",
                (provider_message_id, sent_at, sms_id),
            )

    def mark_failed(self, sms_id: str, error: str) -> None:
        with self._pool.connection() as conn:
            conn.execute("UPDATE sms_messages SET status = 'failed', error = %s WHERE id = %s",
                         (error[:500], sms_id))
