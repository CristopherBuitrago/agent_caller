"""Lista diaria de llamadas salientes (decisión del jefe, 2026-11-12).

Cada día se consulta la base para saber a quién llamar. Si un deudor de la lista llama antes
por su cuenta y verifica su identidad, se le saca (lo hace VerifyIdentity).
"""

from datetime import date, timedelta

from cobranza.application.interfaces.clock import Clock
from cobranza.application.interfaces.outbound_list_repository import OutboundEntry, OutboundListRepository

# Reg F: más de 7 intentos de llamada en 7 días por una deuda se presume acoso, y después de
# una conversación con el deudor no se le llama por 7 días. Solo se cuentan las llamadas de
# esta base; las de los cobradores se sumarán cuando se conozca la base real.
MAX_CALL_ATTEMPTS = 7
ATTEMPTS_WINDOW = timedelta(days=7)
AFTER_CONVERSATION = timedelta(days=7)

REMOVED_BY_INBOUND_CALL = "inbound_call"


class BuildDailyOutboundList:
    def __init__(self, outbound: OutboundListRepository, clock: Clock):
        self._outbound = outbound
        self._clock = clock

    def execute(self, list_date: date) -> int:
        """Devuelve cuántas cuentas agregó. Se puede correr varias veces: no repite cuentas."""
        now = self._clock.now()
        return self._outbound.build(list_date, now - ATTEMPTS_WINDOW, MAX_CALL_ATTEMPTS,
                                    now - AFTER_CONVERSATION)


class GetOutboundCalls:
    """Las cuentas pendientes de llamar en la lista del día (las usa quien marca)."""

    def __init__(self, outbound: OutboundListRepository):
        self._outbound = outbound

    def execute(self, list_date: date) -> list[OutboundEntry]:
        return self._outbound.pending(list_date)


class MarkOutboundCalled:
    def __init__(self, outbound: OutboundListRepository):
        self._outbound = outbound

    def execute(self, entry_id: str, call_id: str) -> None:
        self._outbound.mark_called(entry_id, call_id)
