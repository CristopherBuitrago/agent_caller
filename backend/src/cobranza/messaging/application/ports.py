"""Interfaces de la mensajería. Las implementaciones están en messaging/infrastructure/."""

from datetime import datetime
from enum import Enum
from typing import Protocol


class SmsKind(Enum):
    ARRANGEMENT_CONFIRMATION = "arrangement_confirmation"
    PAYMENT_LINK = "payment_link"
    PAYMENT_REMINDER = "payment_reminder"  # N10: aviso 3 días antes, sin link


class SmsSendError(Exception):
    """El proveedor no pudo enviar el SMS."""


class SmsSender(Protocol):
    """Envía un SMS. Hoy: implementación de desarrollo; después, el proveedor de la empresa."""

    def send(self, to_phone: str, body: str) -> str:
        """Devuelve el id que asigna el proveedor. Lanza SmsSendError si falla."""
        ...


class PaymentLinkProvider(Protocol):
    """Link a la página de pago segura del procesador. Nunca pasa datos de tarjeta por el sistema."""

    def link_for(self, scheduled_payment_id: str, amount_cents: int) -> str: ...


class SmsRepository(Protocol):
    """Registro de SMS (tabla sms_messages). Evita enviar dos veces el mismo mensaje."""

    def claim(self, kind: SmsKind, debtor_id: str, arrangement_id: str,
              scheduled_payment_id: str | None, to_phone: str, body: str) -> str | None:
        """Reserva el envío y devuelve su id, o None si ese mensaje ya se envió o está en curso.

        Un mensaje que falló se puede volver a reservar (reintento).
        """
        ...

    def mark_sent(self, sms_id: str, provider_message_id: str, sent_at: datetime) -> None: ...

    def mark_failed(self, sms_id: str, error: str) -> None: ...
