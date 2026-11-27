"""Las herramientas del agente (CallTools), sin base de datos ni API de Claude.

La conversación con el modelo se prueba en agente/tests; aquí, solo las reglas de cada herramienta.
"""

import json
from datetime import date

import pytest

from cobranza.application.agent_tools import (
    DISCLOSURE,
    HUNG_UP_NEXT_STEP,
    TOOL_SPECS,
    AgentUseCases,
    CallTools,
    ToolCall,
)
from cobranza.application.interfaces.negotiation_log import LoggedProposal
from cobranza.domain.arrangement import (
    ArrangementProposal,
    ArrangementRuleError,
    ArrangementType,
    RuleViolation,
    ScheduledPayment,
)
from cobranza.domain.call import CallDirection, CallOutcome
from cobranza.domain.debtor import AccountSummary, DebtorSummary
from cobranza.domain.hardship import HARDSHIP_QUESTIONS, HardshipAnswerError
from cobranza.domain.identity import VerificationOutcome


# --- datos y dobles ---------------------------------------------------------------------

def _debtor(debtor_id="deb-1", first="Jane", last="Carter", status="NSF", return_code="NSF",
            payment_method="ACH"):
    account = AccountSummary(
        id=f"acc-{debtor_id}", external_id=f"ACC-{debtor_id}", creditor_name="Lakeside Auto Finance",
        account_number_masked="****4821", current_balance_cents=48500, status=status,
        payment_method=payment_method, nsf_amount_cents=45000, nsf_fee_cents=3500, nsf_date=date(2026, 10, 10),
        nsf_return_code=return_code, is_disputed=False,
    )
    return DebtorSummary(id=debtor_id, external_id="TEST-001", first_name=first, last_name=last,
                         phone_primary="+13055550001", us_state="FL", timezone="America/New_York",
                         timezone_inferred=False, do_not_call=False, accounts=(account,))


class Stub:
    """Caso de uso falso: guarda con qué se llamó y responde con `fn`."""

    def __init__(self, fn=None):
        self.calls = []
        self._fn = fn

    def execute(self, *args, **kwargs):
        self.calls.append(args + tuple(kwargs.values()))
        return self._fn(*args, **kwargs) if self._fn else None

    def questions_answered(self, call_id):
        return getattr(self, "answered", 0)

    def attempts_left(self, call_id, debtor_id):
        return getattr(self, "left", 1)

    def mismatched_items(self, debtor_id, full_name, ssn_last4, dob):
        return getattr(self, "mismatch", [])

    def identity_matches(self, debtor_id, ssn_last4, dob):
        return getattr(self, "identity_ok", True)

    def debtor_ids_with_identity(self, ssn_last4, dob):
        return getattr(self, "ids", [])


PLAN2 = ArrangementProposal(ArrangementType.PLAN, 48500, (
    ScheduledPayment(1, 24250, date(2026, 11, 13)), ScheduledPayment(2, 24250, date(2026, 12, 13))))


def _use_cases(debtors=(None,), verify=VerificationOutcome.VERIFIED, next_offer=None,
               last_contact=None):
    """Casos de uso falsos de las herramientas (también los usa test_api.py)."""
    debtors = [d or _debtor() for d in debtors]
    return AgentUseCases(
        find_debtors_by_phone=Stub(lambda phone: debtors),
        get_debtor_by_account=Stub(lambda account: debtors[0]),
        record_recording_consent=Stub(lambda call_id, accepted: accepted),
        verify_identity=Stub(lambda *a: verify),
        end_call=Stub(lambda call_id, outcome, transcript, **kw: "summary"),
        propose_next_offer=Stub(next_offer or (lambda *a: LoggedProposal("P1", "c1", a[1], 2, PLAN2))),
        propose_partial_payment=Stub(),
        record_offer_response=Stub(lambda call_id, proposal_id, accepted: "arr-1" if accepted else None),
        record_hardship_assessment=Stub(),
        record_dispute=Stub(lambda *a: "summary"),
        mark_do_not_call=Stub(lambda *a: "summary"),
        record_collection_hold=Stub(lambda *a: "summary"),
        get_last_contact=Stub(last_contact or (lambda *a: None)),
        schedule_callback=Stub(),
    )


def _tools(debtors=(None,), verify=VerificationOutcome.VERIFIED, next_offer=None, last_contact=None,
           direction=CallDirection.INBOUND):
    uc = _use_cases(debtors, verify, next_offer, last_contact)
    tools = CallTools(uc, "c1", direction, "+13055550001", None, transcript=lambda: "Agent: hi")
    return tools, uc


def _run(tools, name, **tool_input):
    result = tools.execute(ToolCall("t1", name, tool_input))
    return json.loads(result.content), result.is_error


VERIFY_JANE = {"full_name": "Jane Carter", "ssn_last4": "1234", "date_of_birth": "1985-03-14"}


# --- herramientas -------------------------------------------------------------------------

def test_every_tool_has_a_handler_and_a_closed_schema():
    tools, _ = _tools()
    for spec in TOOL_SPECS:
        assert hasattr(tools, f"_tool_{spec.name}"), spec.name
        assert spec.input_schema["additionalProperties"] is False


def test_account_details_need_verification_first():
    tools, _ = _tools()
    answer, is_error = _run(tools, "get_account_details")
    assert is_error and answer["error"] == "identity_not_verified"


def test_verified_caller_hears_the_disclosure_and_sees_only_safe_fields():
    tools, _ = _tools()
    answer, _ = _run(tools, "verify_identity", **VERIFY_JANE)
    assert answer["outcome"] == "verified" and DISCLOSURE in answer["next_step"]
    details, is_error = _run(tools, "get_account_details")
    assert not is_error
    account = details["accounts"][0]
    assert account["balance"] == "$485.00" and account["minimum_partial_payment"] == "$48.50"
    assert "1985" not in json.dumps(details) and "1234" not in json.dumps(details)


