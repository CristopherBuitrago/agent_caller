"""N10: resultados de pago y acuerdos rotos (decisión del jefe, 2026-11-12).

- Cada pago que avisa el procesador se registra; si se pagan todas las cuotas, el acuerdo se completa.
- Si 5 días después de su fecha una cuota sigue sin pagar, el acuerdo queda roto y la cuenta vuelve
  a NSF, con lo que entra de nuevo a la lista diaria de salientes. Sin alerta: la empresa revisa los
  acuerdos rotos con sus reportes semanales y mensuales.
"""

from datetime import date, datetime, timedelta

from cobranza.application.interfaces.payment_ledger import PaymentLedger, RecordedPayment

PAYMENT_RESULT_STATUSES = frozenset({"approved", "declined", "error"})
DAYS_OF_GRACE = 5
ACCOUNT_STATUS_AFTER_BROKEN = "NSF"


class RecordPaymentResult:
    """Lo usa el aviso del procesador de pagos (webhook) cuando se conecte."""

    def __init__(self, ledger: PaymentLedger):
        self._ledger = ledger

    def execute(self, scheduled_payment_id: str, reference: str, amount_cents: int, status: str,
                processed_at: datetime) -> RecordedPayment | None:
        if status not in PAYMENT_RESULT_STATUSES:
            raise ValueError(f"Estado de pago desconocido: {status}")
        if amount_cents <= 0 or not reference.strip():
            raise ValueError("El pago necesita un monto positivo y una referencia")
        return self._ledger.record_result(scheduled_payment_id, reference.strip(), amount_cents, status,
                                          processed_at)


class BreakOverdueArrangements:
    """Rompe los acuerdos con una cuota sin pagar 5 días después de su fecha. Devuelve sus ids."""

    def __init__(self, ledger: PaymentLedger):
        self._ledger = ledger

    def execute(self, as_of: date) -> list[str]:
        return self._ledger.break_overdue(as_of - timedelta(days=DAYS_OF_GRACE), ACCOUNT_STATUS_AFTER_BROKEN)
