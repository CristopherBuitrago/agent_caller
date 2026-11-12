"""Consultas sobre los acuerdos que usan otros módulos (por ejemplo, la mensajería de N1)."""

from datetime import date, datetime

from cobranza.application.interfaces.payment_schedule import (
    ArrangementView,
    PaymentDue,
    PaymentScheduleReader,
)


class ListNewArrangements:
    """Acuerdos activos creados desde `since`, con sus pagos y el teléfono del deudor."""

    def __init__(self, reader: PaymentScheduleReader):
        self._reader = reader

    def execute(self, since: datetime) -> list[ArrangementView]:
        return self._reader.active_arrangements_created_since(since)


class ListPaymentsDue:
    """Cuotas pendientes de acuerdos activos que vencen hasta `as_of` (incluido)."""

    def __init__(self, reader: PaymentScheduleReader):
        self._reader = reader

    def execute(self, as_of: date) -> list[PaymentDue]:
        return self._reader.pending_payments_due(as_of)


class ListPaymentsDueOn:
    """Cuotas pendientes de acuerdos activos que vencen exactamente en `day` (N10: aviso previo)."""

    def __init__(self, reader: PaymentScheduleReader):
        self._reader = reader

    def execute(self, day: date) -> list[PaymentDue]:
        return self._reader.pending_payments_due_on(day)
