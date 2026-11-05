from typing import Protocol


class PhoneService(Protocol):
    """Interfaz. Implementación: infrastructure/services/phonenumbers_phone_service.py"""

    def normalize(self, raw_phone: str) -> str | None:
        """Teléfono de EE. UU. en cualquier formato → E.164 (+13055550123); None si no es válido."""
        ...

    def timezone_for(self, phone_e164: str) -> str | None:
        """Zona horaria IANA según el código de área; None si no se puede deducir."""
        ...
