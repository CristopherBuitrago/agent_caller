"""Paso 8 de punta a punta contra PostgreSQL, con un modelo guionado en lugar de Claude.

Recorre una llamada completa con TEST-001 (Jane Carter, ACC-T001, USD 485): grabación,
verificación, oferta rechazada, oferta aceptada y cierre. Las reglas y lo guardado son reales.
"""

import json

from cobranza.application.interfaces.conversation_model import ModelTurn, ToolCall
from cobranza.domain.call import CallDirection, CallOutcome
from cobranza.infrastructure.config.container import build_agent


class GuionModel:
    """Cada paso del guion es una función que recibe el modelo y devuelve su turno."""

    def __init__(self, *steps):
        self.steps = list(steps)
        self.tool_answers = []

    def start(self, system_prompt, tools):
        return self

    def send_user_text(self, text):
        return self.steps.pop(0)(self)

    def send_tool_results(self, results):
        self.tool_answers.extend(json.loads(r.content) for r in results)
        return self.steps.pop(0)(self)


def say(text, *calls):
    return lambda model: ModelTurn(text, tuple(ToolCall(f"t-{n}", name, args)
                                               for n, (name, args) in enumerate(calls)))


def respond_to_last_offer(accepted):
    """Responde a la última propuesta que devolvió el sistema (el id no lo inventa la IA)."""
    return lambda model: ModelTurn("", (ToolCall("t-r", "record_offer_response", {
        "proposal_id": model.tool_answers[-1]["proposal_id"], "accepted": accepted}),))


def _call_row(pool, call_id):
    with pool.connection() as conn:
        return conn.execute("SELECT outcome, summary FROM calls WHERE id = %s", (call_id,)).fetchone()


def test_inbound_chat_ends_in_an_arrangement(use_cases, started_calls, pool):
    model = GuionModel(
        say("Hi, thanks for calling. This call is recorded. Is that okay?"),
        say("", ("record_recording_consent", {"accepted": True})),
        say("Thank you. Can I have your full name, last four of your SSN and date of birth?"),
        say("", ("verify_identity", {"full_name": "Jane Carter", "ssn_last4": "1234",
                                     "date_of_birth": "1985-03-14"})),
        say("This is an attempt to collect a debt...", ("get_account_details", {})),
        say("A payment to Lakeside Auto Finance was returned. The balance is $485.00."),
        say("", ("propose_offer", {"account_ref": "ACC-T001"})),
        say("You can pay the full $485.00 today."),
        respond_to_last_offer(False),
        say("", ("propose_offer", {"account_ref": "ACC-T001"})),
        say("You could do 2 monthly payments of $242.50."),
        respond_to_last_offer(True),
        say("", ("end_call", {"outcome": "arrangement_made"})),
        say("You're all set. Thank you, goodbye."),
    )
    session, greeting = build_agent(use_cases, model=model).execute(CallDirection.INBOUND, "+13055550001")
    started_calls.append(session.call_id)
    assert "recorded" in greeting.text

    session.debtor_says("Yes, that's fine")
    session.debtor_says("Jane Carter, 1234, March 14 1985")
    session.debtor_says("What can I do?")
    session.debtor_says("I can't pay all of it today")
    reply = session.debtor_says("Two payments works")

    assert reply.call_ended and reply.outcome is CallOutcome.ARRANGEMENT_MADE
    verified, details = model.tool_answers[1], model.tool_answers[2]
    assert verified["outcome"] == "verified"
    assert details["accounts"][0]["balance"] == "$485.00"
    offers = [a for a in model.tool_answers if "option" in a]
    assert [o["option"] for o in offers] == ["pay the full balance", "2 equal monthly payments"]

    with pool.connection() as conn:
        arrangement = conn.execute(
            "SELECT type, total_amount_cents FROM payment_arrangements WHERE call_id = %s",
            (session.call_id,)).fetchone()
        status = conn.execute("SELECT status FROM accounts WHERE external_id = 'ACC-T001'").fetchone()[0]
    assert arrangement == ("plan", 48500) and status == "PTP"
    outcome, summary = _call_row(pool, session.call_id)
    assert outcome == "arrangement_made" and summary.startswith("Summary of")


def test_ai_cannot_skip_verification_or_invent_an_arrangement(use_cases, started_calls, pool):
    model = GuionModel(
        say("Hi, this call is recorded. Is that okay?"),
        say("", ("record_recording_consent", {"accepted": True})),
        say("Thanks. What can I help you with?"),
        say("", ("propose_offer", {"account_ref": "ACC-T001"}),
            ("end_call", {"outcome": "arrangement_made"})),
        say("Let me verify your identity first."),
    )
    session, _ = build_agent(use_cases, model=model).execute(CallDirection.INBOUND, "+13055550001")
    started_calls.append(session.call_id)
    session.debtor_says("Sure")
    session.debtor_says("Just give me a deal")

    assert [a.get("error") for a in model.tool_answers[1:]] == ["identity_not_verified", "not_allowed"]
    assert not session.ended
    with pool.connection() as conn:
        count = conn.execute("SELECT count(*) FROM payment_arrangements WHERE call_id = %s",
                             (session.call_id,)).fetchone()[0]
    assert count == 0


def test_refused_recording_ends_without_discussing_the_debt(use_cases, started_calls, pool):
    model = GuionModel(
        say("Hi, this call is recorded. Is that okay?"),
        say("", ("record_recording_consent", {"accepted": False})),
        say("", ("end_call", {"outcome": "recording_refused"})),
        say("I understand. Goodbye."),
    )
    session, _ = build_agent(use_cases, model=model).execute(CallDirection.INBOUND, "+13055550001")
    started_calls.append(session.call_id)
    reply = session.debtor_says("No, I don't want to be recorded")
    assert reply.call_ended and reply.outcome is CallOutcome.RECORDING_REFUSED
    assert _call_row(pool, session.call_id)[0] == "recording_refused"
