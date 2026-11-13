"""Reglas de los acuerdos de pago (dominio puro)."""

from dataclasses import replace
from datetime import date, timedelta

import pytest

from cobranza.domain.arrangement import (
    ArrangementProposal,
    ArrangementRuleError,
    ArrangementType,
    RuleViolation as R,
    ScheduledPayment,
    add_months,
    build_full,
    build_partial,
    build_plan,
    validate_proposal,
)

TODAY = date(2026, 11, 2)
BALANCE = 100000  # USD 1.000


def _violation(fn, *args, **kwargs):
    with pytest.raises(ArrangementRuleError) as e:
        fn(*args, **kwargs)
    return e.value.violation


def _amounts(proposal):
    return [p.amount_cents for p in proposal.payments]


def _dates(proposal):
    return [p.due_date for p in proposal.payments]


def test_full_is_one_payment_of_the_whole_balance():
    proposal = build_full(BALANCE, TODAY, TODAY)
    assert proposal.type is ArrangementType.FULL
    assert _amounts(proposal) == [BALANCE]


# --- fecha fija cada mes ------------------------------------------------------

@pytest.mark.parametrize("start, months, expected", [
    (date(2026, 11, 2), 1, date(2026, 12, 2)),
    (date(2026, 11, 2), 2, date(2027, 1, 2)),      # cambia de año
    (date(2027, 1, 31), 1, date(2027, 2, 28)),     # febrero no tiene 31
    (date(2027, 1, 31), 2, date(2027, 3, 31)),     # vuelve al día 31
    (date(2028, 1, 31), 1, date(2028, 2, 29)),     # año bisiesto
])
def test_add_months_keeps_the_day_of_the_month(start, months, expected):
    assert add_months(start, months) == expected


# --- planes -------------------------------------------------------------------

@pytest.mark.parametrize("installments", range(2, 11))
def test_plan_is_equal_monthly_installments_that_add_up_to_the_balance(installments):
    proposal = build_plan(BALANCE, installments, TODAY, TODAY)
    assert sum(_amounts(proposal)) == BALANCE
    assert _dates(proposal) == [add_months(TODAY, i) for i in range(installments)]
    assert _amounts(proposal)[0] * 100 >= BALANCE * 10


def test_plan_keeps_a_fixed_date_each_month():
    assert _dates(build_plan(BALANCE, 3, date(2026, 11, 5), TODAY)) == [
        date(2026, 11, 5), date(2026, 12, 5), date(2027, 1, 5),
    ]


def test_longest_plan_is_within_one_year():
    proposal = build_plan(BALANCE, 10, TODAY + timedelta(days=7), TODAY)
    assert proposal.payments[-1].due_date - proposal.payments[0].due_date <= timedelta(days=365)


def test_leftover_cents_go_in_the_first_installment():
    assert _amounts(build_plan(48500, 3, TODAY, TODAY)) == [16168, 16166, 16166]


def test_plan_cannot_exceed_ten_installments():
    assert _violation(build_plan, BALANCE, 11, TODAY, TODAY) is R.INVALID_SCHEDULE


@pytest.mark.parametrize("days, ok", [(-1, False), (0, True), (28, True), (29, False)])  # 2 nov -> 30 nov
def test_first_payment_is_up_to_the_end_of_the_month(days, ok):
    first_due = TODAY + timedelta(days=days)
    if ok:
        assert build_full(BALANCE, first_due, TODAY).payments[0].due_date == first_due
    else:
        assert _violation(build_full, BALANCE, first_due, TODAY) is R.FIRST_PAYMENT_DATE_OUT_OF_RANGE


# --- pago parcial -------------------------------------------------------------

def test_partial_remainder_is_one_payment_at_thirty_days_by_default():
    proposal = build_partial(BALANCE, 70000, TODAY, TODAY)
    assert _amounts(proposal) == [70000, 30000]
    assert _dates(proposal) == [TODAY, TODAY + timedelta(days=30)]


def test_partial_remainder_can_be_sooner_but_not_later_than_thirty_days():
    sooner = TODAY + timedelta(days=10)
    assert _dates(build_partial(BALANCE, 70000, TODAY, TODAY, sooner))[1] == sooner
    assert _violation(build_partial, BALANCE, 70000, TODAY, TODAY,
                      TODAY + timedelta(days=31)) is R.REMAINDER_DATE_OUT_OF_RANGE


def test_partial_thirty_days_count_from_the_first_payment():
    first_due = TODAY + timedelta(days=7)
    assert _dates(build_partial(BALANCE, 70000, first_due, TODAY))[1] == TODAY + timedelta(days=37)


def test_partial_at_the_floor_is_accepted_and_below_it_is_rejected():
    assert _amounts(build_partial(BALANCE, 5000, TODAY, TODAY)) == [5000, 95000]
    assert _violation(build_partial, BALANCE, 4999, TODAY, TODAY) is R.AMOUNT_BELOW_FLOOR


