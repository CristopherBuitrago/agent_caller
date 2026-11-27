from datetime import datetime
from typing import Protocol


class PhoneReportRepository(Protocol):
    """Interfaz. Implementación: infrastructure/repositories/postgres_phone_report_repository.py"""

    def add(self, phone: str, call_id: str, reported_at: datetime) -> None:
        """Guarda que en esta llamada alguien dijo que el teléfono no es del deudor."""
        ...
