"""Implementación PostgreSQL de IdentityRepository."""

from psycopg_pool import ConnectionPool

from cobranza.domain.identity import IdentityRecord


class PostgresIdentityRepository:
    """Único lugar que lee dob_hmac y ssn_last4_hmac."""

    def __init__(self, pool: ConnectionPool):
        self._pool = pool

    def get_identity(self, debtor_id: str) -> IdentityRecord | None:
        with self._pool.connection() as conn:
            row = conn.execute(
                "SELECT id, first_name, last_name, dob_hmac, ssn_last4_hmac FROM debtors WHERE id = %s",
                (debtor_id,),
            ).fetchone()
        if row is None:
            return None
        return IdentityRecord(
            debtor_id=str(row[0]), first_name=row[1], last_name=row[2],
            dob_hash=bytes(row[3]), ssn_last4_hash=bytes(row[4]),
        )
