from dataclasses import dataclass
from typing import Protocol

from cobranza.domain.arrangement import ArrangementProposal


@dataclass(frozen=True)
class LoggedProposal:
    """Una propuesta que el agente le presentó al deudor en la llamada."""
    id: str
    call_id: str
    account_external_id: str
    offer_number: int | None  # 1 = todo de una, 2 = 2 cuotas...; None = pago parcial
    proposal: ArrangementProposal
    rejected: bool = False


class NegotiationLog(Protocol):
    """Lo que se le ofreció al deudor en cada llamada y qué rechazó.

    Con esto el sistema sabe solo si ya se rechazaron todas las ofertas; la IA no lo decide.
    Implementación: infrastructure/repositories/in_memory_negotiation_log.py
    """

    def save(self, call_id: str, account_external_id: str, offer_number: int | None,
             proposal: ArrangementProposal) -> LoggedProposal: ...

    def get(self, call_id: str, proposal_id: str) -> LoggedProposal | None: ...

    def mark_rejected(self, call_id: str, proposal_id: str) -> None: ...

    def rejected_offer_numbers(self, call_id: str, account_external_id: str) -> set[int]:
        """Números de oferta de cuotas rechazados en esta llamada para esta cuenta."""
        ...