@pytest.mark.parametrize("code, method, reason", [
    ("NSF", "CARD", "there were not enough funds on your card"),
    ("nsf", "ACH", "there were not enough funds in your account"),
    ("NSF", "CHECK", "there were not enough funds in your account"),
])
def test_account_details_give_the_nsf_reason_as_a_fact(code, method, reason):
    tools, _ = _tools(debtors=(_debtor(return_code=code, payment_method=method),))
    _run(tools, "verify_identity", **VERIFY_JANE)
    details, _ = _run(tools, "get_account_details")
    assert details["accounts"][0]["returned_payment"]["reason"] == reason
    assert "NSF" not in json.dumps(details)
    assert "as a fact" in details["next_step"]


@pytest.mark.parametrize("code", ["R01", "R10", None])
def test_other_return_codes_give_no_reason_and_never_the_code(code):
    tools, _ = _tools(debtors=(_debtor(return_code=code),))
    _run(tools, "verify_identity", **VERIFY_JANE)
    details, _ = _run(tools, "get_account_details")
    assert "reason" not in details["accounts"][0]["returned_payment"]
    assert code is None or code not in json.dumps(details)
    assert "representative can give them the details" in details["next_step"]


def test_failed_verification_never_says_which_item_failed():
    tools, _ = _tools(verify=VerificationOutcome.FAILED)
    answer, _ = _run(tools, "verify_identity", **VERIFY_JANE)
    assert answer["outcome"] == "failed" and "without saying which item" in answer["next_step"]


def test_failed_verification_warns_when_it_is_the_last_attempt():
    tools, _ = _tools(verify=VerificationOutcome.FAILED)
    answer, _ = _run(tools, "verify_identity", **VERIFY_JANE)
    assert answer["attempts_left"] == 1
    assert "I can try one more time on this call" in answer["next_step"]
    assert "last attempt" not in answer["next_step"]          # sonaba a amenaza (prueba de voz, 2026-11-20)


def test_failed_verification_with_more_attempts_does_not_warn():
    tools, uc = _tools(verify=VerificationOutcome.FAILED)
    uc.verify_identity.left = 2
    answer, _ = _run(tools, "verify_identity", **VERIFY_JANE)
    assert answer["attempts_left"] == 2 and "last attempt" not in answer["next_step"]


def test_attempts_left_only_comes_with_a_failed_attempt():
    tools, _ = _tools(verify=VerificationOutcome.VERIFIED)
    answer, _ = _run(tools, "verify_identity", **VERIFY_JANE)
    assert "attempts_left" not in answer


def test_shared_phone_verifies_the_person_who_said_their_name():
    ana, luis = _debtor("deb-ana", "Ana", "Reyes"), _debtor("deb-luis", "Luis", "Reyes")
    tools, uc = _tools(debtors=(ana, luis))
    _run(tools, "verify_identity", full_name="Luis Reyes", ssn_last4="5555", date_of_birth="1989-02-28")
    assert uc.verify_identity.calls[0][1] == "deb-luis"


def test_unknown_phone_offers_a_representative():
    tools, uc = _tools()
    uc.find_debtors_by_phone._fn = lambda phone: []
    answer, _ = _run(tools, "verify_identity", **VERIFY_JANE)
    assert answer["outcome"] == "not_found" and "transfer_to_human" in answer["next_step"]


def test_bad_date_or_unknown_fields_ask_to_retry():
    tools, uc = _tools()
    answer, is_error = _run(tools, "verify_identity", full_name="Jane Carter", ssn_last4="1234",
                            date_of_birth="March 14")
    assert is_error and answer["error"] == "invalid_input"
    answer, is_error = _run(tools, "end_call", outcome="arrangement_made", discount=True)
    assert is_error and answer["error"] == "invalid_input"
    assert uc.verify_identity.calls == [] and uc.end_call.calls == []


def test_offers_come_from_the_system_with_spoken_amounts_and_dates():
    tools, _ = _tools()
    _run(tools, "verify_identity", **VERIFY_JANE)
    offer, _ = _run(tools, "propose_offer", account_ref="ACC-deb-1")
    assert offer["proposal_id"] == "P1" and offer["option"] == "2 equal monthly payments"
    assert offer["payments"][0] == {"number": 1, "amount": "$242.50", "date": "2026-11-13",
                                    "date_spoken": "Friday, November 13, 2026"}


def test_offers_only_for_accounts_of_the_verified_debtor():
    tools, uc = _tools()
    _run(tools, "verify_identity", **VERIFY_JANE)
    answer, is_error = _run(tools, "propose_offer", account_ref="ACC-SOMEONE-ELSE")
    assert is_error and uc.propose_next_offer.calls == []


def test_rule_errors_come_with_the_next_step():
    def needs_hardship(*a):
        raise ArrangementRuleError(RuleViolation.HARDSHIP_REQUIRED)
    tools, _ = _tools(next_offer=needs_hardship)
    _run(tools, "verify_identity", **VERIFY_JANE)
    answer, is_error = _run(tools, "propose_offer", account_ref="ACC-deb-1")
    assert is_error and answer["error"] == "hardship_required"
    assert "record_hardship_answers" in answer["next_step"]
    assert HARDSHIP_QUESTIONS[0] in answer["next_step"] and "question_number 1" in answer["next_step"]


