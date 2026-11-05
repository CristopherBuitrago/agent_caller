from typing import Protocol

from cobranza.domain.hardship import HardshipAnswers


class HardshipRepository(Protocol):
    """Interfaz. Implementación: infrastructure/repositories/postgres_hardship_repository.py"""

    def save(self, call_id: str, debtor_id: str, answers: HardshipAnswers) -> None:
        """Guarda las respuestas de la llamada; si ya existen, las reemplaza."""
        ...

    def exists_for_call(self, call_id: str) -> bool: ...
