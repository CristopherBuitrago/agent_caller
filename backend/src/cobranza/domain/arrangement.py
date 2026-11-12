"""Reglas de los acuerdos de pago. Nunca hay descuentos: los pagos siempre suman el saldo completo.

Orden: todo de una, 2 cuotas, 3 cuotas, Hardship Questions, de 4 a 10 cuotas, primer pago del 10%
más 12 cuotas mensuales (N5) y, como último recurso, un pago parcial menor al 10%. Si nada funciona,
se transfiere a un agente.
El deudor acepta o rechaza; lo único que puede proponer es el monto de un pago parcial.
"""

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

REGULAR_MIN_PARTIAL_PAYMENT_PCT = 10
# Último recurso, "cuando no hay opción": requiere Hardship y haber rechazado todas las ofertas.
MIN_PARTIAL_PAYMENT_PCT = 5
LAST_INSTALLMENTS_BEFORE_HARDSHIP = 3
MAX_DAYS_TO_FIRST_PAYMENT = 8
MAX_DAYS_TO_PAY_REMAINDER = 30  # contados desde el primer pago
# Plazo máximo del plan: 1 año ("Maximo un año"). El último pago puede caer, como mucho, el mismo
# día del mes 12 meses después del primero.
MAX_PLAN_MONTHS = 12
# Con cuotas iguales y la primera de al menos 10%, no caben más de 10.
MAX_INSTALLMENTS = 10
# N5 (2026-11-12): después de las Hardship Questions, la última oferta es un primer pago del 10% y
# el resto en cuotas mensuales iguales hasta completar el año. Es la cuota más baja posible sin
# pasar del año ni bajar del 10% inicial. Si tampoco alcanza, se transfiere a una persona.
DOWN_PAYMENT_PLAN_INSTALLMENTS = MAX_PLAN_MONTHS
# Números de oferta: 1 = todo de una, 2 a 10 = cuotas iguales, 11 = pago inicial + 12 cuotas.
DOWN_PAYMENT_OFFER = MAX_INSTALLMENTS + 1
LAST_OFFER = DOWN_PAYMENT_OFFER
# Estado de la cuenta al crear un acuerdo (Promise To Pay).
STATUS_AFTER_ARRANGEMENT = "PTP"


class ArrangementType(Enum):
    FULL = "full"
    PARTIAL = "partial"
    PLAN = "plan"


class RuleViolation(Enum):
    NO_BALANCE = "no_balance"
    AMOUNT_BELOW_FLOOR = "amount_below_floor"
    AMOUNT_NOT_PARTIAL = "amount_not_partial"  # cubre todo el saldo: es un pago total
    TOTAL_DIFFERS_FROM_BALANCE = "total_differs_from_balance"  # nunca hay descuentos
    INVALID_SCHEDULE = "invalid_schedule"
    FIRST_PAYMENT_DATE_OUT_OF_RANGE = "first_payment_date_out_of_range"
    REMAINDER_DATE_OUT_OF_RANGE = "remainder_date_out_of_range"
    # Condiciones de la llamada y de la cuenta
    RECORDING_CONSENT_MISSING = "recording_consent_missing"
    IDENTITY_NOT_VERIFIED = "identity_not_verified"
    ACCOUNT_NOT_COLLECTABLE = "account_not_collectable"
    ACTIVE_ARRANGEMENT_EXISTS = "active_arrangement_exists"
    # Orden de la negociación
    HARDSHIP_REQUIRED = "hardship_required"
    OFFERS_NOT_EXHAUSTED = "offers_not_exhausted"


class ArrangementRuleError(ValueError):
    def __init__(self, violation: RuleViolation):
        super().__init__(violation.value)
        self.violation = violation


@dataclass(frozen=True)
class ScheduledPayment:
    sequence: int
    amount_cents: int
    due_date: date


@dataclass(frozen=True)
class ArrangementProposal:
    type: ArrangementType
    total_amount_cents: int
    payments: tuple[ScheduledPayment, ...]


def is_last_resort_partial(proposal: ArrangementProposal) -> bool:
    first = proposal.payments[0].amount_cents
    return (proposal.type is ArrangementType.PARTIAL
            and first * 100 < proposal.total_amount_cents * REGULAR_MIN_PARTIAL_PAYMENT_PCT)


def requires_hardship(proposal: ArrangementProposal) -> bool:
    """Planes de más de 3 cuotas y parciales menores al 10% van después de las Hardship Questions."""
    if proposal.type is ArrangementType.PLAN:
        return len(proposal.payments) > LAST_INSTALLMENTS_BEFORE_HARDSHIP
    return is_last_resort_partial(proposal)


def add_months(start: date, months: int) -> date:
    """Mismo día del mes, `months` después. Si ese mes no tiene ese día, usa su último día."""
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def _equal_parts(total_cents: int, parts: int) -> list[int]:
    """Partes iguales; los centavos que sobran van en la primera, para que el total dé exacto."""
    base, leftover = divmod(total_cents, parts)
    return [base + leftover] + [base] * (parts - 1)


def build_full(balance_cents: int, first_due: date, today: date) -> ArrangementProposal:
    proposal = ArrangementProposal(
        ArrangementType.FULL, balance_cents, (ScheduledPayment(1, balance_cents, first_due),),
    )
    validate_proposal(proposal, balance_cents, today)
    return proposal


def build_plan(balance_cents: int, installments: int, first_due: date, today: date) -> ArrangementProposal:
    """Cuotas iguales y mensuales: la fecha fija es el día del mes del primer pago."""
    if balance_cents < installments:
        raise ArrangementRuleError(RuleViolation.INVALID_SCHEDULE)
    payments = tuple(
        ScheduledPayment(i + 1, amount, add_months(first_due, i))
        for i, amount in enumerate(_equal_parts(balance_cents, installments))
    )
    proposal = ArrangementProposal(ArrangementType.PLAN, balance_cents, payments)
    validate_proposal(proposal, balance_cents, today)
    return proposal


