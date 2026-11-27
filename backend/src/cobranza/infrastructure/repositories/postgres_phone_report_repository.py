"""Implementación PostgreSQL de PhoneReportRepository (tabla phone_reports)."""

from datetime import datetime

from psycopg_pool import ConnectionPool


class PostgresPhoneReportRepository:
    def __init__(self, pool: ConnectionPool):
        self._pool = pool

    def add(self, phone: str, call_id: str, reported_at: datetime) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                "INSERT INTO phone_reports (phone, call_id, reported_at) VALUES (%s, %s, %s)",
                (phone, call_id, reported_at),
            )
