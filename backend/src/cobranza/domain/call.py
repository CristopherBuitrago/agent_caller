"""Llamada: dirección, resultado y reglas de cierre."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class CallDirection(Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallOutcome(Enum):
    """Mismos valores que el CHECK de calls.outcome."""
    PAYMENT_TAKEN = "payment_taken"
    ARRANGEMENT_MADE = "arrangement_made"
    TRANSFERRED_TO_HUMAN = "transferred_to_human"
    DISPUTE = "dispute"
    DO_NOT_CALL = "do_not_call"
    VERIFICATION_FAILED = "verification_failed"
    WRONG_PARTY = "wrong_party"
    CALLBACK_REQUESTED = "callback_requested"
    NO_ANSWER = "no_answer"
    # Toda llamada se graba por política; sin consentimiento se cierra sin hablar de la deuda.
    RECORDING_REFUSED = "recording_refused"
    # Quien llama cambió de nombre entre intentos de verificación; se le pide llamar con sus datos.
    IDENTITY_MISMATCH = "identity_mismatch"


@dataclass(frozen=True)
class CallRecord:
    id: str
    direction: CallDirection
    debtor_id: str | None
    account_id: str | None
    recording_consent: bool | None  # None = aún no se ha preguntado
    ended_at: datetime | None

    @property
    def is_open(self) -> bool:
        return self.ended_at is None


def check_can_close(call: CallRecord, outcome: CallOutcome) -> None:
    """Reglas para cerrar una llamada. Lanza ValueError si no se cumplen."""
    if not call.is_open:
        raise ValueError(f"La llamada {call.id} ya está cerrada")
    if call.recording_consent is False and outcome is not CallOutcome.RECORDING_REFUSED:
        raise ValueError("Sin consentimiento de grabación, el único resultado posible es recording_refused")


@dataclass(frozen=True)
class LastContact:
    """La última llamada saliente de la empresa al deudor (N13)."""
    started_at: datetime
    arrangement_made: bool  # en esa llamada se cerró un acuerdo


# --- N9 / B2: volver a llamar en el día y la hora que pidió la persona ---------------------

# Reg F: no se llama antes de las 8 a. m. ni después de las 9 p. m., hora local del deudor.
CALLBACK_EARLIEST_HOUR = 8
CALLBACK_LATEST_HOUR = 21
# Confirmado por el desarrollador (2026-11-13): no se agenda una devolución de llamada a más de 30 días.
MAX_DAYS_TO_CALLBACK = 30


class CallbackTimeError(ValueError):
    """La hora pedida para volver a llamar no se puede usar."""


def check_callback_time(local_when: datetime, now: datetime) -> None:
    """`local_when` va con la zona horaria del deudor. Lanza CallbackTimeError si no sirve."""
    if local_when <= now:
        raise CallbackTimeError("past")
    minutes = local_when.hour * 60 + local_when.minute
    if not CALLBACK_EARLIEST_HOUR * 60 <= minutes <= CALLBACK_LATEST_HOUR * 60:
        raise CallbackTimeError("outside_calling_hours")
    if (local_when - now).days >= MAX_DAYS_TO_CALLBACK:
        raise CallbackTimeError("too_far")
