"""Paso 8: la conversación del agente, sin backend ni API de Claude.

Las reglas de cada herramienta se prueban en el backend (backend/tests/unit/test_agent_tools.py);
aquí se prueba que la sesión las pide, pasa la conversación, cuelga y cierra como corresponde.
"""

import json
from datetime import date
from types import SimpleNamespace

import anthropic
import pytest

from cobranza_agent.application.call import CallDirection, CallOutcome
from cobranza_agent.application.call_backend import CallBackendError, OpenedCall, ToolCatalog
from cobranza_agent.application.conversation import (
    FALLBACK_TEXT,
    HANG_UP_EVENT,
    MAX_TOOL_ROUNDS_PER_TURN,
    AgentSession,
    StartAgentConversation,
    render_system_prompt,
)
from cobranza_agent.application.conversation_model import (
    ConversationModelError,
    ModelTurn,
    ToolCall,
    ToolResult,
    ToolSpec,
)
from cobranza_agent.infrastructure.claude_conversation_model import ClaudeConversationModel

# --- dobles -------------------------------------------------------------------------------

# Las herramientas que publica el backend (GET /api/agent/tools); el prompt habla de todas.
TOOL_NAMES = ("record_recording_consent", "verify_identity", "confirm_identity", "get_account_details", "propose_offer",
              "record_offer_response", "propose_partial_payment", "record_hardship_answers",
              "record_dispute", "mark_do_not_call", "get_last_contact", "schedule_callback",
              "report_wrong_number", "transfer_to_human", "end_call")
DISCLOSURE = "This is an attempt to collect a debt."
CATALOG = ToolCatalog(tuple(ToolSpec(n, n, {"type": "object"}) for n in TOOL_NAMES), DISCLOSURE,
                      ("What happened?", "Is it temporary?"))
# Herramientas que cierran la llamada en el backend y con qué resultado.
CLOSING_TOOLS = {"mark_do_not_call": CallOutcome.DO_NOT_CALL, "record_dispute": CallOutcome.DISPUTE,
                 "transfer_to_human": CallOutcome.TRANSFERRED_TO_HUMAN}


class FakeCallTools:
    """Llamada abierta en un backend falso: guarda lo que se le pidió."""

    def __init__(self, fail_on=()):
        self.call_id = "c1"
        self.ended = False
        self.outcome = None
        self.summary = None
        self.executed = []        # (nombre, ¿ya había colgado?)
        self.transcripts = []
        self.hung_up = False
        self.closed_with = None
        self._fail_on = set(fail_on)

    def execute(self, call):
        if "execute" in self._fail_on:
            raise CallBackendError("down")
        self.executed.append((call.name, self.hung_up))
        if call.name in CLOSING_TOOLS and not self.ended:
            self.ended, self.outcome, self.summary = True, CLOSING_TOOLS[call.name], "summary"
        return ToolResult(call.id, json.dumps({"ok": True}))

    def update_transcript(self, text):
        if "transcript" in self._fail_on:
            raise CallBackendError("down")
        self.transcripts.append(text)

    def mark_hung_up(self):
        self.hung_up = True

    def close_without_model(self, outcome, transfer_reason=None):
        if "close" in self._fail_on:
            raise CallBackendError("down")
        if not self.ended:
            self.ended, self.outcome, self.summary = True, outcome, "summary"
            self.closed_with = (outcome, transfer_reason)


class FakeBackend:
    def __init__(self, tools=None):
        self.tools = tools or FakeCallTools()
        self.opened = []
        self.catalog_calls = 0

    def catalog(self):
        self.catalog_calls += 1
        return CATALOG

    def open_call(self, direction, phone, account=None):
        if account == "NOPE":
            raise LookupError("No existe la cuenta NOPE")
        self.opened.append((direction, phone, account))
        name = "Jane Carter" if direction is CallDirection.OUTBOUND else None
        return OpenedCall(self.tools, name, date(2026, 11, 16))


