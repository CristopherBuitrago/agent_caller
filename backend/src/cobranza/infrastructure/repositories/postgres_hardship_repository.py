"""Implementación PostgreSQL de HardshipRepository."""

from psycopg_pool import ConnectionPool

from cobranza.domain.hardship import HardshipAnswers


class PostgresHardshipRepository:
    def __init__(self, pool: ConnectionPool):
        self._pool = pool

    def save(self, call_id: str, debtor_id: str, answers: HardshipAnswers) -> None:
        duration = answers.duration_type.value if answers.duration_type else None
        with self._pool.connection() as conn:
            conn.execute(
                """INSERT INTO hardship_assessments
                       (call_id, debtor_id, situation_description, situation_started, duration_type,
                        household_support, offered_amount_cents, notes, recommended_plan)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (call_id) DO UPDATE SET
                       situation_description = EXCLUDED.situation_description,
                       situation_started = EXCLUDED.situation_started,
                       duration_type = EXCLUDED.duration_type,
                       household_support = EXCLUDED.household_support,
                       offered_amount_cents = EXCLUDED.offered_amount_cents,
                       notes = EXCLUDED.notes,
                       recommended_plan = EXCLUDED.recommended_plan""",
                (call_id, debtor_id, answers.situation_description, answers.situation_started, duration,
                 answers.household_support, answers.offered_amount_cents, answers.notes,
                 answers.recommended_plan),
            )

    def exists_for_call(self, call_id: str) -> bool:
        with self._pool.connection() as conn:
            row = conn.execute("SELECT 1 FROM hardship_assessments WHERE call_id = %s", (call_id,)).fetchone()
        return row is not None