def test_arrangement_made_only_after_an_accepted_offer():
    tools, uc = _tools()
    _run(tools, "verify_identity", **VERIFY_JANE)
    answer, is_error = _run(tools, "end_call", outcome="arrangement_made")
    assert is_error and not tools.ended
    offer, _ = _run(tools, "propose_offer", account_ref="ACC-deb-1")
    accepted, _ = _run(tools, "record_offer_response", proposal_id=offer["proposal_id"], accepted=True)
    assert accepted["arrangement_id"] == "arr-1"
    _run(tools, "end_call", outcome="arrangement_made")
    assert tools.ended and tools.outcome is CallOutcome.ARRANGEMENT_MADE
    assert uc.end_call.calls == [("c1", CallOutcome.ARRANGEMENT_MADE, "Agent: hi")]


def test_no_tools_after_the_call_ended():
    tools, uc = _tools()
    _run(tools, "transfer_to_human", reason="asked for a person")
    answer, is_error = _run(tools, "mark_do_not_call")
    assert is_error and answer["error"] == "call_ended" and uc.mark_do_not_call.calls == []


def test_without_recording_consent_the_call_can_only_end_as_refused():
    tools, uc = _tools()
    _run(tools, "record_recording_consent", accepted=False)
    _run(tools, "record_recording_consent", accepted=False)    # la repite después de la explicación
    _, is_error = _run(tools, "transfer_to_human", reason="x")
    assert is_error and not tools.ended
    tools.close_without_model(CallOutcome.TRANSFERRED_TO_HUMAN)
    assert tools.outcome is CallOutcome.RECORDING_REFUSED


# --- B9: next_step que no cubrían casos reales --------------------------------------------

def test_declined_offer_uses_the_amount_the_debtor_gave():
    tools, _ = _tools()
    answer, _ = _run(tools, "record_offer_response", proposal_id="P1", accepted=False)
    assert "propose_partial_payment" in answer["next_step"] and "propose_offer" in answer["next_step"]


def test_account_details_leave_the_offer_for_the_next_turn():
    tools, _ = _tools()
    _run(tools, "verify_identity", **VERIFY_JANE)
    details, _ = _run(tools, "get_account_details")
    assert "Would you like to take care of it today?" in details["next_step"]
    assert "only after they answer" in details["next_step"]


@pytest.mark.parametrize("tool, args", [
    ("mark_do_not_call", {}), ("end_call", {"outcome": "callback_requested"}),
])
def test_after_hang_up_no_tool_asks_the_agent_to_speak(tool, args):
    tools, _ = _tools()
    tools.caller_hung_up = True
    answer, _ = _run(tools, tool, **args)
    assert answer["next_step"] == HUNG_UP_NEXT_STEP
    assert "goodbye" not in answer["next_step"].lower()


# --- N4, opción A': monto que dice el deudor y "opción más baja disponible" ---------------

PLAN3 = ArrangementProposal(ArrangementType.PLAN, 48500, (
    ScheduledPayment(1, 16168, date(2026, 11, 13)), ScheduledPayment(2, 16166, date(2026, 12, 13)),
    ScheduledPayment(3, 16166, date(2027, 1, 13))))
def test_propose_offer_passes_the_stated_amount_and_flags_the_lowest_option():
    tools, uc = _tools(next_offer=lambda *a: LoggedProposal("P3", "c1", a[1], 3, PLAN3))
    _run(tools, "record_recording_consent", accepted=True)
    _run(tools, "verify_identity", **VERIFY_JANE)
    result, is_error = _run(tools, "propose_offer", account_ref="ACC-deb-1", max_payment_dollars=30)
    assert not is_error and result["lowest_option_available_now"] is True
    assert "Do not mention any minimum percentage" in result["next_step"]
    assert uc.propose_next_offer.calls[-1][-1] == 3000


def test_regular_offers_are_not_flagged_as_lowest():
    tools, _ = _tools()                                  # el doble devuelve la oferta de 2 cuotas
    _run(tools, "record_recording_consent", accepted=True)
    _run(tools, "verify_identity", **VERIFY_JANE)
    result, _ = _run(tools, "propose_offer", account_ref="ACC-deb-1")
    assert "lowest_option_available_now" not in result


def test_down_payment_plan_is_described_as_first_payment_and_monthly_payments():
    from cobranza.domain.arrangement import build_down_payment_plan
    plan = build_down_payment_plan(48500, date(2026, 11, 13), date(2026, 11, 13))
    tools, _ = _tools(next_offer=lambda *a: LoggedProposal("P11", "c1", a[1], 11, plan))
    _run(tools, "record_recording_consent", accepted=True)
    _run(tools, "verify_identity", **VERIFY_JANE)
    result, _ = _run(tools, "propose_offer", account_ref="ACC-deb-1")
    assert result["option"] == "a first payment now and then 12 equal monthly payments"
    assert result["payments"][0]["amount"] == "$48.50" and result["lowest_option_available_now"] is True


def test_no_offers_left_transfers_to_a_person():
    tools, _ = _tools(next_offer=lambda *a: None)
    _run(tools, "record_recording_consent", accepted=True)
    _run(tools, "verify_identity", **VERIFY_JANE)
    result, _ = _run(tools, "propose_offer", account_ref="ACC-deb-1")
    assert result["offers_exhausted"] is True and "transfer_to_human" in result["next_step"]


def test_partial_with_installments_is_described_and_passes_the_limit():
    from cobranza.domain.arrangement import build_partial
    partial = build_partial(48500, 9000, date(2026, 11, 13), date(2026, 11, 13), max_installment_cents=20000)
    tools, uc = _tools()
    uc.propose_partial_payment._fn = lambda *a: LoggedProposal("PP", "c1", a[1], None, partial)
    _run(tools, "record_recording_consent", accepted=True)
    _run(tools, "verify_identity", **VERIFY_JANE)
    result, is_error = _run(tools, "propose_partial_payment", account_ref="ACC-deb-1", amount_dollars=90,
                            max_payment_dollars=200)
    assert not is_error
    assert result["option"] == "a partial payment now and the rest in 2 equal monthly payments"
    assert uc.propose_partial_payment.calls[-1][-1] == 20000


