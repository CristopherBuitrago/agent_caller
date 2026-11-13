from typing import Protocol

from cobranza.domain.debtor import DebtorSummary


class DebtorRepository(Protocol):
    """Interfaz. Implementación: infrastructure/repositories/postgres_debtor_repository.py"""

    def find_by_phone(self, phone_e164: str) -> list[DebtorSummary]:
        """Deudores cuyo teléfono principal o secundario coincide (puede ser varios o ninguno)."""
        ...

    def get_by_account(self, account_external_id: str) -> DebtorSummary | None:
        """El deudor dueño de la cuenta, con todas sus cuentas."""
        ...

    def mark_disputed(self, account_id: str, status: str) -> None:
        """Marca la cuenta en disputa (is_disputed) y le pone el estado dado (N11: DISPUTE)."""
        ...

    def mark_do_not_call(self, debtor_id: str) -> None: ...
