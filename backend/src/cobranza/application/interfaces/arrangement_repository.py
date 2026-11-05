from typing import Protocol

from cobranza.domain.arrangement import ArrangementProposal


class ArrangementRepository(Protocol):
    """Interfaz. Implementación: infrastructure/repositories/postgres_arrangement_repository.py"""

    def has_active_arrangement(self, account_id: str) -> bool: ...

    def create(self, call_id: str, account_id: str, proposal: ArrangementProposal,
               new_account_status: str) -> str:
        """Guarda el acuerdo y sus pagos y cambia el estado de la cuenta, todo en una transacción.

        Devuelve el id del acuerdo. Lanza ArrangementRuleError(ACTIVE_ARRANGEMENT_EXISTS) si la
        cuenta ya tiene uno activo.
        """
        ...
