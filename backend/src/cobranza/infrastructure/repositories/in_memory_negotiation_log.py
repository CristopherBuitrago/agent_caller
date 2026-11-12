"""Registro de ofertas en memoria.

Basta mientras cada llamada viva en un solo proceso del servidor. Si se necesita auditar
las ofertas después de la llamada, se cambia por una tabla (requiere aprobar el modelo).
"""

import threading
import uuid
from dataclasses import replace

from cobranza.application.interfaces.negotiation_log import LoggedProposal
from cobranza.domain.arrangement import ArrangementProposal


class InMemoryNegotiationLog:
    def __init__(self):
        self._by_call: dict[str, dict[str, LoggedProposal]] = {}
        self._lock = threading.Lock()

    def save(self, call_id: str, account_external_id: str, offer_number: int | None,
             proposal: ArrangementProposal) -> LoggedProposal:
        return self._store(LoggedProposal(f"P{uuid.uuid4().hex[:8]}", call_id, account_external_id,
                                          offer_number, proposal))

    def save_skipped(self, call_id: str, account_external_id: str, offer_number: int,
                     proposal: ArrangementProposal, reason: str) -> LoggedProposal:
        return self._store(LoggedProposal(f"S{uuid.uuid4().hex[:8]}", call_id, account_external_id,
                                          offer_number, proposal, rejected=True, skip_reason=reason))

    def _store(self, logged: LoggedProposal) -> LoggedProposal:
        with self._lock:
            self._by_call.setdefault(logged.call_id, {})[logged.id] = logged
        return logged

    def get(self, call_id: str, proposal_id: str) -> LoggedProposal | None:
        with self._lock:
            return self._by_call.get(call_id, {}).get(proposal_id)

    def mark_rejected(self, call_id: str, proposal_id: str) -> None:
        with self._lock:
            proposals = self._by_call.get(call_id, {})
            if proposal_id in proposals:
                proposals[proposal_id] = replace(proposals[proposal_id], rejected=True)

    def rejected_offer_numbers(self, call_id: str, account_external_id: str) -> set[int]:
        with self._lock:
            return {
                p.offer_number for p in self._by_call.get(call_id, {}).values()
                if p.rejected and p.offer_number is not None
                and p.account_external_id == account_external_id
            }