class ScriptedModel:
    """Modelo falso: responde los turnos en el orden dado y guarda lo que recibió."""

    def __init__(self, *turns):
        self.turns = list(turns)
        self.received = []
        self.started_with = None

    def start(self, system_prompt, tools):
        self.started_with = (system_prompt, tools)
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


def _prompt():
    return render_system_prompt("Live Oac Financial", "L.O.F.", CATALOG)


# --- sesión -------------------------------------------------------------------------------

def test_session_runs_the_tools_and_joins_the_agent_text():
    tools = FakeCallTools()
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


def test_the_backend_gets_the_conversation_after_each_line():
    tools = FakeCallTools()
    session = AgentSession(tools, ScriptedModel(_say("Hello.")))
    session.debtor_says("Hi")
    assert tools.transcripts == ["Debtor: Hi", "Debtor: Hi\nAgent: Hello."]


def test_a_failed_transcript_update_does_not_stop_the_call():
    tools = FakeCallTools(fail_on={"transcript"})
    reply = AgentSession(tools, ScriptedModel(_say("Hello."))).debtor_says("Hi")
    assert reply.text == "Hello." and not reply.call_ended


def test_model_failure_transfers_to_a_person():
    tools = FakeCallTools()
    session = AgentSession(tools, ScriptedModel(ConversationModelError("down")))
    reply = session.debtor_says("hello")
    assert reply == type(reply)(FALLBACK_TEXT, True, CallOutcome.TRANSFERRED_TO_HUMAN)
    with pytest.raises(ValueError):
        session.debtor_says("hello?")


def test_model_failure_saves_a_transfer_reason():
    tools = FakeCallTools()
    AgentSession(tools, ScriptedModel(ConversationModelError("down"))).debtor_says("hello")
    outcome, reason = tools.closed_with
    assert outcome is CallOutcome.TRANSFERRED_TO_HUMAN and "technical problem" in reason


def test_backend_failure_transfers_to_a_person():
    tools = FakeCallTools(fail_on={"execute"})
    reply = AgentSession(tools, ScriptedModel(_say("", ("get_account_details", {})))).debtor_says("hi")
    assert reply.text == FALLBACK_TEXT and reply.call_ended
    assert tools.closed_with[0] is CallOutcome.TRANSFERRED_TO_HUMAN


def test_backend_down_still_answers_the_fallback():
    tools = FakeCallTools(fail_on={"execute", "close"})
    reply = AgentSession(tools, ScriptedModel(_say("", ("get_account_details", {})))).debtor_says("hi")
    assert reply == type(reply)(FALLBACK_TEXT, True, CallOutcome.TRANSFERRED_TO_HUMAN)


def test_endless_tool_loop_transfers_to_a_person():
    tools = FakeCallTools()
    loop = [_say("", ("get_account_details", {}))] * (MAX_TOOL_ROUNDS_PER_TURN + 1)
    reply = AgentSession(tools, ScriptedModel(*loop)).debtor_says("hi")
    assert reply.call_ended and reply.outcome is CallOutcome.TRANSFERRED_TO_HUMAN


def test_hang_up_closes_the_call_even_if_the_model_does_not():
    tools = FakeCallTools()
    session = AgentSession(tools, ScriptedModel(_say("")))
    session.hang_up()
    assert session.ended and session.outcome is CallOutcome.CALLBACK_REQUESTED


def test_hang_up_marks_the_tools_as_hung_up():
    tools = FakeCallTools()
    AgentSession(tools, ScriptedModel(_say(""))).hang_up()
    assert tools.hung_up


# --- error E1 (simulación 7): al colgar no se pierde "no llamar" ni una disputa ------------

def test_hang_up_event_tells_the_model_to_save_do_not_call_and_disputes():
    model = ScriptedModel(_say(""))
    AgentSession(FakeCallTools(), model).hang_up()
    event = model.received[-1]
    assert "mark_do_not_call" in event and "record_dispute" in event and "end_call" in event
    assert HANG_UP_EVENT in event


