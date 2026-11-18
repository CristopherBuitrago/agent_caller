"""Implementación PostgreSQL de HardshipRepository."""

from datetime import datetime

from psycopg_pool import ConnectionPool

from cobranza.domain.hardship import HARDSHIP_QUESTION_COUNT, HardshipAnswers


class PostgresHardshipRepository:
    def __init__(self, pool: ConnectionPool):
        self._pool = pool

    def save(self, call_id: str, debtor_id: str, answers: HardshipAnswers, questions_answered: int) -> None:
        """Se puede llamar varias veces en la llamada: cada vez completa las respuestas.

        Un campo vacío no borra lo que ya estaba guardado (el agente guarda de a una respuesta), y la
        cuenta de preguntas respondidas nunca baja.
        """
        duration = answers.duration_type.value if answers.duration_type else None
        with self._pool.connection() as conn:
            conn.execute(
                """INSERT INTO hardship_assessments AS h
                       (call_id, debtor_id, situation_description, situation_started, duration_type,
                        household_support, offered_amount_cents, notes, recommended_plan,
                        arrangement_answer, questions_answered)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (call_id) DO UPDATE SET
                       situation_description = COALESCE(EXCLUDED.situation_description, h.situation_description),
                       situation_started = COALESCE(EXCLUDED.situation_started, h.situation_started),
                       duration_type = COALESCE(EXCLUDED.duration_type, h.duration_type),
                       household_support = COALESCE(EXCLUDED.household_support, h.household_support),
                       offered_amount_cents = COALESCE(EXCLUDED.offered_amount_cents, h.offered_amount_cents),
                       notes = COALESCE(EXCLUDED.notes, h.notes),
                       recommended_plan = COALESCE(EXCLUDED.recommended_plan, h.recommended_plan),
                       arrangement_answer = COALESCE(EXCLUDED.arrangement_answer, h.arrangement_answer),
                       questions_answered = GREATEST(EXCLUDED.questions_answered, h.questions_answered)""",
                (call_id, debtor_id, answers.situation_description, answers.situation_started, duration,
                 answers.household_support, answers.offered_amount_cents, answers.notes,
                 answers.recommended_plan, answers.arrangement_answer, questions_answered),
            )

    def questions_answered(self, call_id: str) -> int:
        with self._pool.connection() as conn:
            row = conn.execute("SELECT questions_answered FROM hardship_assessments WHERE call_id = %s",
                               (call_id,)).fetchone()
        return row[0] if row else 0

    def set_recommended_plan(self, debtor_id: str, since: datetime, plan: str) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                """UPDATE hardship_assessments SET recommended_plan = %s
                   WHERE id = (SELECT id FROM hardship_assessments
                               WHERE debtor_id = %s AND created_at >= %s AND questions_answered = %s
                               ORDER BY created_at DESC LIMIT 1)""",
                (plan, debtor_id, since, HARDSHIP_QUESTION_COUNT),
            )

    def exists_for_debtor_since(self, debtor_id: str, since: datetime) -> bool:
        with self._pool.connection() as conn:
            row = conn.execute(
                """SELECT 1 FROM hardship_assessments
                   WHERE debtor_id = %s AND created_at >= %s AND questions_answered = %s LIMIT 1""",
                (debtor_id, since, HARDSHIP_QUESTION_COUNT),
            ).fetchone()
        return row is not None