# --- N8: la herramienta dice hasta cuándo puede ir el primer pago --------------------------

class _Clock:
    def __init__(self, now):
        self._now = now

    def now(self):
        return self._now


def _tools_on(day):
    from datetime import datetime, timezone
    tools, uc = _tools()
    tools._clock = _Clock(datetime(day.year, day.month, day.day, 17, 0, tzinfo=timezone.utc))
    _run(tools, "record_recording_consent", accepted=True)
    _run(tools, "verify_identity", **VERIFY_JANE)
    return tools


def test_offer_says_the_first_payment_can_wait_until_the_end_of_the_month():
    result, _ = _run(_tools_on(date(2026, 11, 12)), "propose_offer", account_ref="ACC-deb-1")
    assert result["latest_first_payment_date"] == "2026-12-02"
    assert result["first_payment_date_rule"].startswith("Try to get the first payment today.")
    assert "offer the last day of the month, Monday, November 30, 2026" in result["first_payment_date_rule"]
    assert "the latest possible date is Wednesday, December 2, 2026" in result["first_payment_date_rule"]


def test_near_the_end_of_the_month_it_asks_for_this_month_first():
    result, _ = _run(_tools_on(date(2027, 1, 27)), "propose_offer", account_ref="ACC-deb-1")
    assert result["latest_first_payment_date"] == "2027-03-02"
    rule = result["first_payment_date_rule"]
    assert (rule.index("Sunday, January 31, 2027") < rule.index("Sunday, February 28, 2027")
            < rule.index("Tuesday, March 2, 2027"))


# --- N12: número para devolver la llamada a quien no logra verificarse ---------------------

from cobranza.application.agent_tools import spoken_phone  # noqa: E402


@pytest.mark.parametrize("outcome", [VerificationOutcome.MAX_ATTEMPTS_REACHED,
                                     VerificationOutcome.IDENTITY_MISMATCH])
def test_failed_verification_offers_the_callback_number(outcome):
    tools, _ = _tools(verify=outcome)
    tools._callback_number = "+18005550199"
    _run(tools, "record_recording_consent", accepted=True)
    result, _ = _run(tools, "verify_identity", **VERIFY_JANE)
    assert "call us back at 1-800-555-0199" in result["next_step"]
    assert "debt" in result["next_step"]                    # sigue diciendo "Do not mention any debt"


def test_without_a_configured_number_nothing_is_offered():
    tools, _ = _tools(verify=VerificationOutcome.MAX_ATTEMPTS_REACHED)
    _run(tools, "record_recording_consent", accepted=True)
    result, _ = _run(tools, "verify_identity", **VERIFY_JANE)
    assert "call us back" not in result["next_step"]


def test_other_outcomes_do_not_offer_the_number():
    tools, _ = _tools(verify=VerificationOutcome.FAILED)
    tools._callback_number = "+18005550199"
    _run(tools, "record_recording_consent", accepted=True)
    result, _ = _run(tools, "verify_identity", **VERIFY_JANE)
    assert "call us back" not in result["next_step"]


@pytest.mark.parametrize("raw, spoken", [("+18005550199", "1-800-555-0199"),
                                         ("3055550001", "305-555-0001"), ("ext 12", "ext 12")])
def test_spoken_phone(raw, spoken):
    assert spoken_phone(raw) == spoken


# --- N13: la fecha real de la última llamada -----------------------------------------------

def _verified_tools(last_contact):
    tools, uc = _tools(last_contact=last_contact)
    _run(tools, "record_recording_consent", accepted=True)
    _run(tools, "verify_identity", **VERIFY_JANE)
    return tools, uc


def test_last_contact_is_said_in_the_debtor_local_time():
    from datetime import datetime, timezone
    from cobranza.domain.call import LastContact
    when = datetime(2026, 11, 10, 20, 15, tzinfo=timezone.utc)            # 3:15 PM en Florida
    tools, uc = _verified_tools(lambda *a: LastContact(when, False))
    result, _ = _run(tools, "get_last_contact")
    assert "our last call was on Tuesday, November 10, 2026 at 3:15 PM." in result["next_step"]
    assert "arrangement" not in result["next_step"].split("Do not add")[0]
    assert uc.get_last_contact.calls == [("deb-1", "c1")]


def test_last_contact_with_an_arrangement_explains_why_we_call():
    from datetime import datetime, timezone
    from cobranza.domain.call import LastContact
    tools, _ = _verified_tools(lambda *a: LastContact(datetime(2026, 11, 10, 14, 0, tzinfo=timezone.utc), True))
    result, _ = _run(tools, "get_last_contact")
    assert "when we set up a payment arrangement; that's why we're following up" in result["next_step"]


def test_no_previous_call_is_never_invented():
    tools, _ = _verified_tools(None)
    result, _ = _run(tools, "get_last_contact")
    assert result["last_call"] is None and "don't see a previous call" in result["next_step"]


def test_last_contact_needs_verification():
    tools, uc = _tools()
    _, is_error = _run(tools, "get_last_contact")
    assert is_error and uc.get_last_contact.calls == []


# --- N7: una aceptación con duda no cierra el acuerdo ---------------------------------------

def test_record_offer_response_asks_for_a_clear_yes():
    spec = next(s for s in TOOL_SPECS if s.name == "record_offer_response")
    assert "only after a clear yes, without doubts or conditions" in spec.description


