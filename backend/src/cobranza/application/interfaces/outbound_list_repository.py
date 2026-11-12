from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True)
class OutboundEntry:
    """Una cuenta a llamar en la lista del día."""
    id: str
    list_date: date
    account_id: str
    account_external_id: str
    debtor_id: str
    phone: str


class OutboundListRepository(Protocol):
    """Lista diaria de llamadas salientes.

    Implementación: infrastructure/repositories/postgres_outbound_list_repository.py
    """

    def build(self, list_date: date, attempts_since: datetime, max_attempts: int,
              conversation_since: datetime) -> int:
        """Agrega a la lista del día las cuentas que se pueden llamar y devuelve cuántas agregó.

        Criterios (sobre la base de prueba hasta conocer la base real): cuenta en NSF, sin disputa,
        deudor sin "no llamar", sin acuerdo activo, con teléfono, con menos de `max_attempts`
        llamadas salientes desde `attempts_since` y sin una conversación (identidad verificada)
        desde `conversation_since`. Una cuenta que ya está en la lista del día no se repite.
        """
        ...

    def pending(self, list_date: date) -> list[OutboundEntry]: ...

    def remove_debtor(self, debtor_id: str, reason: str, call_id: str) -> int:
        """Saca de la lista todas las cuentas pendientes del deudor. Devuelve cuántas sacó."""
        ...

    def mark_called(self, entry_id: str, call_id: str) -> None: ...
