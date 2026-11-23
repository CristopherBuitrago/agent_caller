from typing import Protocol

from cobranza.domain.identity import IdentityRecord


class IdentityRepository(Protocol):
    """Interfaz. Implementación: infrastructure/repositories/postgres_identity_repository.py"""

    def get_identity(self, debtor_id: str) -> IdentityRecord | None:
        """Datos de verificación (solo hashes). Lo usa únicamente VerifyIdentity."""
        ...

    def find_debtor_ids(self, ssn_last4_hash: bytes, dob_hash: bytes) -> list[str]:
        """Deudores con esos últimos 4 del SSN y esa fecha (hashes). Solo para demos sin teléfono."""
        ...