def test_doubtful_yes_flow_gets_a_new_offer_within_the_stated_amount():
    """El agente rechaza la oferta con duda y pide otra con el monto cómodo: el sistema la arma."""
    tools, uc = _tools()
    _run(tools, "record_recording_consent", accepted=True)
    _run(tools, "verify_identity", **VERIFY_JANE)
    first, _ = _run(tools, "propose_offer", account_ref="ACC-deb-1")
    _run(tools, "record_offer_response", proposal_id=first["proposal_id"], accepted=False)
    _run(tools, "propose_offer", account_ref="ACC-deb-1", max_payment_dollars=150)
    assert uc.record_offer_response.calls[-1][-1] is False
    assert uc.propose_next_offer.calls[-1][-1] == 15000


# --- N9 / B2: el agente guarda el día y la hora pedidos -------------------------------------

def test_schedule_callback_uses_the_debtor_local_time_and_closes_the_call():
    tools, uc = _tools()
    _run(tools, "record_recording_consent", accepted=True)
    _run(tools, "verify_identity", **VERIFY_JANE)
    result, is_error = _run(tools, "schedule_callback", date="2026-11-20", time="18:00", note="asked by debtor")
    assert not is_error and result["scheduled"] is True
    call_id, when, note = uc.schedule_callback.calls[0]
    assert (call_id, when.isoformat(), note) == ("c1", "2026-11-20T18:00:00-05:00", "asked by debtor")
    assert "Friday, November 20, 2026 at 6:00 PM" in result["next_step"]
    assert tools.ended and tools.outcome is CallOutcome.CALLBACK_REQUESTED


def test_invalid_callback_time_asks_for_another_one():
    from cobranza.domain.call import CallbackTimeError
    tools, uc = _tools()
    uc.schedule_callback._fn = lambda *a: (_ for _ in ()).throw(CallbackTimeError("outside_calling_hours"))
    _run(tools, "record_recording_consent", accepted=True)
    result, _ = _run(tools, "schedule_callback", date="2026-11-20", time="22:30")
    assert result["error"] == "invalid_callback_time" and not tools.ended


def test_bad_time_format_asks_to_retry():
    tools, _ = _tools()
    _, is_error = _run(tools, "schedule_callback", date="2026-11-20", time="six pm")
    assert is_error


# --- B3 / B4: acuerdo + transferencia y tercero que contesta ---------------------------------

def test_transfer_after_an_arrangement_keeps_arrangement_made_and_saves_the_reason():
    tools, uc = _tools()
    _run(tools, "record_recording_consent", accepted=True)
    _run(tools, "verify_identity", **VERIFY_JANE)
    offer, _ = _run(tools, "propose_offer", account_ref="ACC-deb-1")
    _run(tools, "record_offer_response", proposal_id=offer["proposal_id"], accepted=True)
    _run(tools, "transfer_to_human", reason="Debtor wants to know how to pay")
    assert tools.outcome is CallOutcome.ARRANGEMENT_MADE and tools.transferred
    assert uc.end_call.calls[-1][1:] == (CallOutcome.ARRANGEMENT_MADE, "Agent: hi", "Debtor wants to know how to pay")


def test_transfer_without_an_arrangement_saves_the_reason():
    tools, uc = _tools()
    _run(tools, "record_recording_consent", accepted=True)
    _run(tools, "transfer_to_human", reason="Debtor asked for a person")
    assert tools.outcome is CallOutcome.TRANSFERRED_TO_HUMAN
    assert uc.end_call.calls[-1][-1] == "Debtor asked for a person"


def test_third_party_can_close_as_debtor_unavailable():
    tools, _ = _tools(direction=CallDirection.OUTBOUND)
    result, is_error = _run(tools, "end_call", outcome="debtor_unavailable")
    assert not is_error and tools.outcome is CallOutcome.DEBTOR_UNAVAILABLE


# --- "contestó otra persona" solo en salientes y sin verificar (prueba con la API real) ------

@pytest.mark.parametrize("outcome", ["debtor_unavailable", "wrong_party"])
def test_third_party_outcomes_become_callback_on_inbound_calls(outcome):
    tools, _ = _tools()                                    # entrante
    _run(tools, "end_call", outcome=outcome)
    assert tools.outcome is CallOutcome.CALLBACK_REQUESTED


@pytest.mark.parametrize("outcome", ["debtor_unavailable", "wrong_party"])
def test_third_party_outcomes_become_callback_once_the_debtor_is_verified(outcome):
    tools, _ = _tools(direction=CallDirection.OUTBOUND)
    _run(tools, "verify_identity", **VERIFY_JANE)
    _run(tools, "end_call", outcome=outcome)
    assert tools.outcome is CallOutcome.CALLBACK_REQUESTED


@pytest.mark.parametrize("outcome", ["debtor_unavailable", "wrong_party"])
def test_third_party_outcomes_stay_on_outbound_calls_before_verification(outcome):
    tools, _ = _tools(direction=CallDirection.OUTBOUND)
    _run(tools, "end_call", outcome=outcome)
    assert tools.outcome is CallOutcome(outcome)


def test_invalid_verification_input_asks_for_the_data_and_does_not_count_the_name():
    outcomes = iter([VerificationOutcome.INVALID_INPUT, VerificationOutcome.FAILED])
    tools, uc = _tools()
    uc.verify_identity._fn = lambda *a: next(outcomes)
    answer, _ = _run(tools, "verify_identity", full_name="pending", ssn_last4="0000", date_of_birth="1900-01-01")
    assert answer["outcome"] == "invalid_input"
    assert "Never guess" in answer["next_step"] and "did not count as an attempt" in answer["next_step"]
    _run(tools, "verify_identity", **VERIFY_JANE)
    assert uc.verify_identity.calls[1][-1] == ()   # "pending" no quedó como nombre dado antes


# --- hallazgo 2 de las simulaciones con Haiku: frases exactas antes de verificar --------------

