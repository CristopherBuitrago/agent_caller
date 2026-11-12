"""Implementaciones de desarrollo mientras no se conecten el proveedor de SMS ni el procesador de pagos.

- Proveedor de SMS: la empresa ya tiene uno para sus campañas; su nombre empieza por "V" (por confirmar).
- Página de pago: por confirmar con el jefe.
Cuando se conozcan, se agregan sus implementaciones y se cambian en messaging/infrastructure/container.py.
"""

import logging
import uuid

log = logging.getLogger(__name__)


class LoggingSmsSender:
    """No envía nada: deja el SMS en el log y devuelve un id de prueba."""

    def send(self, to_phone: str, body: str) -> str:
        message_id = f"dev-{uuid.uuid4().hex[:12]}"
        log.info("SMS (simulado) %s a %s: %s", message_id, to_phone, body)
        return message_id


class PlaceholderPaymentLinkProvider:
    """Link de prueba que no lleva a ningún lado (dominio .invalid)."""

    def link_for(self, scheduled_payment_id: str, amount_cents: int) -> str:
        return f"https://pay.example.invalid/p/{scheduled_payment_id}"
