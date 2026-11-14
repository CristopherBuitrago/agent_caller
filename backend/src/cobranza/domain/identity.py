"""Reglas de verificación de identidad (nombre completo + últimos 4 del SSN + fecha de nacimiento)."""

import re
import unicodedata
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum

MAX_FAILED_ATTEMPTS_PER_CALL = 2
MAX_FAILED_ATTEMPTS_IN_WINDOW = 5
LOCKOUT_WINDOW = timedelta(hours=24)


class VerificationOutcome(Enum):
    VERIFIED = "verified"
    # SSN, fecha y nombre de pila coinciden; solo el apellido no (error típico al transcribir):
    # el agente pide deletrear el apellido. No cuenta como intento.
    NAME_RETRY = "name_retry"
    # Falló; puede volver a intentarlo en esta llamada. No se dice qué dato falló.
    FAILED = "failed"
    # 2 fallos en esta llamada: se cierra sin revelar la deuda.
    MAX_ATTEMPTS_REACHED = "max_attempts_reached"
    # 5 fallos en 24 horas sumando llamadas: se transfiere a una persona.
    LOCKED = "locked"
    # Quien llama cambió de nombre entre intentos (p. ej. "Paul Carter" y luego "Jane Carter"):
    # se cierra la llamada sin revisar los datos, para que no pueda adivinar por tanteo.
    IDENTITY_MISMATCH = "identity_mismatch"


def attempts_left(failed_in_call: int, failed_in_window: int) -> int:
    """Intentos que le quedan a quien llama antes de cerrar o bloquear (B8). Nunca negativo."""
    return max(0, min(MAX_FAILED_ATTEMPTS_PER_CALL - failed_in_call,
                      MAX_FAILED_ATTEMPTS_IN_WINDOW - failed_in_window))


@dataclass(frozen=True)
class IdentityRecord:
    """Lo guardado para verificar. dob y SSN vienen solo como hash; nunca en claro."""
    debtor_id: str
    first_name: str
    last_name: str
    dob_hash: bytes
    ssn_last4_hash: bytes


@dataclass(frozen=True)
class CallVerificationState:
    debtor_id: str | None  # a quién se está verificando en esta llamada
    attempts: int
    identity_verified: bool

    @property
    def failed_attempts(self) -> int:
        return self.attempts - (1 if self.identity_verified else 0)


def _name_tokens(name: str) -> list[str]:
    without_accents = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z ]", " ", without_accents.lower().replace("'", "")).split()


def names_match(spoken_full_name: str, first_name: str, last_name: str) -> bool:
    """Nombre y apellido deben coincidir; se toleran mayúsculas, tildes, guiones y segundos nombres.

    "jane marie carter" coincide con Jane / Carter; "Jane Smith" no.
    """
    spoken = _name_tokens(spoken_full_name)
    first = _name_tokens(first_name)
    last = _name_tokens(last_name)
    if not spoken or not first or not last or len(spoken) < len(first) + len(last):
        return False
    return spoken[: len(first)] == first and spoken[-len(last):] == last


def only_last_name_differs(spoken_full_name: str, first_name: str, last_name: str) -> bool:
    """El nombre de pila coincide y el apellido no: suele ser un error al transcribir la voz.

    Es el único caso en que tiene sentido pedir que deletree el apellido (S2).
    "Jane Karter" -> True; "Paul Carter" -> False (lo que falla es el nombre de pila).
    """
    spoken = _name_tokens(spoken_full_name)
    first = _name_tokens(first_name)
    if not spoken or not first or len(spoken) <= len(first) or spoken[: len(first)] != first:
        return False
    return not names_match(spoken_full_name, first_name, last_name)


def is_valid_ssn_last4(value: str) -> bool:
    return bool(re.fullmatch(r"\d{4}", value))


def first_name_changed(earlier_full_name: str, full_name: str) -> bool:
    """True si quien llama dio un nombre de pila distinto al de un intento anterior de la misma llamada.

    Solo se compara el primer nombre: corregir la ortografía del apellido ("Karter" -> "Carter",
    lo que pide NAME_RETRY) o agregar un segundo nombre no cuenta como cambio.
    """
    earlier = _name_tokens(earlier_full_name)
    current = _name_tokens(full_name)
    if not earlier or not current:
        return False
    return earlier[0] != current[0]