@pytest.mark.parametrize("outcome", [VerificationOutcome.MAX_ATTEMPTS_REACHED, VerificationOutcome.LOCKED,
                                     VerificationOutcome.IDENTITY_MISMATCH])
def test_closing_without_verification_gives_the_exact_sentence(outcome):
    tools, _ = _tools(verify=outcome)
    result, _ = _run(tools, "verify_identity", **VERIFY_JANE)
    assert "Say exactly" in result["next_step"] and "wasn't able to verify your identity" in result["next_step"]
    assert "not even to say you cannot discuss them" in result["next_step"]


@pytest.mark.parametrize("outcome", ["debtor_unavailable", "wrong_party"])
def test_third_party_goodbye_is_a_fixed_sentence(outcome):
    tools, _ = _tools(direction=CallDirection.OUTBOUND)
    result, _ = _run(tools, "end_call", outcome=outcome)
    assert 'Say exactly: "Thank you for your time. Goodbye."' in result["next_step"]


def test_callback_for_someone_not_verified_uses_the_fixed_sentence():
    tools, _ = _tools(direction=CallDirection.OUTBOUND)
    result, _ = _run(tools, "schedule_callback", date="2026-11-20", time="18:00", note="husband answered")
    assert "we'll try again on Friday, November 20, 2026 at 6:00 PM. Goodbye." in result["next_step"]
    assert "not even to say you cannot discuss them" in result["next_step"]


def test_callback_for_the_verified_debtor_keeps_the_normal_confirmation():
    tools, _ = _tools()
    _run(tools, "verify_identity", **VERIFY_JANE)
    result, _ = _run(tools, "schedule_callback", date="2026-11-20", time="18:00")
    assert result["next_step"].startswith("Confirm: \"We'll call back on")


# --- hallazgo 3: las Hardship Questions, una por una --------------------------------------------

def test_saving_a_hardship_answer_gives_the_next_question():
    tools, uc = _tools()
    uc.record_hardship_assessment._fn = lambda call_id, number, answers: number
    _run(tools, "verify_identity", **VERIFY_JANE)
    answer, is_error = _run(tools, "record_hardship_answers", question_number=1,
                            situation_description="Lost her job")
    assert not is_error and answer["questions_answered"] == 1
    assert HARDSHIP_QUESTIONS[1] in answer["next_step"] and "question_number 2" in answer["next_step"]
    call_id, number, answers = uc.record_hardship_assessment.calls[0]
    assert number == 1 and answers.situation_description == "Lost her job"


def test_the_fifth_answer_sends_the_agent_back_to_the_offers():
    tools, uc = _tools()
    uc.record_hardship_assessment._fn = lambda call_id, number, answers: 5
    _run(tools, "verify_identity", **VERIFY_JANE)
    answer, _ = _run(tools, "record_hardship_answers", question_number=5, arrangement_answer="30 a month")
    assert "call propose_offer" in answer["next_step"]
    assert uc.record_hardship_assessment.calls[0][2].arrangement_answer == "30 a month"


def test_a_skipped_hardship_question_is_not_saved_and_asks_the_right_one():
    tools, uc = _tools()

    def skipped(call_id, number, answers):
        raise HardshipAnswerError("Ask question 2 first")
    uc.record_hardship_assessment._fn = skipped
    uc.record_hardship_assessment.answered = 1
    _run(tools, "verify_identity", **VERIFY_JANE)
    answer, is_error = _run(tools, "record_hardship_answers", question_number=3, household_support=True)
    assert answer["error"] == "hardship_answer_not_saved"   # como invalid_callback_time: el modelo sigue
    assert HARDSHIP_QUESTIONS[1] in answer["next_step"]


def test_question_number_is_required():
    tools, _ = _tools()
    _run(tools, "verify_identity", **VERIFY_JANE)
    answer, is_error = _run(tools, "record_hardship_answers", situation_description="Lost her job")
    assert is_error


# --- hallazgo 4: no cerrar como "otra persona" a quien ya se trató como el deudor -------------

@pytest.mark.parametrize("outcome", ["debtor_unavailable", "wrong_party"])
def test_third_party_close_after_the_recording_notice_asks_to_confirm_first(outcome):
    tools, _ = _tools(direction=CallDirection.OUTBOUND)
    _run(tools, "record_recording_consent", accepted=True)     # solo se da si dijo ser el deudor
    first, _ = _run(tools, "end_call", outcome=outcome)
    assert first["error"] == "confirm_who_answered" and not tools.ended
    assert '"Am I speaking with Jane Carter?"' in first["next_step"]
    second, _ = _run(tools, "end_call", outcome=outcome)        # la persona dijo que no es
    assert second["ended"] is True and tools.outcome is CallOutcome(outcome)


# --- hallazgo 5: el agente sabe cómo se paga ----------------------------------------------------

def test_account_details_and_offers_explain_how_payments_work():
    tools, _ = _tools()
    _run(tools, "verify_identity", **VERIFY_JANE)
    details, _ = _run(tools, "get_account_details")
    offer, _ = _run(tools, "propose_offer", account_ref="ACC-deb-1")
    for result in (details, offer):
        assert "secure link to pay online" in result["how_payments_work"]
        assert "Nobody will call you to take the payment" in result["how_payments_work"]


def test_the_agreement_tells_the_debtor_how_payments_work():
    tools, _ = _tools()
    _run(tools, "verify_identity", **VERIFY_JANE)
    offer, _ = _run(tools, "propose_offer", account_ref="ACC-deb-1")
    accepted, _ = _run(tools, "record_offer_response", proposal_id=offer["proposal_id"], accepted=True)
    assert "reminder text" in accepted["next_step"] and "end_call" in accepted["next_step"]


# --- hallazgo 6: las herramientas que cierran la llamada lo avisan --------------------------------