def test_do_not_call_asked_right_before_hanging_up_is_saved():
    tools = FakeCallTools()
    model = ScriptedModel(
        _say("I understand."),                                 # el modelo solo contesta...
        _say("", ("mark_do_not_call", {})),                    # ...y guarda el pedido al colgar
        _say(""),
    )
    session = AgentSession(tools, model)
    session.debtor_says("Do not call me again!")
    session.hang_up()
    assert tools.executed == [("mark_do_not_call", True)]    # se pidió después de avisar que colgó
    assert session.outcome is CallOutcome.DO_NOT_CALL and tools.closed_with is None


def test_dispute_said_right_before_hanging_up_is_saved():
    tools = FakeCallTools()
    model = ScriptedModel(
        _say("I'm sorry to hear that."),
        _say("", ("record_dispute", {"account_ref": "ACC-T001"})),
        _say(""),
    )
    session = AgentSession(tools, model)
    session.debtor_says("I already paid that, it was the bank's fault")
    session.hang_up()
    assert tools.executed == [("record_dispute", True)]
    assert session.outcome is CallOutcome.DISPUTE


# --- apertura de la llamada -----------------------------------------------------------------

def test_inbound_call_opens_in_the_backend_and_greets():
    backend = FakeBackend()
    model = ScriptedModel(_say("Thank you for calling L.O.F."))
    agent = StartAgentConversation(backend, model, "Live Oac Financial", "L.O.F.")
    session, reply = agent.execute(CallDirection.INBOUND, "+13055550001")
    assert backend.opened == [(CallDirection.INBOUND, "+13055550001", None)]
    assert session.call_id == "c1" and reply.text == "Thank you for calling L.O.F."
    assert model.received[0] == ("<call_event>Inbound call connected. Today is Monday, November 16, "
                                 "2026. Greet the caller.</call_event>")
    prompt, tools = model.started_with
    assert DISCLOSURE in prompt and [t.name for t in tools] == list(TOOL_NAMES)


def test_outbound_call_says_who_we_are_calling():
    backend = FakeBackend()
    model = ScriptedModel(_say("Hello."))
    StartAgentConversation(backend, model, "Live Oac Financial", "L.O.F.").execute(
        CallDirection.OUTBOUND, None, "ACC-T001")
    assert backend.opened == [(CallDirection.OUTBOUND, None, "ACC-T001")]
    assert "You are calling Jane Carter." in model.received[0]


def test_unknown_account_is_a_lookup_error():
    agent = StartAgentConversation(FakeBackend(), ScriptedModel(), "Live Oac Financial", "L.O.F.")
    with pytest.raises(LookupError):
        agent.execute(CallDirection.OUTBOUND, None, "NOPE")


def test_the_catalog_is_asked_only_once():
    backend = FakeBackend()
    agent = StartAgentConversation(backend, ScriptedModel(_say("a"), _say("b")), "Live Oac Financial", "L.O.F.")
    agent.execute(CallDirection.INBOUND, "+13055550001")
    agent.execute(CallDirection.INBOUND, "+13055550001")
    assert backend.catalog_calls == 1


# --- prompt ---------------------------------------------------------------------------------

def test_system_prompt_has_no_placeholders_left():
    prompt = _prompt()
    assert "{{" not in prompt and DISCLOSURE in prompt
    assert "L.O.F." in prompt and "Live Oac Financial" in prompt
    assert all(q in prompt for q in CATALOG.hardship_questions)
    assert all(name in prompt for name in TOOL_NAMES)


