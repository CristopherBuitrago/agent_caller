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
    # Si el sistema la saltó sin presentarla (N4), el motivo. Cuenta como rechazada.
    skip_reason: str | None = None


class NegotiationLog(Protocol):
    """Lo que se le ofreció al deudor en cada llamada y qué rechazó.

    Con esto el sistema sabe solo si ya se rechazaron todas las ofertas; la IA no lo decide.
    Implementación: infrastructure/repositories/in_memory_negotiation_log.py
    """

    def save(self, call_id: str, account_external_id: str, offer_number: int | None,
             proposal: ArrangementProposal) -> LoggedProposal: ...

    def save_skipped(self, call_id: str, account_external_id: str, offer_number: int,
                     proposal: ArrangementProposal, reason: str) -> LoggedProposal:
        """Oferta que no se presentó porque supera lo que el deudor dijo poder pagar (N4)."""
        ...

    def get(self, call_id: str, proposal_id: str) -> LoggedProposal | None: ...

    def mark_rejected(self, call_id: str, proposal_id: str) -> None: ...

    def rejected_offer_numbers(self, call_id: str, account_external_id: str) -> set[int]:
        """Números de oferta de cuotas rechazados en esta llamada para esta cuenta."""
        ...
