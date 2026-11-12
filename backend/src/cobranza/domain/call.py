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
