"""Implementación PostgreSQL de OutboundListRepository.

Cuando llegue la base real (y su EER), lo que cambia es la consulta de `build`.
"""

from datetime import date, datetime

from psycopg_pool import ConnectionPool

from cobranza.application.interfaces.outbound_list_repository import OutboundEntry


class PostgresOutboundListRepository:
    def __init__(self, pool: ConnectionPool):
        self._pool = pool

    def build(self, list_date: date, attempts_since: datetime, max_attempts: int,
              conversation_since: datetime) -> int:
        with self._pool.connection() as conn:
            # N9: si alguien pidió que lo llamen ese día (hora local del deudor), entra con esa hora.
            # Si lo pidió el propio deudor verificado, es su consentimiento: entra aunque haya hablado
            # hace menos de 7 días. El límite de 7 llamadas en 7 días se respeta siempre.
            cur = conn.execute(
                """WITH callbacks AS (
                       SELECT DISTINCT ON (d.id) d.id AS debtor_id, c.callback_at, c.identity_verified
                       FROM calls c
                       JOIN debtors d ON d.id = c.debtor_id
                          OR d.id = (SELECT debtor_id FROM accounts WHERE id = c.account_id)
                       WHERE c.callback_at IS NOT NULL
                         AND (c.callback_at AT TIME ZONE COALESCE(d.timezone, 'America/New_York'))::date
                             = %(list_date)s
                       ORDER BY d.id, c.started_at DESC
                   )
                   INSERT INTO outbound_call_list (list_date, account_id, debtor_id, phone, call_at)
                   SELECT %(list_date)s, a.id, d.id, d.phone_primary, cb.callback_at
                   FROM accounts a
                   JOIN debtors d ON d.id = a.debtor_id
                   LEFT JOIN callbacks cb ON cb.debtor_id = d.id
                   WHERE a.status = 'NSF'
                     AND NOT a.is_disputed
                     AND NOT d.do_not_call
                     AND d.phone_primary IS NOT NULL
                     AND NOT EXISTS (SELECT 1 FROM payment_arrangements pa
                                     WHERE pa.account_id = a.id AND pa.status = 'active')
                     AND (SELECT count(*) FROM calls c
                          WHERE c.account_id = a.id AND c.direction = 'outbound'
                            AND c.started_at >= %(attempts_since)s) < %(max_attempts)s
                     AND (cb.identity_verified IS TRUE
                          OR NOT EXISTS (SELECT 1 FROM calls c
                                         WHERE c.debtor_id = d.id AND c.identity_verified
                                           AND c.started_at >= %(conversation_since)s))
                   ON CONFLICT (list_date, account_id) DO UPDATE SET call_at = EXCLUDED.call_at,
                                                                     updated_at = now()
                       WHERE outbound_call_list.status = 'pending' AND EXCLUDED.call_at IS NOT NULL
                         AND outbound_call_list.call_at IS DISTINCT FROM EXCLUDED.call_at""",
                {"list_date": list_date, "attempts_since": attempts_since, "max_attempts": max_attempts,
                 "conversation_since": conversation_since},
            )
            return cur.rowcount

    def pending(self, list_date: date) -> list[OutboundEntry]:
        with self._pool.connection() as conn:
            rows = conn.execute(
                """SELECT o.id::text, o.list_date, o.account_id::text, a.external_id, o.debtor_id::text,
                          o.phone, o.call_at
                   FROM outbound_call_list o JOIN accounts a ON a.id = o.account_id
                   WHERE o.list_date = %s AND o.status = 'pending'
                   ORDER BY o.call_at NULLS LAST, o.created_at, a.external_id""",
                (list_date,),
            ).fetchall()
        return [OutboundEntry(*row) for row in rows]

    def remove_debtor(self, debtor_id: str, reason: str, call_id: str) -> int:
        with self._pool.connection() as conn:
            cur = conn.execute(
                """UPDATE outbound_call_list
                   SET status = 'removed', removed_reason = %s, removed_by_call_id = %s, updated_at = now()
                   WHERE debtor_id = %s AND status = 'pending'""",
                (reason, call_id, debtor_id),
            )
            return cur.rowcount

    def mark_called(self, entry_id: str, call_id: str) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                """UPDATE outbound_call_list SET status = 'called', called_call_id = %s, updated_at = now()
                   WHERE id = %s AND status = 'pending'""",
                (call_id, entry_id),
            )