def test_paying_everything_is_not_a_partial():
    assert _violation(build_partial, BALANCE, BALANCE, TODAY, TODAY) is R.AMOUNT_NOT_PARTIAL


def test_no_balance_cannot_be_negotiated():
    assert _violation(build_full, 0, TODAY, TODAY) is R.NO_BALANCE
    assert _violation(build_partial, 0, 100, TODAY, TODAY) is R.NO_BALANCE


# --- nunca hay descuentos -----------------------------------------------------

def test_discounted_total_is_rejected():
    discounted = ArrangementProposal(
        ArrangementType.FULL, 90000, (ScheduledPayment(1, 90000, TODAY),))
    assert _violation(validate_proposal, discounted, BALANCE, TODAY) is R.TOTAL_DIFFERS_FROM_BALANCE


def test_payments_that_do_not_add_up_are_rejected_even_if_the_total_says_otherwise():
    tampered = ArrangementProposal(
        ArrangementType.FULL, BALANCE, (ScheduledPayment(1, 90000, TODAY),))
    assert _violation(validate_proposal, tampered, BALANCE, TODAY) is R.TOTAL_DIFFERS_FROM_BALANCE


def test_proposal_is_rejected_if_the_balance_changed():
    proposal = build_full(BALANCE, TODAY, TODAY)
    assert _violation(validate_proposal, proposal, BALANCE + 1, TODAY) is R.TOTAL_DIFFERS_FROM_BALANCE


# --- propuestas mal armadas ---------------------------------------------------

def test_unequal_plan_is_rejected():
    payments = (ScheduledPayment(1, 60000, TODAY), ScheduledPayment(2, 40000, add_months(TODAY, 1)))
    plan = ArrangementProposal(ArrangementType.PLAN, BALANCE, payments)
    assert _violation(validate_proposal, plan, BALANCE, TODAY) is R.INVALID_SCHEDULE


def test_plan_that_is_not_monthly_on_a_fixed_date_is_rejected():
    plan = build_plan(BALANCE, 2, TODAY, TODAY)
    biweekly = replace(plan.payments[1], due_date=TODAY + timedelta(days=14))
    assert _violation(validate_proposal, replace(plan, payments=(plan.payments[0], biweekly)),
                      BALANCE, TODAY) is R.INVALID_SCHEDULE


def test_partial_with_a_single_payment_is_rejected():
    partial = ArrangementProposal(ArrangementType.PARTIAL, BALANCE, (ScheduledPayment(1, BALANCE, TODAY),))
    assert _violation(validate_proposal, partial, BALANCE, TODAY) is R.INVALID_SCHEDULE


# --- N5: primer pago del 10% y el resto en 12 cuotas mensuales iguales -----------

from cobranza.domain.arrangement import build_down_payment_plan, is_down_payment_plan  # noqa: E402


def test_down_payment_plan_for_485():
    plan = build_down_payment_plan(48500, TODAY, TODAY)
    amounts = [p.amount_cents for p in plan.payments]
    assert amounts[0] == 4850 and amounts[1:] == [3643] + [3637] * 11   # 48,50; 36,43 y 11 de 36,37
    assert sum(amounts) == 48500 and is_down_payment_plan(plan)
    assert plan.payments[-1].due_date == date(2027, 11, 2)


def test_down_payment_rounds_ten_percent_up():
    assert build_down_payment_plan(48505, TODAY, TODAY).payments[0].amount_cents == 4851


def test_one_year_limit_works_across_a_leap_day():
    plan = build_down_payment_plan(48500, date(2027, 3, 1), date(2027, 3, 1))
    assert plan.payments[-1].due_date == date(2028, 3, 1)   # 366 días, pero es 1 año


@pytest.mark.parametrize("change", ["lower_down_payment", "unequal_installments", "longer"])
def test_altered_down_payment_plans_are_rejected(change):
    plan = build_down_payment_plan(48500, TODAY, TODAY)
    payments = list(plan.payments)
    if change == "lower_down_payment":      # 9% de entrada y lo demás repartido
        payments[0] = replace(payments[0], amount_cents=4365)
        payments[1] = replace(payments[1], amount_cents=payments[1].amount_cents + 485)
    elif change == "unequal_installments":
        payments[1] = replace(payments[1], amount_cents=payments[1].amount_cents + 100)
        payments[2] = replace(payments[2], amount_cents=payments[2].amount_cents - 100)
    else:                                   # una cuota más allá del año
        payments.append(ScheduledPayment(14, 1, add_months(TODAY, 13)))
        payments[1] = replace(payments[1], amount_cents=payments[1].amount_cents - 1)
    altered = ArrangementProposal(ArrangementType.PLAN, 48500, tuple(payments))
    assert _violation(validate_proposal, altered, 48500, TODAY) is R.INVALID_SCHEDULE


# --- N6: el resto de un parcial en cuotas mensuales cuando el deudor dice su límite -----

from cobranza.domain.arrangement import remainder_installments, requires_hardship  # noqa: E402


