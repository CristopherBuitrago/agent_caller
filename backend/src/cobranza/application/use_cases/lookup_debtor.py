"""Función 1: consultar deudor (casos de uso / puertos de entrada)."""

from cobranza.application.interfaces.debtor_repository import DebtorRepository
from cobranza.application.interfaces.phone_service import PhoneService
from cobranza.domain.debtor import DebtorSummary
from cobranza.domain.identity import name_words, names_match


class FindDebtorsByPhone:
    """Llamada entrante: busca por el número desde el que llaman."""

    def __init__(self, debtors: DebtorRepository, phones: PhoneService):
        self._debtors = debtors
        self._phones = phones

    def execute(self, raw_phone: str) -> list[DebtorSummary]:
        phone = self._phones.normalize(raw_phone)
        if phone is None:
            return []
        return [_fill_timezone(d, self._phones) for d in self._debtors.find_by_phone(phone)]


class FindDebtorsByName:
    """Solo para demos sin teléfono (navegador): busca por el nombre que dijo quien llama.

    En producción las entrantes se buscan por teléfono; esto lo activa DEMO_LOOKUP_BY_NAME en la API.
    Devuelve primero a quien coincide en nombre y apellido; si nadie coincide, a quienes comparten
    alguna palabra (así la verificación puede pedir deletrear el apellido, como con el teléfono).
    """

    def __init__(self, debtors: DebtorRepository, phones: PhoneService):
        self._debtors = debtors
        self._phones = phones

    def execute(self, spoken_full_name: str) -> list[DebtorSummary]:
        words = name_words(spoken_full_name)
        if not words:
            return []
        found = [_fill_timezone(d, self._phones) for d in self._debtors.find_by_name_words(words)]
        return sorted(found, key=lambda d: not names_match(spoken_full_name, d.first_name, d.last_name))


class GetDebtorById:
    """El deudor encontrado por sus datos de identidad (demo sin teléfono)."""

    def __init__(self, debtors: DebtorRepository, phones: PhoneService):
        self._debtors = debtors
        self._phones = phones

    def execute(self, debtor_id: str) -> DebtorSummary | None:
        debtor = self._debtors.get_by_id(debtor_id)
        return _fill_timezone(debtor, self._phones) if debtor else None


class GetDebtorByAccount:
    """Llamada saliente: el deudor dueño de la cuenta que entrega el job."""

    def __init__(self, debtors: DebtorRepository, phones: PhoneService):
        self._debtors = debtors
        self._phones = phones

    def execute(self, account_external_id: str) -> DebtorSummary | None:
        debtor = self._debtors.get_by_account(account_external_id)
        return _fill_timezone(debtor, self._phones) if debtor else None


def _fill_timezone(debtor: DebtorSummary, phones: PhoneService) -> DebtorSummary:
    """Si falta la zona horaria, se deduce del código de área del teléfono principal."""
    if debtor.timezone is not None:
        return debtor
    timezone = phones.timezone_for(debtor.phone_primary)
    return debtor.with_inferred_timezone(timezone) if timezone else debtor
