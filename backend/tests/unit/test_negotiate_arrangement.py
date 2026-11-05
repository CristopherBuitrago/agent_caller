"""Casos de uso de la Función 4, sin base de datos."""

from datetime import date, datetime, timedelta, timezone

import pytest

from cobranza.application.use_cases.lookup_debtor import GetDebtorByAccount
from cobranza.application.use_cases.negotiate_arrangement import (
    CreateArrangement,
    ProposeArrangement,
    ProposePartialPayment,
    RecordHardshipAssessment,
    _ArrangementGate,
)
from cobranza.domain.arrangement import ArrangementRuleError, ArrangementType, RuleViolation as R
from cobranza.domain.call import CallDirection, CallRecord
from cobranza.domain.debtor import AccountSummary, DebtorSummary
from cobranza.domain.hardship import HARDSHIP_QUESTIONS, HardshipAnswers, HardshipDuration
from cobranza.domain.identity import CallVerificationState
from cobranza.infrastructure.services.phonenumbers_phone_service import PhonenumbersPhoneService

NOW = datetime(2026, 11, 2, 15, 0, tzinfo=timezone.utc)
TODAY = NOW.date()


class FixedClock:
    def __init__(self, now=NOW):
        self._now = now

    def now(self):
        return self._now


def _debtor(status="NSF", disputed=False, do_not_call=False, balance=100000, tz="America/New_York"):
    account = AccountSummary(
        id="acc-1", external_id="ACC-1", creditor_name="Acme", account_number_masked="****0001",
        current_balance_cents=balance, status=status, payment_method="ACH", nsf_amount_cents=None,
        nsf_fee_cents=0, nsf_date=None, nsf_return_code=None, is_disputed=disputed,
    )
    return DebtorSummary(
        id="deb-1", external_id="DEB-1", first_name="Jane", last_name="Doe", phone_primary="+12125550100",
        us_state="NY", timezone=tz, timezone_inferred=False, do_not_call=do_not_call, accounts=(account,),
    )


class FakeDebtors:
    def __init__(self, debtor):
        self.debtor = debtor

    def get_by_account(self, account_external_id):
        return self.debtor if account_external_id == "ACC-1" else None


class FakeCalls:
    def __init__(self, consent=True, verified=True, verified_debtor="deb-1", open_call=True):
        self.record = CallRecord("c1", CallDirection.INBOUND, verified_debtor, None, consent,
                                 None if open_call else NOW)
        self.state = CallVerificationState(verified_debtor, 1, verified)

    def get(self, call_id):
        return self.record if call_id == "c1" else None

    def get_verification_state(self, call_id):
        return self.state if call_id == "c1" else None


class FakeArrangements:
    def __init__(self, active=False):
        self.active = active
        self.created = []

    def has_active_arrangement(self, account_id):
        return self.active

    def create(self, call_id, account_id, proposal, new_account_status):
        self.created.append((call_id, account_id, proposal, new_account_status))
        return "arr-1"


class FakeHardships:
    def __init__(self, done=False):
        self.done = done
        self.saved = []

    def save(self, call_id, debtor_id, answers):
        self.saved.append((call_id, debtor_id, answers))
        self.done = True

    def exists_for_call(self, call_id):
        return self.done


def _use_cases(debtor=None, calls=None, arrangements=None, clock=None, hardship_done=False):
    debtors = FakeDebtors(debtor or _debtor())
    arrangements = arrangements or FakeArrangements()
    gate = _ArrangementGate(calls or FakeCalls(), arrangements,
                            GetDebtorByAccount(debtors, PhonenumbersPhoneService()), clock or FixedClock(),
                            FakeHardships(hardship_done))
    return (ProposeArrangement(gate), ProposePartialPayment(gate),
            CreateArrangement(gate, arrangements), debtors, arrangements)


def _violation(fn, *args, **kwargs):
    with pytest.raises(ArrangementRuleError) as e:
        fn(*args, **kwargs)
    return e.value.violation


# --- orden de las ofertas -----------------------------------------------------

