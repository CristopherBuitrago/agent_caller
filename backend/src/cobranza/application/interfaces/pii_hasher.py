from typing import Protocol


class PiiHasher(Protocol):
    """Interfaz. Implementación: infrastructure/services/hmac_pii_hasher.py"""

    def hash(self, value: str) -> bytes:
        """Hash con clave secreta (HMAC). La clave nunca entra al dominio."""
        ...
