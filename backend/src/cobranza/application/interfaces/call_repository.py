from datetime import datetime
from typing import Protocol

from cobranza.domain.call import CallDirection, CallOutcome, CallRecord
from cobranza.domain.identity import CallVerificationState


class CallRepository(Protocol):
    """Interfaz. Implementación: infrastructure/repositories/postgres_call_repository.py"""

    # --- ciclo de vida de la llamada (Función 3) ---

    def create(self, direction: CallDirection, caller_phone: str, started_at: datetime,
               debtor_id: str | None, account_id: str | None) -> str:
        """Crea la llamada y devuelve su id."""
        ...

    def get(self, call_id: str) -> CallRecord | None: ...

    def set_recording_consent(self, call_id: str, accepted: bool) -> None: ...

    def link_account(self, call_id: str, account_id: str) -> None: ...

    def close(self, call_id: str, outcome: CallOutcome, summary: str | None, ended_at: datetime) -> None: ...

    # --- verificación de identidad (Función 2) ---

    def get_verification_state(self, call_id: str) -> CallVerificationState | None: ...

    def record_verification_attempt(self, call_id: str, debtor_id: str, succeeded: bool) -> None:
        """Suma 1 a calls.verification_attempts y asocia la llamada al deudor."""
        ...

    def count_failed_verifications_since(self, debtor_id: str, since: datetime) -> int:
        """Fallos de verificación del deudor en todas sus llamadas desde `since`."""
        ...
