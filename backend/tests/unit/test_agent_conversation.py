"""Paso 8: la conversación y las herramientas del agente, sin base de datos ni API de Claude."""

import json
from datetime import date
from types import SimpleNamespace

import anthropic
import pytest

from cobranza.agent.application.conversation_model import (
    ConversationModelError,
    ModelTurn,
    ToolCall,
    ToolSpec,
)
from cobranza.application.interfaces.negotiation_log import LoggedProposal
from cobranza.agent.application.conversation import (
    FALLBACK_TEXT,
    MAX_TOOL_ROUNDS_PER_TURN,
    AgentSession,
    render_system_prompt,
)
from cobranza.agent.application.tools import DISCLOSURE, TOOL_SPECS, AgentUseCases, CallTools
from cobranza.domain.arrangement import (
    ArrangementProposal,
    ArrangementRuleError,
    ArrangementType,
    RuleViolation,
    ScheduledPayment,
)
from cobranza.domain.call import CallDirection, CallOutcome
from cobranza.domain.debtor import AccountSummary, DebtorSummary
from cobranza.domain.hardship import HARDSHIP_QUESTIONS
from cobranza.domain.identity import VerificationOutcome
from cobranza.agent.infrastructure.claude_conversation_model import ClaudeConversationModel


# --- datos y dobles ---------------------------------------------------------------------

