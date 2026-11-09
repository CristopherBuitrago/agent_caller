"""Implementación PostgreSQL de CallRepository."""

from datetime import datetime

from psycopg_pool import ConnectionPool

from cobranza.domain.call import CallDirection, CallOutcome, CallRecord
from cobranza.domain.identity import CallVerificationState


class PostgresCallRepository:
    def __init__(self, pool: ConnectionPool):
        self._pool = pool

    # --- ciclo de vida de la llamada ---

    def create(self, direction: CallDirection, caller_phone: str, started_at: datetime,
               debtor_id: str | None, account_id: str | None) -> str:
        with self._pool.connection() as conn:
            row = conn.execute(
                """INSERT INTO calls (direction, caller_phone, started_at, debtor_id, account_id)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                (direction.value, caller_phone, started_at, debtor_id, account_id),
            ).fetchone()
        return str(row[0])

    def get(self, call_id: str) -> CallRecord | None:
        with self._pool.connection() as conn:
            row = conn.execute(
                """SELECT id, direction, debtor_id, account_id, recording_consent, ended_at
                   FROM calls WHERE id = %s""",
                (call_id,),
            ).fetchone()
        if row is None:
            return None
        return CallRecord(
            id=str(row[0]), direction=CallDirection(row[1]),
            debtor_id=str(row[2]) if row[2] else None, account_id=str(row[3]) if row[3] else None,
            recording_consent=row[4], ended_at=row[5],
        )

    def set_recording_consent(self, call_id: str, accepted: bool) -> None:
        with self._pool.connection() as conn:
            conn.execute("UPDATE calls SET recording_consent = %s WHERE id = %s", (accepted, call_id))

    def link_account(self, call_id: str, account_id: str) -> None:
        with self._pool.connection() as conn:
            conn.execute("UPDATE calls SET account_id = %s WHERE id = %s", (account_id, call_id))

    def close(self, call_id: str, outcome: CallOutcome, summary: str | None, ended_at: datetime) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                "UPDATE calls SET outcome = %s, summary = %s, ended_at = %s WHERE id = %s",
                (outcome.value, summary, ended_at, call_id),
            )

    # --- verificación de identidad ---

    def get_verification_state(self, call_id: str) -> CallVerificationState | None:
        with self._pool.connection() as conn:
            row = conn.execute(
                "SELECT debtor_id, verification_attempts, identity_verified FROM calls WHERE id = %s",
                (call_id,),
            ).fetchone()
        if row is None:
            return None
        return CallVerificationState(
            debtor_id=str(row[0]) if row[0] else None, attempts=row[1], identity_verified=row[2],
        )

    def record_verification_attempt(self, call_id: str, debtor_id: str, succeeded: bool) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                """UPDATE calls
                   SET verification_attempts = verification_attempts + 1,
                       identity_verified = identity_verified OR %(ok)s,
                       debtor_id = %(debtor)s
                   WHERE id = %(call)s""",
                {"ok": succeeded, "debtor": debtor_id, "call": call_id},
            )

    def count_failed_verifications_since(self, debtor_id: str, since: datetime) -> int:
        with self._pool.connection() as conn:
            row = conn.execute(
                """SELECT COALESCE(SUM(verification_attempts
                                       - CASE WHEN identity_verified THEN 1 ELSE 0 END), 0)
                   FROM calls
                   WHERE debtor_id = %s AND started_at >= %s""",
                (debtor_id, since),
            ).fetchone()
        return int(row[0])
