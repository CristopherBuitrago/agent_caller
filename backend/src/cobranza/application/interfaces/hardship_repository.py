from datetime import datetime
from typing import Protocol

from cobranza.domain.hardship import HardshipAnswers


class HardshipRepository(Protocol):
    """Interfaz. Implementación: infrastructure/repositories/postgres_hardship_repository.py"""

    def save(self, call_id: str, debtor_id: str, answers: HardshipAnswers, questions_answered: int) -> None:
        """Guarda las respuestas de la llamada; cada vez completa las anteriores (E2).

        `questions_answered`: hasta qué pregunta se respondió (hallazgo 3). Nunca baja.
        """
        ...

    def questions_answered(self, call_id: str) -> int:
        """Cuántas Hardship Questions se respondieron en esta llamada (0 si ninguna)."""
        ...

    def set_recommended_plan(self, debtor_id: str, since: datetime, plan: str) -> None:
        """B14: guarda el acuerdo en las Hardship Questions más recientes del deudor desde `since`.

        Si no contestó ninguna en ese tiempo, no hace nada.
        """
        ...

    def exists_for_debtor_since(self, debtor_id: str, since: datetime) -> bool:
        """B1: el deudor contestó las 5 Hardship Questions desde `since` (en esta u otra llamada).

        Las que quedaron a medias no cuentan (hallazgo 3).
        """
        ...
