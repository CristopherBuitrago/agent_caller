"""Casos de uso de la Función 4, sin base de datos."""

from datetime import date, datetime, timedelta, timezone

import pytest

from cobranza.application.use_cases.lookup_debtor import GetDebtorByAccount
from cobranza.application.use_cases.negotiate_arrangement import (
    CreateArrangement,
    ProposeArrangement,
    ProposeNextOffer,
    ProposePartialPayment,
    RecordHardshipAssessment,
    RecordOfferResponse,
    UnknownProposalError,
    _ArrangementGate,
)
from cobranza.domain.arrangement import ArrangementRuleError, ArrangementType, RuleViolation as R
from cobranza.domain.call import CallDirection, CallRecord
from cobranza.domain.debtor import AccountSummary, DebtorSummary
from cobranza.domain.hardship import HARDSHIP_QUESTIONS, HardshipAnswers, HardshipDuration
from cobranza.domain.identity import CallVerificationState
from cobranza.infrastructure.repositories.in_memory_negotiation_log import InMemoryNegotiationLog
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


def _all_rejected_log():
    """Registro de una llamada donde el deudor ya rechazó las 11 ofertas (hasta el pago inicial + 12 cuotas)."""
    log = InMemoryNegotiationLog()
    for offer_number in range(1, 12):
        log.mark_rejected("c1", log.save("c1", "ACC-1", offer_number, None).id)
    return log