def _down_payment(balance_cents: int) -> int:
    """El 10% del saldo, redondeado hacia arriba al centavo."""
    return -(-balance_cents * REGULAR_MIN_PARTIAL_PAYMENT_PCT // 100)


def build_down_payment_plan(balance_cents: int, first_due: date, today: date) -> ArrangementProposal:
    """N5: primer pago del 10% y el resto en 12 cuotas mensuales iguales (13 pagos en 1 año)."""
    down = _down_payment(balance_cents)
    rest = balance_cents - down
    if rest < DOWN_PAYMENT_PLAN_INSTALLMENTS:
        raise ArrangementRuleError(RuleViolation.INVALID_SCHEDULE)
    payments = (ScheduledPayment(1, down, first_due),) + tuple(
        ScheduledPayment(i + 2, amount, add_months(first_due, i + 1))
        for i, amount in enumerate(_equal_parts(rest, DOWN_PAYMENT_PLAN_INSTALLMENTS))
    )
    proposal = ArrangementProposal(ArrangementType.PLAN, balance_cents, payments)
    validate_proposal(proposal, balance_cents, today)
    return proposal


def is_down_payment_plan(proposal: ArrangementProposal) -> bool:
    amounts = [p.amount_cents for p in proposal.payments]
    return (proposal.type is ArrangementType.PLAN
            and len(amounts) == DOWN_PAYMENT_PLAN_INSTALLMENTS + 1
            and amounts[0] == _down_payment(proposal.total_amount_cents)
            and amounts[1:] == _equal_parts(sum(amounts[1:]), DOWN_PAYMENT_PLAN_INSTALLMENTS))


def build_partial(balance_cents: int, first_amount_cents: int, first_due: date, today: date,
                  remainder_due: date | None = None) -> ArrangementProposal:
    """Monto propuesto por el deudor. El resto va en un solo pago, por defecto a los 30 días."""
    if balance_cents <= 0:
        raise ArrangementRuleError(RuleViolation.NO_BALANCE)
    if first_amount_cents >= balance_cents:
        raise ArrangementRuleError(RuleViolation.AMOUNT_NOT_PARTIAL)
    default_remainder_due = first_due + timedelta(days=MAX_DAYS_TO_PAY_REMAINDER)
    proposal = ArrangementProposal(ArrangementType.PARTIAL, balance_cents, (
        ScheduledPayment(1, first_amount_cents, first_due),
        ScheduledPayment(2, balance_cents - first_amount_cents, remainder_due or default_remainder_due),
    ))
    validate_proposal(proposal, balance_cents, today)
    return proposal


def validate_proposal(proposal: ArrangementProposal, balance_cents: int, today: date) -> None:
    """Toda propuesta pasa por aquí antes de ofrecerse y otra vez antes de guardarse."""
    payments = proposal.payments
    if balance_cents <= 0:
        raise ArrangementRuleError(RuleViolation.NO_BALANCE)
    if proposal.type is ArrangementType.PARTIAL and payments:
        # Va antes de revisar el calendario para que un monto bajo se informe como tal.
        if payments[0].amount_cents * 100 < balance_cents * MIN_PARTIAL_PAYMENT_PCT:
            raise ArrangementRuleError(RuleViolation.AMOUNT_BELOW_FLOOR)
    if (proposal.total_amount_cents != balance_cents
            or sum(p.amount_cents for p in payments) != balance_cents):
        raise ArrangementRuleError(RuleViolation.TOTAL_DIFFERS_FROM_BALANCE)
    if (not payments
            or any(p.amount_cents <= 0 for p in payments)
            or [p.sequence for p in payments] != list(range(1, len(payments) + 1))
            or any(a.due_date >= b.due_date for a, b in zip(payments, payments[1:]))):
        raise ArrangementRuleError(RuleViolation.INVALID_SCHEDULE)

    first = payments[0]
    if not today <= first.due_date <= today + timedelta(days=MAX_DAYS_TO_FIRST_PAYMENT):
        raise ArrangementRuleError(RuleViolation.FIRST_PAYMENT_DATE_OUT_OF_RANGE)

    if proposal.type is ArrangementType.FULL:
        if len(payments) != 1:
            raise ArrangementRuleError(RuleViolation.INVALID_SCHEDULE)
    elif proposal.type is ArrangementType.PLAN:
        _validate_plan(payments)
    else:
        _validate_partial(payments)


def _validate_plan(payments) -> None:
    amounts = [p.amount_cents for p in payments]
    first_due = payments[0].due_date
    equal_installments = (2 <= len(payments) <= MAX_INSTALLMENTS
                          and amounts == _equal_parts(sum(amounts), len(amounts)))
    down_payment_plan = is_down_payment_plan(
        ArrangementProposal(ArrangementType.PLAN, sum(amounts), tuple(payments)))
    if (not (equal_installments or down_payment_plan)
            or any(p.due_date != add_months(first_due, i) for i, p in enumerate(payments))
            or payments[-1].due_date > add_months(first_due, MAX_PLAN_MONTHS)):
        raise ArrangementRuleError(RuleViolation.INVALID_SCHEDULE)


def _validate_partial(payments) -> None:
    if len(payments) != 2:
        raise ArrangementRuleError(RuleViolation.INVALID_SCHEDULE)
    if payments[1].due_date - payments[0].due_date > timedelta(days=MAX_DAYS_TO_PAY_REMAINDER):
        raise ArrangementRuleError(RuleViolation.REMAINDER_DATE_OUT_OF_RANGE)
