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
