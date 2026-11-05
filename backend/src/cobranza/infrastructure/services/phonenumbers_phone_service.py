"""Adaptador de PhoneService sobre la librería phonenumbers (libphonenumber de Google)."""

import phonenumbers
from phonenumbers import timezone as phone_timezone


class PhonenumbersPhoneService:
    def normalize(self, raw_phone: str) -> str | None:
        try:
            parsed = phonenumbers.parse(raw_phone, "US")
        except phonenumbers.NumberParseException:
            return None
        if parsed.country_code != 1 or len(str(parsed.national_number)) != 10:
            return None
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

    def timezone_for(self, phone_e164: str) -> str | None:
        # Búsqueda por prefijo: no exige que el número sea válido (los 555-01XX
        # de los datos simulados no lo son). Si el código de área cubre varias
        # zonas, se toma la primera que reporta la librería.
        parsed = phonenumbers.parse(phone_e164, "US")
        zones = phone_timezone.time_zones_for_geographical_number(parsed)
        if not zones or zones[0] == phone_timezone.UNKNOWN_TIMEZONE:
            return None
        return zones[0]