@pytest.mark.parametrize("phrase", [
    "To protect your privacy",                                          # P1
    "I can share the reason once I confirm I'm speaking with the right person",  # P1
    "You've reached L.O.F., and I'm happy to help",                     # P12
    "wait for a clear yes",                                             # P4
    "yes, but with a discount",                                         # P4
    "I'm not able to remove it",                                        # P5
    "Do you remember the date of that payment and the confirmation number?",  # P6 y B5
    "Are you saying the payment went through?",                         # P6
    "Would you like to take care of it today?",                         # P8
    "about one hundred sixty-two dollars a month",                      # P8
    "we can set your first payment for when you'll have the money",     # P9
    "leave `duration_type` empty",                                      # P10
    "in the coming weeks",                                              # P10
    "Hello, I'm Lucy from L.O.F.",                                      # nombre (2026-11-19)
    "this is Lucy calling from L.O.F.",
    "I'm Lucy, a virtual assistant with L.O.F.",                        # si pregunta si es un robot
])
def test_system_prompt_has_the_approved_phrases(phrase):
    assert phrase in _prompt()


def test_the_greeting_says_lucy_and_not_virtual_assistant():
    prompt = _prompt()
    assert "you're speaking with a virtual assistant" not in prompt
    assert "this is a virtual assistant calling" not in prompt


def test_lucy_never_says_an_option_does_not_exist():          # prueba de voz, 2026-11-20
    assert "Never say that an option does not exist or is not available" in _prompt()


def test_lucy_asks_ssn_then_date_then_confirms_the_name():      # usuario, 2026-11-22
    prompt = _prompt()
    assert "could you please give me the last four digits of your Social Security number?" in prompt
    assert 'ask: "And your date of birth?"' in prompt
    assert "Am I speaking with [name]?" in prompt and "confirm_identity" in prompt


def test_lucy_says_what_lof_is_before_verifying():               # decisión 1, 2026-11-24
    assert "L.O.F. is the company that sent you the message." in _prompt()


def test_lucy_never_talks_about_errors_or_the_system():          # decisión 10, 2026-11-24
    prompt = _prompt()
    assert "Never say \"error\", \"system\"" in prompt
    assert "I'm sorry, we need to end the call here. You can call us back anytime. Goodbye." in prompt


def test_lucy_only_speaks_english():                         # prueba de voz, 2026-11-20
    prompt = _prompt()
    assert "Always speak English, even if the caller or someone in the background" in prompt
    assert "I'm sorry, I can only help in English. Would you like me to transfer you" in prompt


def test_after_verification_it_says_this_is_and_not_calling_from():
    prompt = _prompt()
    assert "This is Live Oac Financial." in prompt
    assert "I'm calling from Live Oac Financial" not in prompt


def test_prompt_says_a_doubtful_yes_does_not_create_the_agreement():       # N7
    prompt = _prompt()
    assert "Only a clear yes counts" in prompt
    assert "how much could you comfortably pay each month?" in prompt
    assert "`max_payment_dollars`" in prompt


def test_prompt_keeps_calm_with_distress_and_threats_and_never_transfers_for_it():   # N14
    prompt = _prompt()
    assert "This is only a debt, there is a solution" in prompt
    assert "let them be the one to hang up" in prompt
    assert "Never hang up or transfer because of a threat or an insult" in prompt
    assert "is upset" not in prompt          # antes: "upset" -> transfer_to_human


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
    conversation.send_tool_results([ToolResult("t1", "{}"), ToolResult("t2", "{}", is_error=True)])
    last_user = messages.last_request["messages"][-2]
    assert last_user["role"] == "user" and [b["tool_use_id"] for b in last_user["content"]] == ["t1", "t2"]
    assert last_user["content"][1]["is_error"] is True


def test_claude_raises_when_no_model_answers():
    conversation, _ = _conversation(_api_error(), _api_error())
    with pytest.raises(ConversationModelError):
        conversation.send_user_text("hi")


def test_the_prompt_never_says_the_short_name_with_a_double_period():
    """Hallazgo 6 de las simulaciones con Haiku: decía "calling from L.O.F..". """
    prompt = render_system_prompt("Live Oac Financial", "L.O.F.", CATALOG)
    assert "L.O.F.." not in prompt and "calling from L.O.F." in prompt
    without_period = render_system_prompt("Live Oac Financial", "LOF", CATALOG)
    assert "calling from LOF." in without_period