def test_offers_go_from_the_fastest_to_the_slowest():
    propose = _use_cases(hardship_done=True)[0]
    first = propose.execute("c1", "ACC-1", 1)
    assert first.type is ArrangementType.FULL
    for offer_number in range(2, 11):
        plan = propose.execute("c1", "ACC-1", offer_number)
        assert plan.type is ArrangementType.PLAN
        assert len(plan.payments) == offer_number


def test_after_the_last_offer_there_is_nothing_left():
    assert _use_cases(hardship_done=True)[0].execute("c1", "ACC-1", 11) is None


@pytest.mark.parametrize("offer_number", [1, 2, 3])
def test_first_three_offers_do_not_need_hardship(offer_number):
    assert _use_cases()[0].execute("c1", "ACC-1", offer_number) is not None


@pytest.mark.parametrize("offer_number", [4, 10, 11])
def test_later_offers_need_hardship(offer_number):
    assert _violation(_use_cases()[0].execute, "c1", "ACC-1", offer_number) is R.HARDSHIP_REQUIRED


def test_regular_partial_can_be_offered_at_any_time():
    assert _use_cases()[1].execute("c1", "ACC-1", 10000) is not None


def test_last_resort_partial_needs_hardship():
    assert _violation(_use_cases()[1].execute, "c1", "ACC-1", 9999,
                      all_offers_rejected=True) is R.HARDSHIP_REQUIRED


def test_last_resort_partial_needs_all_offers_rejected():
    partial = _use_cases(hardship_done=True)[1]
    assert _violation(partial.execute, "c1", "ACC-1", 9999) is R.OFFERS_NOT_EXHAUSTED
    assert partial.execute("c1", "ACC-1", 9999, all_offers_rejected=True) is not None


def test_create_also_checks_hardship():
    allowed = _use_cases(hardship_done=True)
    long_plan = allowed[0].execute("c1", "ACC-1", 4)
    last_resort = allowed[1].execute("c1", "ACC-1", 5000, all_offers_rejected=True)
    without_hardship = _use_cases()
    assert _violation(without_hardship[2].execute, "c1", "ACC-1", long_plan) is R.HARDSHIP_REQUIRED
    assert _violation(without_hardship[2].execute, "c1", "ACC-1", last_resort) is R.HARDSHIP_REQUIRED
    assert without_hardship[4].created == []


# --- Hardship Questions -------------------------------------------------------

def _record_hardship(calls=None):
    arrangements, hardships = FakeArrangements(), FakeHardships()
    gate = _ArrangementGate(calls or FakeCalls(), arrangements,
                            GetDebtorByAccount(FakeDebtors(_debtor()), PhonenumbersPhoneService()),
                            FixedClock(), hardships)
    return RecordHardshipAssessment(gate, hardships), hardships


def test_hardship_is_saved_for_the_verified_debtor():
    record, hardships = _record_hardship()
    answers = HardshipAnswers(situation_description="Lost a shift", situation_started="last month",
                              duration_type=HardshipDuration.TEMPORARY, household_support=False,
                              offered_amount_cents=5000)
    record.execute("c1", answers)
    assert hardships.saved == [("c1", "deb-1", answers)]


@pytest.mark.parametrize("calls, violation", [
    (FakeCalls(consent=False), R.RECORDING_CONSENT_MISSING),
    (FakeCalls(verified=False), R.IDENTITY_NOT_VERIFIED),
])
def test_hardship_needs_recording_and_verification(calls, violation):
    record, hardships = _record_hardship(calls)
    assert _violation(record.execute, "c1", HardshipAnswers()) is violation
    assert hardships.saved == []


def test_agent_only_has_the_five_questions_from_the_list():
    assert len(HARDSHIP_QUESTIONS) == 5


def test_offer_number_starts_at_one():
    with pytest.raises(ValueError):
        _use_cases()[0].execute("c1", "ACC-1", 0)


def test_first_due_defaults_to_today_and_can_be_up_to_eight_days():
    propose = _use_cases()[0]
    assert propose.execute("c1", "ACC-1", 1).payments[0].due_date == TODAY
    assert _violation(propose.execute, "c1", "ACC-1", 1, TODAY + timedelta(days=9)) \
        is R.FIRST_PAYMENT_DATE_OUT_OF_RANGE