def _use_cases(debtor=None, calls=None, arrangements=None, clock=None, hardship_done=False, log=None):
    debtors = FakeDebtors(debtor or _debtor())
    arrangements = arrangements or FakeArrangements()
    gate = _ArrangementGate(calls or FakeCalls(), arrangements,
                            GetDebtorByAccount(debtors, PhonenumbersPhoneService()), clock or FixedClock(),
                            FakeHardships(hardship_done))
    return (ProposeArrangement(gate), ProposePartialPayment(gate, log or InMemoryNegotiationLog()),
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
    assert _use_cases(hardship_done=True)[0].execute("c1", "ACC-1", 12) is None


def test_offer_eleven_is_ten_percent_down_and_twelve_equal_monthly_payments():
    """N5: saldo de USD 1.000 -> 100 hoy y 12 cuotas de 75 (la primera lleva los centavos que sobran)."""
    plan = _use_cases(hardship_done=True)[0].execute("c1", "ACC-1", 11)
    assert plan.type is ArrangementType.PLAN and plan.total_amount_cents == 100000
    assert [p.amount_cents for p in plan.payments] == [10000] + [7500] * 12
    assert plan.payments[-1].due_date == TODAY.replace(year=TODAY.year + 1)   # justo 1 año


def test_offer_eleven_needs_hardship():
    assert _violation(_use_cases()[0].execute, "c1", "ACC-1", 11) is R.HARDSHIP_REQUIRED


@pytest.mark.parametrize("offer_number", [1, 2, 3])
def test_first_three_offers_do_not_need_hardship(offer_number):
    assert _use_cases()[0].execute("c1", "ACC-1", offer_number) is not None


@pytest.mark.parametrize("offer_number", [4, 10, 11])
def test_later_offers_need_hardship(offer_number):
    assert _violation(_use_cases()[0].execute, "c1", "ACC-1", offer_number) is R.HARDSHIP_REQUIRED


def test_regular_partial_can_be_offered_at_any_time():
    assert _use_cases()[1].execute("c1", "ACC-1", 10000) is not None


def test_last_resort_partial_needs_hardship():
    assert _violation(_use_cases(log=_all_rejected_log())[1].execute,
                      "c1", "ACC-1", 9999) is R.HARDSHIP_REQUIRED


def test_last_resort_partial_needs_all_offers_rejected_in_the_call_log():
    assert _violation(_use_cases(hardship_done=True)[1].execute,
                      "c1", "ACC-1", 9999) is R.OFFERS_NOT_EXHAUSTED
    partial = _use_cases(hardship_done=True, log=_all_rejected_log())[1]
    assert partial.execute("c1", "ACC-1", 9999) is not None


def test_create_also_checks_hardship():
    allowed = _use_cases(hardship_done=True, log=_all_rejected_log())
    long_plan = allowed[0].execute("c1", "ACC-1", 4)
    last_resort = allowed[1].execute("c1", "ACC-1", 5000).proposal
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
    partial = _use_cases()[1].execute("c1", "ACC-1", 70000).proposal
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


# --- el sistema elige la oferta y guarda lo que se presentó (paso 8) ------------

def _offer_flow(hardship_done=False):
    log = InMemoryNegotiationLog()
    propose, _, create, _, arrangements = _use_cases(hardship_done=hardship_done, log=log)
    return ProposeNextOffer(propose, log), RecordOfferResponse(log, create), arrangements


def test_next_offer_is_the_fastest_one_not_yet_rejected():
    next_offer, respond, _ = _offer_flow()
    first = next_offer.execute("c1", "ACC-1")
    assert first.offer_number == 1 and first.proposal.type is ArrangementType.FULL
    assert respond.execute("c1", first.id, accepted=False) is None
    second = next_offer.execute("c1", "ACC-1")
    assert second.offer_number == 2 and len(second.proposal.payments) == 2


def test_next_offer_after_three_rejections_needs_hardship():
    next_offer, respond, _ = _offer_flow()
    for _ in range(3):
        respond.execute("c1", next_offer.execute("c1", "ACC-1").id, accepted=False)
    assert _violation(next_offer.execute, "c1", "ACC-1") is R.HARDSHIP_REQUIRED


def test_no_offer_left_after_rejecting_all_eleven():
    next_offer, respond, _ = _offer_flow(hardship_done=True)
    for _ in range(10):
        respond.execute("c1", next_offer.execute("c1", "ACC-1").id, accepted=False)
    last = next_offer.execute("c1", "ACC-1")
    assert last.offer_number == 11 and len(last.proposal.payments) == 13   # N5: pago inicial + 12
    respond.execute("c1", last.id, accepted=False)
    assert next_offer.execute("c1", "ACC-1") is None


def test_accepting_creates_the_arrangement_with_the_saved_proposal():
    next_offer, respond, arrangements = _offer_flow()
    offer = next_offer.execute("c1", "ACC-1")
    assert respond.execute("c1", offer.id, accepted=True) == "arr-1"
    assert arrangements.created == [("c1", "acc-1", offer.proposal, "PTP")]


def test_unknown_or_already_rejected_proposals_cannot_be_answered():
    next_offer, respond, arrangements = _offer_flow()
    with pytest.raises(UnknownProposalError):
        respond.execute("c1", "P-made-up", accepted=True)
    offer = next_offer.execute("c1", "ACC-1")
    with pytest.raises(UnknownProposalError):
        respond.execute("other-call", offer.id, accepted=True)  # de otra llamada
    respond.execute("c1", offer.id, accepted=False)
    with pytest.raises(ValueError):
        respond.execute("c1", offer.id, accepted=True)
    assert arrangements.created == []


def test_rejections_count_per_call_and_account():
    log = InMemoryNegotiationLog()
    log.mark_rejected("c1", log.save("c1", "ACC-1", 1, None).id)
    log.mark_rejected("c1", log.save("c1", "ACC-2", 2, None).id)
    log.mark_rejected("c2", log.save("c2", "ACC-1", 3, None).id)
    log.mark_rejected("c1", log.save("c1", "ACC-1", None, None).id)  # parcial: no es oferta de cuotas
    assert log.rejected_offer_numbers("c1", "ACC-1") == {1}


# --- casos borde de ProposeNextOffer, ProposePartialPayment y RecordOfferResponse (2026-11-11)

def _log_size(log, call_id="c1"):
    return len(log._by_call.get(call_id, {}))


def test_next_offer_uses_the_requested_first_date_up_to_eight_days():
    next_offer, _, _ = _offer_flow()
    offer = next_offer.execute("c1", "ACC-1", TODAY + timedelta(days=8))
    assert offer.proposal.payments[0].due_date == TODAY + timedelta(days=8)


def test_next_offer_with_a_date_out_of_range_logs_nothing():
    log = InMemoryNegotiationLog()
    next_offer = ProposeNextOffer(_use_cases(log=log)[0], log)
    assert _violation(next_offer.execute, "c1", "ACC-1",
                      TODAY + timedelta(days=9)) is R.FIRST_PAYMENT_DATE_OUT_OF_RANGE
    assert _violation(next_offer.execute, "c1", "ACC-1",
                      TODAY - timedelta(days=1)) is R.FIRST_PAYMENT_DATE_OUT_OF_RANGE
    assert _log_size(log) == 0


@pytest.mark.parametrize("calls, violation", [
    (FakeCalls(consent=False), R.RECORDING_CONSENT_MISSING),
    (FakeCalls(verified=False), R.IDENTITY_NOT_VERIFIED),
])
def test_next_offer_needs_recording_and_verification_and_logs_nothing(calls, violation):
    log = InMemoryNegotiationLog()
    next_offer = ProposeNextOffer(_use_cases(calls=calls, log=log)[0], log)
    assert _violation(next_offer.execute, "c1", "ACC-1") is violation
    assert _log_size(log) == 0


def test_next_offer_does_not_advance_until_the_debtor_answers():
    next_offer, _, _ = _offer_flow()
    first = next_offer.execute("c1", "ACC-1")
    again = next_offer.execute("c1", "ACC-1")
    assert first.offer_number == again.offer_number == 1
    assert first.id != again.id


def test_next_offer_after_hardship_continues_with_four_installments():
    log = InMemoryNegotiationLog()
    hardships = FakeHardships()
    arrangements = FakeArrangements()
    gate = _ArrangementGate(FakeCalls(), arrangements,
                            GetDebtorByAccount(FakeDebtors(_debtor()), PhonenumbersPhoneService()),
                            FixedClock(), hardships)
    next_offer = ProposeNextOffer(ProposeArrangement(gate), log)
    respond = RecordOfferResponse(log, CreateArrangement(gate, arrangements))
    for _ in range(3):
        respond.execute("c1", next_offer.execute("c1", "ACC-1").id, accepted=False)
    assert _violation(next_offer.execute, "c1", "ACC-1") is R.HARDSHIP_REQUIRED
    hardships.done = True
    fourth = next_offer.execute("c1", "ACC-1")
    assert fourth.offer_number == 4 and len(fourth.proposal.payments) == 4
    assert respond.execute("c1", fourth.id, accepted=True) == "arr-1"


def test_no_more_offers_once_an_arrangement_exists():
    log = InMemoryNegotiationLog()
    arrangements = FakeArrangements()
    propose, _, create, _, _ = _use_cases(arrangements=arrangements, log=log)
    next_offer, respond = ProposeNextOffer(propose, log), RecordOfferResponse(log, create)
    respond.execute("c1", next_offer.execute("c1", "ACC-1").id, accepted=True)
    arrangements.active = True  # lo que queda en la base después de guardar
    assert _violation(next_offer.execute, "c1", "ACC-1") is R.ACTIVE_ARRANGEMENT_EXISTS


def test_partial_of_exactly_ten_percent_needs_no_hardship():
    partial = _use_cases()[1].execute("c1", "ACC-1", 10000)
    assert partial.offer_number is None
    assert [p.amount_cents for p in partial.proposal.payments] == [10000, 90000]


def test_partial_just_below_ten_percent_needs_hardship_first():
    assert _violation(_use_cases()[1].execute, "c1", "ACC-1", 9999) is R.HARDSHIP_REQUIRED


def test_partial_between_five_and_ten_percent_needs_all_offers_rejected():
    assert _violation(_use_cases(hardship_done=True)[1].execute, "c1", "ACC-1", 5000) is R.OFFERS_NOT_EXHAUSTED
    partial = _use_cases(hardship_done=True, log=_all_rejected_log())[1].execute("c1", "ACC-1", 5000)
    assert partial.proposal.payments[0].amount_cents == 5000


def test_partial_for_the_whole_balance_is_not_a_partial():
    assert _violation(_use_cases()[1].execute, "c1", "ACC-1", 100000) is R.AMOUNT_NOT_PARTIAL


def test_partial_remainder_defaults_to_thirty_days_after_the_first_payment():
    first_due = TODAY + timedelta(days=5)
    partial = _use_cases()[1].execute("c1", "ACC-1", 20000, first_due=first_due)
    assert [p.due_date for p in partial.proposal.payments] == [first_due, first_due + timedelta(days=30)]


def test_partial_remainder_cannot_go_past_thirty_days():
    use = _use_cases()[1]
    ok = use.execute("c1", "ACC-1", 20000, remainder_due=TODAY + timedelta(days=15))
    assert ok.proposal.payments[1].due_date == TODAY + timedelta(days=15)
    assert _violation(use.execute, "c1", "ACC-1", 20000,
                      remainder_due=TODAY + timedelta(days=31)) is R.REMAINDER_DATE_OUT_OF_RANGE


def test_partial_first_payment_cannot_go_past_eight_days():
    assert _violation(_use_cases()[1].execute, "c1", "ACC-1", 20000,
                      first_due=TODAY + timedelta(days=9)) is R.FIRST_PAYMENT_DATE_OUT_OF_RANGE


def test_rejected_partial_does_not_count_as_a_rejected_offer():
    log = InMemoryNegotiationLog()
    propose, partial_uc, create, _, _ = _use_cases(log=log)
    RecordOfferResponse(log, create).execute("c1", partial_uc.execute("c1", "ACC-1", 20000).id, accepted=False)
    assert ProposeNextOffer(propose, log).execute("c1", "ACC-1").offer_number == 1


def test_accepting_a_partial_saves_it_and_moves_the_account_to_ptp():
    log = InMemoryNegotiationLog()
    _, partial_uc, create, _, arrangements = _use_cases(log=log)
    partial = partial_uc.execute("c1", "ACC-1", 20000)
    assert RecordOfferResponse(log, create).execute("c1", partial.id, accepted=True) == "arr-1"
    assert arrangements.created == [("c1", "acc-1", partial.proposal, "PTP")]


def test_accepting_the_same_proposal_twice_creates_only_one_arrangement():
    log = InMemoryNegotiationLog()
    arrangements = FakeArrangements()
    propose, _, create, _, _ = _use_cases(arrangements=arrangements, log=log)
    offer = ProposeNextOffer(propose, log).execute("c1", "ACC-1")
    respond = RecordOfferResponse(log, create)
    respond.execute("c1", offer.id, accepted=True)
    arrangements.active = True
    assert _violation(respond.execute, "c1", offer.id, accepted=True) is R.ACTIVE_ARRANGEMENT_EXISTS
    assert len(arrangements.created) == 1


def test_cannot_accept_after_the_call_ended():
    log = InMemoryNegotiationLog()
    calls = FakeCalls()
    propose, _, create, _, arrangements = _use_cases(calls=calls, log=log)
    offer = ProposeNextOffer(propose, log).execute("c1", "ACC-1")
    calls.record = FakeCalls(open_call=False).record
    with pytest.raises(ValueError):
        RecordOfferResponse(log, create).execute("c1", offer.id, accepted=True)
    assert arrangements.created == []


def test_cannot_accept_if_the_balance_changed_after_the_offer():
    log = InMemoryNegotiationLog()
    propose, _, create, debtors, arrangements = _use_cases(log=log)
    offer = ProposeNextOffer(propose, log).execute("c1", "ACC-1")
    debtors.debtor = _debtor(balance=90000)
    assert _violation(RecordOfferResponse(log, create).execute, "c1", offer.id,
                      accepted=True) is R.TOTAL_DIFFERS_FROM_BALANCE
    assert arrangements.created == []


def test_a_rejected_offer_cannot_be_accepted_later_but_the_new_one_can():
    log = InMemoryNegotiationLog()
    propose, _, create, _, arrangements = _use_cases(log=log)
    next_offer, respond = ProposeNextOffer(propose, log), RecordOfferResponse(log, create)
    first = next_offer.execute("c1", "ACC-1")
    respond.execute("c1", first.id, accepted=False)
    second = next_offer.execute("c1", "ACC-1")
    with pytest.raises(ValueError):
        respond.execute("c1", first.id, accepted=True)
    assert respond.execute("c1", second.id, accepted=True) == "arr-1"
    assert arrangements.created[0][2] is second.proposal


# --- N4, opción A': el monto que dice el deudor salta ofertas, nunca las más bajas de cada etapa
# Saldo de prueba: USD 1.000 -> 1 pago de 1.000, 2 de 500, 3 de ~333, 4 de 250 ... 10 de 100.

def _skip_flow(hardship_done=False):
    log = InMemoryNegotiationLog()
    propose, partial, create, _, _ = _use_cases(hardship_done=hardship_done, log=log)
    return ProposeNextOffer(propose, log), RecordOfferResponse(log, create), partial, log


def test_offers_above_the_stated_amount_are_skipped_and_logged():
    next_offer, _, _, log = _skip_flow()
    offer = next_offer.execute("c1", "ACC-1", stated_max_payment_cents=60000)
    assert offer.offer_number == 2                                  # 1.000 se saltó; 500 cabe
    skipped = [p for p in log._by_call["c1"].values() if p.skip_reason]
    assert [p.offer_number for p in skipped] == [1] and "60000" in skipped[0].skip_reason
    assert log.rejected_offer_numbers("c1", "ACC-1") == {1}


def test_a_low_amount_never_skips_three_payments_or_the_hardship_questions():
    next_offer, respond, _, _ = _skip_flow()
    offer = next_offer.execute("c1", "ACC-1", stated_max_payment_cents=3000)   # "solo puedo $30"
    assert offer.offer_number == 3                                  # la más baja antes de Hardship
    respond.execute("c1", offer.id, accepted=False)
    assert _violation(next_offer.execute, "c1", "ACC-1", stated_max_payment_cents=3000) is R.HARDSHIP_REQUIRED


def test_after_hardship_the_amount_picks_the_fastest_plan_that_fits():
    next_offer, respond, _, _ = _skip_flow(hardship_done=True)
    respond.execute("c1", next_offer.execute("c1", "ACC-1", stated_max_payment_cents=3000).id, accepted=False)
    assert next_offer.execute("c1", "ACC-1", stated_max_payment_cents=15000).offer_number == 7  # 7 de ~143


def test_after_hardship_the_down_payment_plan_is_never_skipped_and_then_the_last_resort_partial_opens():
    next_offer, respond, partial, _ = _skip_flow(hardship_done=True)
    respond.execute("c1", next_offer.execute("c1", "ACC-1", stated_max_payment_cents=3000).id, accepted=False)
    last = next_offer.execute("c1", "ACC-1", stated_max_payment_cents=3000)
    assert last.offer_number == 11          # 4 a 10 se saltan; 100 hoy y 12 de 75 aunque dijo 30
    respond.execute("c1", last.id, accepted=False)
    assert next_offer.execute("c1", "ACC-1") is None
    assert partial.execute("c1", "ACC-1", 5000).proposal.payments[0].amount_cents == 5000  # 5%: último recurso


def test_a_skipped_offer_cannot_be_accepted():
    next_offer, respond, _, log = _skip_flow()
    next_offer.execute("c1", "ACC-1", stated_max_payment_cents=60000)
    skipped = next(p for p in log._by_call["c1"].values() if p.skip_reason)
    with pytest.raises(ValueError):
        respond.execute("c1", skipped.id, accepted=True)
