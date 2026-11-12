from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True)
class ScheduledPaymentView:
    id: str
    sequence: int
    amount_cents: int
    due_date: date
    status: str  # pending | paid | failed | cancelled


@dataclass(frozen=True)
class ArrangementView:
    """Un acuerdo con sus pagos y el teléfono del deudor, para avisarle por SMS."""
    id: str
    debtor_id: str
    phone: str | None
    created_at: datetime
    payments: tuple[ScheduledPaymentView, ...]


@dataclass(frozen=True)
class PaymentDue:
    """Una cuota pendiente de un acuerdo activo cuya fecha ya llegó."""
    scheduled_payment_id: str
    arrangement_id: str
    debtor_id: str
    phone: str | None
    sequence: int
    amount_cents: int
    due_date: date


class PaymentScheduleReader(Protocol):
    """Consultas de solo lectura sobre los acuerdos.

    Implementación: infrastructure/repositories/postgres_payment_schedule_reader.py
    """

    def active_arrangements_created_since(self, since: datetime) -> list[ArrangementView]: ...

    def pending_payments_due(self, as_of: date) -> list[PaymentDue]:
        """Cuotas `pending` de acuerdos `active` con `due_date <= as_of`."""
        ...

    def pending_payments_due_on(self, day: date) -> list[PaymentDue]:
        """Cuotas `pending` de acuerdos `active` que vencen exactamente `day` (para avisar antes)."""
        ...