@pytest.mark.parametrize("tool, args", [
    ("record_dispute", {"account_ref": "ACC-deb-1"}),
    ("mark_do_not_call", {}),
    ("schedule_callback", {"date": "2026-11-20", "time": "18:00"}),
])
def test_tools_that_close_the_call_say_not_to_close_it_again(tool, args):
    tools, _ = _tools()
    _run(tools, "verify_identity", **VERIFY_JANE)
    result, _ = _run(tools, tool, **args)
    assert "do not call end_call" in result["next_step"] and tools.ended


def test_how_payments_work_only_promises_the_reminder_for_payments_far_enough_away():
    tools, _ = _tools()
    _run(tools, "verify_identity", **VERIFY_JANE)
    details, _ = _run(tools, "get_account_details")
    assert "at least three days away" in details["how_payments_work"]


# --- prueba de ataque: casos legales ---------------------------------------------------------

@pytest.mark.parametrize("reason, sentence", [
    ("attorney", "We'll contact your attorney from now on."),
    ("bankruptcy", "We'll stop collection activity while a representative reviews it."),
    ("deceased", "I'm sorry for your loss. We'll update our records."),
])
def test_a_legal_hold_closes_the_call_with_its_fixed_sentence(reason, sentence):
    tools, uc = _tools(direction=CallDirection.OUTBOUND)
    result, is_error = _run(tools, "record_collection_hold", reason=reason, details="details")
    assert not is_error and sentence in result["next_step"] and "do not call end_call" in result["next_step"]
    assert tools.ended and tools.outcome is CallOutcome.COLLECTION_HOLD
    assert uc.record_collection_hold.calls[0][1].value == reason


def test_an_unknown_legal_hold_reason_is_rejected():
    tools, _ = _tools(direction=CallDirection.OUTBOUND)
    result, is_error = _run(tools, "record_collection_hold", reason="vacation")
    assert is_error and not tools.ended


# --- varias deudas: después de un acuerdo, la siguiente cuenta (prueba por celular, 2026-11-19) --

def _debtor_with_two_accounts():
    from dataclasses import replace
    debtor = _debtor()
    second = replace(debtor.accounts[0], id="acc-2", external_id="ACC-2", creditor_name="Brightwater Utilities",
                     current_balance_cents=20500)
    return replace(debtor, accounts=debtor.accounts + (second,))


def _accept_offer_for(tools, account_ref):
    offer, _ = _run(tools, "propose_offer", account_ref=account_ref)
    answer, is_error = _run(tools, "record_offer_response", proposal_id=offer["proposal_id"], accepted=True)
    assert not is_error
    return answer


def test_after_an_arrangement_the_agent_offers_the_next_debt():
    tools, _ = _tools(debtors=(_debtor_with_two_accounts(),))
    _run(tools, "record_recording_consent", accepted=True)
    _run(tools, "verify_identity", **VERIFY_JANE)
    first = _accept_offer_for(tools, "ACC-deb-1")
    assert [a["account_ref"] for a in first["other_accounts"]] == ["ACC-2"]
    assert "Brightwater Utilities balance of $205.00" in first["next_step"]
    assert "propose_offer with account_ref ACC-2" in first["next_step"]
    second = _accept_offer_for(tools, "ACC-2")
    assert "other_accounts" not in second
    assert "end_call with outcome arrangement_made" in second["next_step"]


def test_with_a_single_debt_the_agent_goes_straight_to_the_goodbye():
    tools, _ = _tools()
    _run(tools, "record_recording_consent", accepted=True)
    _run(tools, "verify_identity", **VERIFY_JANE)
    answer = _accept_offer_for(tools, "ACC-deb-1")
    assert "other_accounts" not in answer and "they also have" not in answer["next_step"]


def test_with_several_debts_the_agent_announces_the_order_oldest_first():
    from dataclasses import replace
    debtor = _debtor_with_two_accounts()
    newer, older = debtor.accounts[0], replace(debtor.accounts[1], nsf_date=date(2026, 9, 1))
    tools, _ = _tools(debtors=(replace(debtor, accounts=(newer, older)),))
    _run(tools, "record_recording_consent", accepted=True)
    _run(tools, "verify_identity", **VERIFY_JANE)
    details, _ = _run(tools, "get_account_details")
    assert [a["account_ref"] for a in details["accounts"]] == ["ACC-2", "ACC-deb-1"]
    step = details["next_step"]
    assert "start with the Brightwater Utilities balance and then look at Lakeside Auto Finance" in step
    assert "propose_offer with account_ref ACC-2" in step


def test_with_one_debt_there_is_no_order_to_announce():
    tools, _ = _tools()
    _run(tools, "record_recording_consent", accepted=True)
    _run(tools, "verify_identity", **VERIFY_JANE)
    details, _ = _run(tools, "get_account_details")
    assert "start with the" not in details["next_step"]
    assert "Would you like to take care of it today?" in details["next_step"]


def test_a_requested_number_of_payments_leads_to_the_monthly_amount_question():
    tools, _ = _tools()
    answer, _ = _run(tools, "record_offer_response", proposal_id="P1", accepted=False)
    assert "If they asked for a number of payments" in answer["next_step"]
    assert "How much could you comfortably pay each month?" in answer["next_step"]


def test_an_unclear_answer_about_the_next_debt_is_confirmed():
    tools, _ = _tools(debtors=(_debtor_with_two_accounts(),))
    _run(tools, "record_recording_consent", accepted=True)
    _run(tools, "verify_identity", **VERIFY_JANE)
    first = _accept_offer_for(tools, "ACC-deb-1")
    assert "Should we leave the Brightwater Utilities balance for another time?" in first["next_step"]


# --- demo en el navegador: entrante sin teléfono, se busca por el nombre (2026-11-22) -------------

