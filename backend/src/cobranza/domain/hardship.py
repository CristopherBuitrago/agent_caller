"""Hardship Questions: se hacen tras rechazar 3 cuotas, para saber qué plan ofrecer después."""

from dataclasses import dataclass
from enum import Enum

# Lista entregada por el jefe; traducción al inglés aprobada el 2026-11-08.
# Si hace falta preguntar algo más, se sigue el tono de estas preguntas. Nunca se
# sugiere vender bienes ni pedir dinero prestado, porque puede verse como presión.
HARDSHIP_QUESTIONS = (
    "Can you tell me a little about what happened and when this situation started?",
    "Do you expect this to be temporary, or a longer-term change in your income?",
    "Is there anyone else in your household who could help out while things stabilize?",
    "I understand things are difficult. Is there a partial amount you could put toward this "
    "today or on your next pay date?",
    "What realistic arrangement could we set for the next 30 or 60 days that you could keep up "
    "with comfortably?",
)


class HardshipDuration(Enum):
    TEMPORARY = "temporary"
    LONG_TERM = "long_term"


@dataclass(frozen=True)
class HardshipAnswers:
    situation_description: str | None = None
    situation_started: str | None = None  # en palabras del deudor, p. ej. "last month"
    duration_type: HardshipDuration | None = None
    household_support: bool | None = None
    offered_amount_cents: int | None = None
    notes: str | None = None
    recommended_plan: str | None = None  # lo que el agente termina ofreciendo
    arrangement_answer: str | None = None  # respuesta a la pregunta 5, en palabras del deudor


# Hallazgo 3 de las simulaciones con Haiku (2026-11-18): las preguntas se hacen en orden, una por una,
# y el sistema lleva la cuenta. Las ofertas que exigen Hardship Questions esperan las 5.
HARDSHIP_QUESTION_COUNT = len(HARDSHIP_QUESTIONS)


class HardshipAnswerError(ValueError):
    """La respuesta no corresponde a la pregunta que toca o le falta el dato de esa pregunta."""


def check_hardship_answer(question_number: int, answered_before: int, answers: HardshipAnswers) -> None:
    """Revisa que la respuesta sea de una pregunta ya hecha o de la siguiente, y que traiga su dato.

    Las preguntas 2 y 4 pueden quedar sin dato: la duración puede no estar clara (P10) y el deudor
    puede no ofrecer ningún monto.
    """
    if not 1 <= question_number <= HARDSHIP_QUESTION_COUNT:
        raise HardshipAnswerError(f"question_number must be between 1 and {HARDSHIP_QUESTION_COUNT}")
    if question_number > answered_before + 1:
        raise HardshipAnswerError(f"Ask question {answered_before + 1} first")
    missing = {
        1: not (answers.situation_description or "").strip(),
        3: answers.household_support is None,
        5: not (answers.arrangement_answer or "").strip(),
    }.get(question_number, False)
    if missing:
        field = {1: "situation_description", 3: "household_support", 5: "arrangement_answer"}[question_number]
        raise HardshipAnswerError(f"Question {question_number} needs {field}")
