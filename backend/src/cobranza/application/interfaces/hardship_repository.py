from datetime import datetime
from typing import Protocol

from cobranza.domain.hardship import HardshipAnswers


class HardshipRepository(Protocol):
    """Interfaz. Implementación: infrastructure/repositories/postgres_hardship_repository.py"""

    def save(self, call_id: str, debtor_id: str, answers: HardshipAnswers) -> None:
        """Guarda las respuestas de la llamada; cada vez completa las anteriores (E2)."""
        ...

    def exists_for_debtor_since(self, debtor_id: str, since: datetime) -> bool:
        """B1: el deudor contestó las Hardship Questions desde `since` (en esta u otra llamada)."""
        ...
