"""Función 2: verificar identidad."""

import hmac
from collections.abc import Sequence
from datetime import date

from cobranza.application.interfaces.call_repository import CallRepository
from cobranza.application.interfaces.clock import Clock
from cobranza.application.interfaces.identity_repository import IdentityRepository
from cobranza.application.interfaces.pii_hasher import PiiHasher
from cobranza.domain.identity import (
    LOCKOUT_WINDOW,
    MAX_FAILED_ATTEMPTS_IN_WINDOW,
    MAX_FAILED_ATTEMPTS_PER_CALL,
    VerificationOutcome,
    first_name_changed,
    is_valid_ssn_last4,
    names_match,
    only_last_name_differs,
)


class VerifyIdentity:
    def __init__(self, identities: IdentityRepository, calls: CallRepository,
                 hasher: PiiHasher, clock: Clock):
        self._identities = identities
        self._calls = calls
        self._hasher = hasher
        self._clock = clock

    def execute(self, call_id: str, debtor_id: str, full_name: str, ssn_last4: str,
                dob: date, name_was_spelled: bool = False,
                earlier_names: Sequence[str] = ()) -> VerificationOutcome:
        """`dob` llega ya convertida desde lo hablado. `name_was_spelled` = el deudor ya deletreó el apellido.

        `earlier_names`: los nombres que dio quien llama en los intentos anteriores de esta llamada.
        """
        state = self._calls.get_verification_state(call_id)
        if state is None:
            raise ValueError(f"Llamada desconocida: {call_id}")
        if state.identity_verified:
            # Una llamada verifica a una sola persona (importa con teléfonos compartidos).
            if state.debtor_id != debtor_id:
                raise ValueError("La llamada ya verificó a otro deudor")
            return VerificationOutcome.VERIFIED
        if state.failed_attempts >= MAX_FAILED_ATTEMPTS_PER_CALL:
            return VerificationOutcome.MAX_ATTEMPTS_REACHED

        since = self._clock.now() - LOCKOUT_WINDOW
        recent_failures = self._calls.count_failed_verifications_since(debtor_id, since)
        if recent_failures >= MAX_FAILED_ATTEMPTS_IN_WINDOW:
            return VerificationOutcome.LOCKED

        # Verificación por tanteo (S1): si cambia el nombre entre intentos, no se revisan los datos.
        # Cuenta como intento fallido para el bloqueo de 24 horas.
        if any(first_name_changed(earlier, full_name) for earlier in earlier_names):
            self._calls.record_verification_attempt(call_id, debtor_id, False)
            return VerificationOutcome.IDENTITY_MISMATCH

        identity = self._identities.get_identity(debtor_id)
        if identity is None:
            raise ValueError(f"Deudor desconocido: {debtor_id}")

        name_ok = names_match(full_name, identity.first_name, identity.last_name)
        data_ok = (
            is_valid_ssn_last4(ssn_last4)
            and hmac.compare_digest(self._hasher.hash(ssn_last4), identity.ssn_last4_hash)
            and hmac.compare_digest(self._hasher.hash(dob.isoformat()), identity.dob_hash)
        )
        # S2: deletrear solo cuando todo coincide menos el apellido (error típico al transcribir la voz).
        # Cualquier otro fallo es un intento fallido normal, sin decir qué dato falló.
        if (data_ok and not name_was_spelled
                and only_last_name_differs(full_name, identity.first_name, identity.last_name)):
            return VerificationOutcome.NAME_RETRY

        verified = name_ok and data_ok
        self._calls.record_verification_attempt(call_id, debtor_id, verified)

        if verified:
            return VerificationOutcome.VERIFIED
        if recent_failures + 1 >= MAX_FAILED_ATTEMPTS_IN_WINDOW:
            return VerificationOutcome.LOCKED
        if state.failed_attempts + 1 >= MAX_FAILED_ATTEMPTS_PER_CALL:
            return VerificationOutcome.MAX_ATTEMPTS_REACHED
        return VerificationOutcome.FAILED
