"""Decisión 5 de las pruebas de voz (2026-11-24): número equivocado.

Si quien contesta (o llama) dice que el teléfono no es del deudor y no logra verificarse, el número
queda reportado. Mientras un cobrador no lo revise, no recibe SMS ni entra a la lista diaria.
"""

from cobranza.application.interfaces.clock import Clock
from cobranza.application.interfaces.phone_report_repository import PhoneReportRepository
from cobranza.application.interfaces.phone_service import PhoneService


class ReportWrongNumber:
    def __init__(self, reports: PhoneReportRepository, phones: PhoneService, clock: Clock):
        self._reports = reports
        self._phones = phones
        self._clock = clock

    def execute(self, call_id: str, phone: str) -> None:
        self._reports.add(self._phones.normalize(phone) or phone, call_id, self._clock.now())