@pytest.mark.parametrize("max_cents, installments", [(50000, 1), (20000, 2), (10000, 4), (1000, 12)])
def test_remainder_installments_is_the_fewest_that_fit(max_cents, installments):
    assert remainder_installments(39500, max_cents) == installments


def test_partial_rest_in_monthly_installments():
    partial = build_partial(48500, 9000, TODAY, TODAY, max_installment_cents=10000)
    assert partial.type is ArrangementType.PARTIAL
    assert [p.amount_cents for p in partial.payments] == [9000] + [9875] * 4
    assert [p.due_date for p in partial.payments[1:]] == [add_months(TODAY, i) for i in range(1, 5)]
    assert requires_hardship(partial)                      # 5 pagos: más de 3


def test_partial_rest_in_one_payment_when_it_fits_or_without_a_limit():
    for partial in (build_partial(48500, 9000, TODAY, TODAY, max_installment_cents=50000),
                    build_partial(48500, 9000, TODAY, TODAY)):
        assert [p.amount_cents for p in partial.payments] == [9000, 39500]
        assert partial.payments[1].due_date == TODAY + timedelta(days=30)
        assert not requires_hardship(partial)


def test_partial_with_rest_in_two_installments_needs_no_hardship():
    partial = build_partial(48500, 9000, TODAY, TODAY, max_installment_cents=20000)
    assert len(partial.payments) == 3 and not requires_hardship(partial)


def test_altered_partial_installments_are_rejected():
    partial = build_partial(48500, 9000, TODAY, TODAY, max_installment_cents=10000)
    payments = list(partial.payments)
    payments[1] = replace(payments[1], amount_cents=payments[1].amount_cents + 100)
    payments[2] = replace(payments[2], amount_cents=payments[2].amount_cents - 100)
    altered = ArrangementProposal(ArrangementType.PARTIAL, 48500, tuple(payments))
    assert _violation(validate_proposal, altered, 48500, TODAY) is R.INVALID_SCHEDULE


# --- N8: el primer pago, hasta fin de mes (o fin del mes siguiente si faltan menos de 8 días) --

from cobranza.domain.arrangement import latest_first_payment_date  # noqa: E402


@pytest.mark.parametrize("today, latest", [
    (date(2026, 11, 12), date(2026, 11, 30)),   # faltan 18 días: fin de este mes
    (date(2026, 12, 8), date(2026, 12, 31)),
    (date(2027, 1, 23), date(2027, 1, 31)),     # justo 8 días
    (date(2027, 1, 27), date(2027, 2, 28)),     # faltan 4: fin del mes siguiente
    (date(2028, 1, 27), date(2028, 2, 29)),     # año bisiesto
    (date(2026, 12, 29), date(2027, 1, 31)),    # cambia de año
])
def test_latest_first_payment_date(today, latest):
    assert latest_first_payment_date(today) == latest


# --- N8: si el primer pago cae a fin de mes, todas las cuotas caen a fin de mes ------------

from cobranza.domain.arrangement import build_down_payment_plan as _down_plan, monthly_due_date  # noqa: E402


@pytest.mark.parametrize("first, months, due", [
    (date(2026, 11, 30), 1, date(2026, 12, 31)),   # fin de mes: siempre el último día
    (date(2026, 11, 30), 3, date(2027, 2, 28)),
    (date(2027, 2, 28), 12, date(2028, 2, 29)),     # año bisiesto
    (date(2026, 11, 13), 1, date(2026, 12, 13)),   # otro día: el mismo día de cada mes
    (date(2027, 1, 30), 1, date(2027, 2, 28)),
])
def test_monthly_due_date(first, months, due):
    assert monthly_due_date(first, months) == due


def test_plan_starting_at_the_end_of_the_month_stays_at_the_end_of_each_month():
    plan = build_plan(BALANCE, 4, date(2026, 11, 30), date(2026, 11, 13))
    assert [p.due_date for p in plan.payments] == [date(2026, 11, 30), date(2026, 12, 31),
                                                   date(2027, 1, 31), date(2027, 2, 28)]


def test_down_payment_plan_and_partial_also_follow_the_end_of_the_month():
    plan = _down_plan(48500, date(2026, 11, 30), date(2026, 11, 13))
    assert plan.payments[1].due_date == date(2026, 12, 31) and plan.payments[-1].due_date == date(2027, 11, 30)
    partial = build_partial(48500, 9000, date(2026, 11, 30), date(2026, 11, 13), max_installment_cents=20000)
    assert [p.due_date for p in partial.payments[1:]] == [date(2026, 12, 31), date(2027, 1, 31)]


def test_a_month_end_plan_with_mid_month_installments_is_rejected():
    plan = build_plan(BALANCE, 2, date(2026, 11, 30), date(2026, 11, 13))
    altered = replace(plan, payments=(plan.payments[0], replace(plan.payments[1], due_date=date(2026, 12, 30))))
    assert _violation(validate_proposal, altered, BALANCE, date(2026, 11, 13)) is R.INVALID_SCHEDULE