def _tools_by_name(lookup_by_name, by_name):
    from dataclasses import replace
    uc = replace(_use_cases(), find_debtors_by_phone=Stub(lambda phone: []),
                 find_debtors_by_name=Stub(lambda name: by_name))
    return CallTools(uc, "c1", CallDirection.INBOUND, "+10000000000", None, transcript=lambda: "",
                     lookup_by_name=lookup_by_name), uc


def test_demo_inbound_finds_the_debtor_by_the_spoken_name():
    tools, uc = _tools_by_name(True, [_debtor()])
    answer, _ = _run(tools, "verify_identity", **VERIFY_JANE)
    assert answer["outcome"] == "verified"
    assert uc.find_debtors_by_name.calls == [("Jane Carter",)]


def test_without_the_demo_switch_an_unknown_phone_finds_nobody():
    tools, uc = _tools_by_name(False, [_debtor()])
    answer, _ = _run(tools, "verify_identity", **VERIFY_JANE)
    assert answer["outcome"] == "not_found" and uc.find_debtors_by_name.calls == []


# --- antes del último intento, solo lo que no coincidió (decisión del usuario, 2026-11-22) ---------

def test_last_attempt_confirms_the_ssn_heard_and_asks_only_the_birth_date():
    tools, uc = _tools(verify=VerificationOutcome.FAILED)
    uc.verify_identity.mismatch = ["ssn_last4", "date_of_birth"]
    answer, _ = _run(tools, "verify_identity", **VERIFY_JANE)
    assert answer["mismatched"] == ["ssn_last4", "date_of_birth"]
    step = answer["next_step"]
    assert "are the last four digits of your Social Security number 1 2 3 4?" in step
    assert "Could you tell me your date of birth again?" in step
    assert "Do not ask again for the other items" in step and "spell" not in step


def test_last_attempt_with_only_the_date_wrong_asks_only_the_date():
    tools, uc = _tools(verify=VerificationOutcome.FAILED)
    uc.verify_identity.mismatch = ["date_of_birth"]
    step = _run(tools, "verify_identity", **VERIFY_JANE)[0]["next_step"]
    assert "date of birth" in step and "Social Security" not in step


# --- primero SSN y fecha, después "Am I speaking with ...?" (usuario, 2026-11-22) --------------------

SSN_DOB = {"ssn_last4": "1234", "date_of_birth": "1985-03-14"}


def test_verify_identity_needs_only_ssn_and_date():
    spec = next(s for s in TOOL_SPECS if s.name == "verify_identity")
    assert spec.input_schema["required"] == ["ssn_last4", "date_of_birth"]


def test_ssn_and_date_lead_to_the_name_confirmation_then_verification():
    tools, uc = _tools(verify=VerificationOutcome.VERIFIED)
    _run(tools, "record_recording_consent", accepted=True)
    answer, _ = _run(tools, "verify_identity", **SSN_DOB)
    assert answer["outcome"] == "confirm_name" and answer["debtor_name"] == "Jane Carter"
    assert "Am I speaking with Jane Carter?" in answer["next_step"]
    assert uc.verify_identity.calls == []                       # todavía no cuenta como intento
    verified, _ = _run(tools, "confirm_identity", confirmed=True)
    assert verified["outcome"] == "verified"
    assert uc.verify_identity.calls[0][2:5] == ("Jane Carter", "1234", date(1985, 3, 14))


def test_saying_no_to_the_name_asks_for_the_full_name():
    tools, uc = _tools()
    _run(tools, "verify_identity", **SSN_DOB)
    answer, _ = _run(tools, "confirm_identity", confirmed=False)
    assert "Ask for their full name" in answer["next_step"] and uc.verify_identity.calls == []


def test_ssn_and_date_that_do_not_match_count_as_a_failed_attempt():
    tools, uc = _tools(verify=VerificationOutcome.FAILED)
    uc.verify_identity.identity_ok = False
    answer, _ = _run(tools, "verify_identity", **SSN_DOB)
    assert answer["outcome"] == "failed" and len(uc.verify_identity.calls) == 1


def test_confirm_without_a_pending_name_is_an_error():
    tools, _ = _tools()
    answer, is_error = _run(tools, "confirm_identity", confirmed=True)
    assert is_error and answer["error"] == "invalid_input"


def test_outbound_skips_the_name_question():
    tools, uc = _tools(direction=CallDirection.OUTBOUND)
    answer, _ = _run(tools, "verify_identity", **SSN_DOB)
    assert answer["outcome"] == "verified" and len(uc.verify_identity.calls) == 1


def test_demo_without_phone_finds_the_debtor_by_ssn_and_date():
    from dataclasses import replace
    uc = replace(_use_cases(), find_debtors_by_phone=Stub(lambda phone: []),
                 get_debtor_by_id=Stub(lambda debtor_id: _debtor()))
    uc.verify_identity.ids = ["deb-1"]
    tools = CallTools(uc, "c1", CallDirection.INBOUND, "+10000000000", None, transcript=lambda: "",
                      lookup_by_name=True)
    answer, _ = _run(tools, "verify_identity", **SSN_DOB)
    assert answer["outcome"] == "confirm_name" and answer["debtor_name"] == "Jane Carter"


def test_a_first_refusal_is_not_saved_until_the_caller_repeats_it():
    """Prueba de voz (2026-11-22): el modelo cerró como recording_refused a un deudor molesto."""
    tools, uc = _tools()
    first, _ = _run(tools, "record_recording_consent", accepted=False)
    assert first["recorded"] is False and "May we continue?" in first["next_step"]
    assert uc.record_recording_consent.calls == [] and not tools.ended
    second, _ = _run(tools, "record_recording_consent", accepted=False)
    assert second["recorded"] is True and "recording_refused" in second["next_step"]