def test_today_is_the_local_date_of_the_debtor():
    # 02:00 UTC del 3 de noviembre todavía es 2 de noviembre en Los Ángeles.
    late = FixedClock(datetime(2026, 11, 3, 2, 0, tzinfo=timezone.utc))
    propose = _use_cases(_debtor(tz="America/Los_Angeles"), clock=late)[0]
    assert propose.execute("c1", "ACC-1", 1).payments[0].due_date == date(2026, 11, 2)


# --- condiciones --------------------------------------------------------------

@pytest.mark.parametrize("calls, violation", [
    (FakeCalls(consent=None), R.RECORDING_CONSENT_MISSING),
    (FakeCalls(consent=False), R.RECORDING_CONSENT_MISSING),
    (FakeCalls(verified=False), R.IDENTITY_NOT_VERIFIED),
    (FakeCalls(verified_debtor="someone-else"), R.IDENTITY_NOT_VERIFIED),
])
def test_call_conditions_are_required(calls, violation):
    propose, partial, *_ = _use_cases(calls=calls)
    assert _violation(propose.execute, "c1", "ACC-1", 1) is violation
    assert _violation(partial.execute, "c1", "ACC-1", 50000) is violation


@pytest.mark.parametrize("debtor", [
    _debtor(status="PAID"),
    _debtor(status="PAYMENT_PLAN"),
    _debtor(disputed=True),
    _debtor(do_not_call=True),
])
def test_only_collectable_accounts_can_negotiate(debtor):
    assert _violation(_use_cases(debtor)[0].execute, "c1", "ACC-1", 1) is R.ACCOUNT_NOT_COLLECTABLE


def test_account_with_an_active_arrangement_cannot_negotiate_again():
    assert _violation(_use_cases(arrangements=FakeArrangements(active=True))[0].execute,
                      "c1", "ACC-1", 1) is R.ACTIVE_ARRANGEMENT_EXISTS


def test_unknown_or_closed_call_and_unknown_account_raise():
    propose = _use_cases()[0]
    with pytest.raises(ValueError):
        propose.execute("missing", "ACC-1", 1)
    with pytest.raises(ValueError):
        propose.execute("c1", "ACC-MISSING", 1)
    with pytest.raises(ValueError):
        _use_cases(calls=FakeCalls(open_call=False))[0].execute("c1", "ACC-1", 1)


# --- pago parcial y guardado --------------------------------------------------

def test_partial_uses_the_amount_of_the_debtor():
    partial = _use_cases()[1].execute("c1", "ACC-1", 70000)
    assert partial.type is ArrangementType.PARTIAL
    assert [p.amount_cents for p in partial.payments] == [70000, 30000]


def test_partial_below_floor_is_rejected():
    assert _violation(_use_cases()[1].execute, "c1", "ACC-1", 4999) is R.AMOUNT_BELOW_FLOOR


def test_accepted_proposal_is_saved_and_moves_the_account_to_ptp():
    propose, _, create, _, arrangements = _use_cases()
    proposal = propose.execute("c1", "ACC-1", 2)
    assert create.execute("c1", "ACC-1", proposal) == "arr-1"
    assert arrangements.created == [("c1", "acc-1", proposal, "PTP")]


def test_active_arrangement_is_reported_even_if_the_account_is_already_in_ptp():
    use_cases = _use_cases(_debtor(status="PTP"), arrangements=FakeArrangements(active=True))
    assert _violation(use_cases[0].execute, "c1", "ACC-1", 1) is R.ACTIVE_ARRANGEMENT_EXISTS


def test_proposal_is_not_saved_if_the_balance_changed_after_offering_it():
    propose, _, create, debtors, arrangements = _use_cases()
    proposal = propose.execute("c1", "ACC-1", 2)
    debtors.debtor = _debtor(balance=90000)
    assert _violation(create.execute, "c1", "ACC-1", proposal) is R.TOTAL_DIFFERS_FROM_BALANCE
    assert arrangements.created == []