def _debtor(debtor_id="deb-1", first="Jane", last="Carter", status="NSF"):
    account = AccountSummary(
        id=f"acc-{debtor_id}", external_id=f"ACC-{debtor_id}", creditor_name="Lakeside Auto Finance",
        account_number_masked="****4821", current_balance_cents=48500, status=status,
        payment_method="ACH", nsf_amount_cents=45000, nsf_fee_cents=3500, nsf_date=date(2026, 10, 10),
        nsf_return_code="R01", is_disputed=False,
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


PLAN2 = ArrangementProposal(ArrangementType.PLAN, 48500, (
    ScheduledPayment(1, 24250, date(2026, 11, 13)), ScheduledPayment(2, 24250, date(2026, 12, 13))))


def _tools(debtors=(None,), verify=VerificationOutcome.VERIFIED, next_offer=None,
           direction=CallDirection.INBOUND):
    debtors = [d or _debtor() for d in debtors]
    uc = AgentUseCases(
        find_debtors_by_phone=Stub(lambda phone: debtors),
        get_debtor_by_account=Stub(lambda account: debtors[0]),
        record_recording_consent=Stub(lambda call_id, accepted: accepted),
        verify_identity=Stub(lambda *a: verify),
        end_call=Stub(lambda call_id, outcome, transcript: "summary"),
        propose_next_offer=Stub(next_offer or (lambda *a: LoggedProposal("P1", "c1", a[1], 2, PLAN2))),
        propose_partial_payment=Stub(),
        record_offer_response=Stub(lambda call_id, proposal_id, accepted: "arr-1" if accepted else None),
        record_hardship_assessment=Stub(),
        record_dispute=Stub(lambda *a: "summary"),
        mark_do_not_call=Stub(lambda *a: "summary"),
    )
    tools = CallTools(uc, "c1", direction, "+13055550001", None, transcript=lambda: "Agent: hi")
    return tools, uc


def _run(tools, name, **tool_input):
    result = tools.execute(ToolCall("t1", name, tool_input))
    return json.loads(result.content), result.is_error


VERIFY_JANE = {"full_name": "Jane Carter", "ssn_last4": "1234", "date_of_birth": "1985-03-14"}


class ScriptedModel:
    """Modelo falso: responde los turnos en el orden dado y guarda lo que recibió."""

    def __init__(self, *turns):
        self.turns = list(turns)
        self.received = []

    def start(self, system_prompt, tools):
        return self

    def send_user_text(self, text):
        self.received.append(text)
        return self._next()

    def send_tool_results(self, results):
        self.received.append(results)
        return self._next()

    def _next(self):
        turn = self.turns.pop(0)
        if isinstance(turn, Exception):
            raise turn
        return turn


def _say(text, *calls):
    return ModelTurn(text, tuple(ToolCall(f"t{i}", name, args) for i, (name, args) in enumerate(calls)))


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


def test_failed_verification_never_says_which_item_failed():
    tools, _ = _tools(verify=VerificationOutcome.FAILED)
    answer, _ = _run(tools, "verify_identity", **VERIFY_JANE)
    assert answer["outcome"] == "failed" and "without saying which item" in answer["next_step"]


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
    _, is_error = _run(tools, "transfer_to_human", reason="x")
    assert is_error and not tools.ended
    tools.close_without_model(CallOutcome.TRANSFERRED_TO_HUMAN)
    assert tools.outcome is CallOutcome.RECORDING_REFUSED


# --- sesión -------------------------------------------------------------------------------

def test_session_runs_the_tools_and_joins_the_agent_text():
    tools, _ = _tools()
    seen = []
    model = ScriptedModel(
        _say("One moment.", ("record_recording_consent", {"accepted": True})),
        _say("Thanks. Can I have your full name?"),
    )
    session = AgentSession(tools, model, on_tool=lambda call, result: seen.append(call.name))
    reply = session.debtor_says("Yes, that's fine")
    assert reply.text == "One moment. Thanks. Can I have your full name?" and not reply.call_ended
    assert seen == ["record_recording_consent"]
    assert session.transcript() == ("Debtor: Yes, that's fine\n"
                                    "Agent: One moment. Thanks. Can I have your full name?")


def test_model_failure_transfers_to_a_person():
    tools, uc = _tools()
    session = AgentSession(tools, ScriptedModel(ConversationModelError("down")))
    reply = session.debtor_says("hello")
    assert reply == type(reply)(FALLBACK_TEXT, True, CallOutcome.TRANSFERRED_TO_HUMAN)
    with pytest.raises(ValueError):
        session.debtor_says("hello?")


def test_endless_tool_loop_transfers_to_a_person():
    tools, _ = _tools()
    loop = [_say("", ("get_account_details", {}))] * (MAX_TOOL_ROUNDS_PER_TURN + 1)
    reply = AgentSession(tools, ScriptedModel(*loop)).debtor_says("hi")
    assert reply.call_ended and reply.outcome is CallOutcome.TRANSFERRED_TO_HUMAN


def test_hang_up_closes_the_call_even_if_the_model_does_not():
    tools, _ = _tools()
    session = AgentSession(tools, ScriptedModel(_say("")))
    session.hang_up()
    assert session.ended and session.outcome is CallOutcome.CALLBACK_REQUESTED


def test_system_prompt_has_no_placeholders_left():
    prompt = render_system_prompt("Lakeside Recovery Services")
    assert "{{" not in prompt and DISCLOSURE in prompt
    assert all(q in prompt for q in HARDSHIP_QUESTIONS)
    assert all(spec.name in prompt for spec in TOOL_SPECS)


# --- implementación con Claude (cliente falso) ---------------------------------------------

class FakeMessages:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.models = []

    def create(self, **request):
        self.models.append(request["model"])
        self.last_request = request
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _response(stop_reason="end_turn", *blocks):
    return SimpleNamespace(stop_reason=stop_reason, content=list(blocks))


def _text(text):
    return SimpleNamespace(type="text", text=text)


def _api_error():
    """Error de red de la API, sin depender del cliente HTTP que use el SDK por dentro."""
    error = anthropic.APIConnectionError.__new__(anthropic.APIConnectionError)
    Exception.__init__(error, "connection failed")
    return error


def _conversation(*responses):
    messages = FakeMessages(*responses)
    model = ClaudeConversationModel(SimpleNamespace(messages=messages), "primary", "backup")
    return model.start("system", [ToolSpec("end_call", "End", {"type": "object"})]), messages


def test_claude_turn_returns_text_and_tool_calls():
    conversation, messages = _conversation(_response(
        "tool_use", _text("One moment."),
        SimpleNamespace(type="tool_use", id="tu1", name="end_call", input={"outcome": "wrong_party"})))
    turn = conversation.send_user_text("hi")
    assert turn == ModelTurn("One moment.", (ToolCall("tu1", "end_call", {"outcome": "wrong_party"}),))
    assert messages.last_request["cache_control"] == {"type": "ephemeral"}
    assert messages.last_request["tools"][0]["name"] == "end_call"


def test_claude_uses_the_backup_when_the_primary_fails_or_refuses():
    conversation, messages = _conversation(_api_error(), _response("end_turn", _text("Hello")),
                                           _response("refusal"), _response("end_turn", _text("Sure")))
    assert conversation.send_user_text("hi").text == "Hello"
    assert conversation.send_user_text("ok").text == "Sure"
    assert messages.models == ["primary", "backup", "primary", "backup"]


def test_claude_tool_results_go_back_together_in_one_message():
    conversation, messages = _conversation(_response("end_turn", _text("a")), _response("end_turn", _text("b")))
    conversation.send_user_text("hi")
    from cobranza.agent.application.conversation_model import ToolResult
    conversation.send_tool_results([ToolResult("t1", "{}"), ToolResult("t2", "{}", is_error=True)])
    last_user = messages.last_request["messages"][-2]
    assert last_user["role"] == "user" and [b["tool_use_id"] for b in last_user["content"]] == ["t1", "t2"]
    assert last_user["content"][1]["is_error"] is True


def test_claude_raises_when_no_model_answers():
    conversation, _ = _conversation(_api_error(), _api_error())
    with pytest.raises(ConversationModelError):
        conversation.send_user_text("hi")


# --- error E1 (simulación 7): al colgar no se pierde "no llamar" ni una disputa ------------

def test_hang_up_event_tells_the_model_to_save_do_not_call_and_disputes():
    tools, _ = _tools()
    model = ScriptedModel(_say(""))
    AgentSession(tools, model).hang_up()
    event = model.received[-1]
    assert "mark_do_not_call" in event and "record_dispute" in event and "end_call" in event


def test_do_not_call_asked_right_before_hanging_up_is_saved():
    tools, uc = _tools(direction=CallDirection.OUTBOUND)
    model = ScriptedModel(
        _say("I understand."),                                 # el modelo solo contesta...
        _say("", ("mark_do_not_call", {})),                    # ...y guarda el pedido al colgar
        _say(""),
    )
    session = AgentSession(tools, model)
    session.debtor_says("Do not call me again!")
    session.hang_up()
    assert session.outcome is CallOutcome.DO_NOT_CALL
    assert len(uc.mark_do_not_call.calls) == 1


def test_dispute_said_right_before_hanging_up_is_saved():
    tools, uc = _tools()
    model = ScriptedModel(
        _say("", ("record_recording_consent", {"accepted": True}), ("verify_identity", VERIFY_JANE)),
        _say("Thank you, Ms. Carter."),
        _say("I'm sorry to hear that."),
        _say("", ("record_dispute", {"account_ref": "ACC-deb-1"})),
        _say(""),
    )
    session = AgentSession(tools, model)
    session.debtor_says("Yes. Jane Carter, 1234, March 14 1985")
    session.debtor_says("I already paid that, it was the bank's fault")
    session.hang_up()
    assert session.outcome is CallOutcome.DISPUTE
    assert len(uc.record_dispute.calls) == 1


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
