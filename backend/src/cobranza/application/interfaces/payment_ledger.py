from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True)
class RecordedPayment:
    arrangement_id: str
    arrangement_completed: bool  # se pagaron todas las cuotas


class PaymentLedger(Protocol):
    """Resultados de pago y estado de los acuerdos (N10).

    Implementación: infrastructure/repositories/postgres_payment_ledger.py
    """

    def record_result(self, scheduled_payment_id: str, reference: str, amount_cents: int,
                      status: str, processed_at: datetime) -> RecordedPayment | None:
        """Guarda el resultado en una transacción. Si es `approved`, la cuota queda pagada y, si ya
        no quedan cuotas pendientes, el acuerdo pasa a `completed`.

        Devuelve None si esa referencia ya se había registrado (el procesador puede avisar dos veces).
        Lanza ValueError si la cuota no existe.
        """
        ...

    def break_overdue(self, due_on_or_before: date, account_status: str) -> list[str]:
        """Rompe los acuerdos activos con alguna cuota pendiente que vencía hasta esa fecha.

        En una transacción: acuerdo `broken`, sus cuotas pendientes `cancelled` y la cuenta al
        estado dado. Devuelve los ids de los acuerdos rotos.
        """
        ...
