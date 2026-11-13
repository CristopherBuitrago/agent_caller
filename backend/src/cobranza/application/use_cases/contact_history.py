"""N13: la última llamada de la empresa al deudor, para responder con datos reales cuando se queja
de que lo llaman mucho (respuesta del jefe, 2026-11-12). El dato sale del sistema, nunca se inventa.

Solo cuenta las llamadas de esta base; las de los cobradores se sumarán con la base real.
"""

from cobranza.application.interfaces.call_repository import CallRepository
from cobranza.domain.call import LastContact


class GetLastContact:
    def __init__(self, calls: CallRepository):
        self._calls = calls

    def execute(self, debtor_id: str, current_call_id: str) -> LastContact | None:
        return self._calls.last_outbound_call(debtor_id, current_call_id)
