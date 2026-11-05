"""Deudor y cuentas tal como los ve el agente.

Dominio puro: no depende de la base de datos ni de librerías externas.
Nunca incluye la fecha de nacimiento ni el SSN; esos datos solo se usan dentro
de la verificación de identidad y no salen de la base.
"""

from dataclasses import dataclass, replace
from datetime import date

# Estados que el agente puede cobrar. Cualquier otro valor se transfiere a una persona.
COLLECTABLE_STATUSES = frozenset({
    "NSF",
    "first_attempt",
    "second_attempt",
    "third_attempt",
    "fourth_attempt",
})


@dataclass(frozen=True)
class AccountSummary:
    id: str
    external_id: str | None
    creditor_name: str
    account_number_masked: str
    current_balance_cents: int
    status: str
    payment_method: str | None
    nsf_amount_cents: int | None
    nsf_fee_cents: int
    nsf_date: date | None
    nsf_return_code: str | None
    is_disputed: bool


@dataclass(frozen=True)
class DebtorSummary:
    id: str
    external_id: str | None
    first_name: str
    last_name: str
    phone_primary: str
    us_state: str | None
    timezone: str | None
    timezone_inferred: bool  # True si se dedujo del código de área
    do_not_call: bool
    accounts: tuple[AccountSummary, ...]

    def can_collect(self, account: AccountSummary) -> bool:
        """El agente cobra solo NSF / intentos 1–4, sin disputa y sin "no llamar"."""
        return (
            account.status in COLLECTABLE_STATUSES
            and not account.is_disputed
            and not self.do_not_call
        )

    @property
    def collectable_accounts(self) -> tuple[AccountSummary, ...]:
        return tuple(a for a in self.accounts if self.can_collect(a))

    def with_inferred_timezone(self, timezone: str) -> "DebtorSummary":
        return replace(self, timezone=timezone, timezone_inferred=True)
