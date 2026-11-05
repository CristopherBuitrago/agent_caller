"""Función 1: consultar deudor (casos de uso / puertos de entrada)."""

from cobranza.application.interfaces.debtor_repository import DebtorRepository
from cobranza.application.interfaces.phone_service import PhoneService
from cobranza.domain.debtor import DebtorSummary


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
