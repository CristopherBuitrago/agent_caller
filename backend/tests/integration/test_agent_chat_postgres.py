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


# --- más llamadas completas por chat (2026-11-11) -------------------------------------------

JANE = ("verify_identity", {"full_name": "Jane Carter", "ssn_last4": "1234", "date_of_birth": "1985-03-14"})


def _start(use_cases, started_calls, model, direction=CallDirection.INBOUND, account=None):
    session, greeting = build_agent(use_cases, model=model).execute(direction, "+13055550001", account)
    started_calls.append(session.call_id)
    return session, greeting


def _arrangement(pool, call_id):
    with pool.connection() as conn:
        row = conn.execute("SELECT id, type FROM payment_arrangements WHERE call_id = %s",
                           (call_id,)).fetchone()
        if row is None:
            return None
        amounts = [r[0] for r in conn.execute(
            "SELECT amount_cents FROM scheduled_payments WHERE arrangement_id = %s ORDER BY sequence",
            (row[0],)).fetchall()]
    return row[1], amounts


def _jane_flags(pool):
    with pool.connection() as conn:
        return conn.execute(
            """SELECT a.status, a.is_disputed, d.do_not_call FROM accounts a
               JOIN debtors d ON d.id = a.debtor_id WHERE a.external_id = 'ACC-T001'""").fetchone()


def test_chat_hardship_then_four_payments(use_cases, started_calls, pool):
    model = GuionModel(
        say("Hi, this call is recorded. Is that okay?"),
        say("", ("record_recording_consent", {"accepted": True})),
        say("Thanks. Full name, last four of your SSN and date of birth?"),
        say("", JANE),
        say("", ("propose_offer", {"account_ref": "ACC-T001"})),
        say("You can pay the full $485.00."),
        respond_to_last_offer(False), say("", ("propose_offer", {"account_ref": "ACC-T001"})),
        say("Two monthly payments of $242.50?"),
        respond_to_last_offer(False), say("", ("propose_offer", {"account_ref": "ACC-T001"})),
        say("Three monthly payments?"),
        respond_to_last_offer(False), say("", ("propose_offer", {"account_ref": "ACC-T001"})),
        say("Can I ask a few questions about your situation?"),
        say("", ("record_hardship_answers", {"situation_description": "Reduced hours at work",
                                             "duration_type": "temporary", "household_support": False})),
        say("", ("propose_offer", {"account_ref": "ACC-T001"})),
        say("Four monthly payments of $121.25?"),
        respond_to_last_offer(True),
        say("", ("end_call", {"outcome": "arrangement_made"})),
        say("You're all set. Goodbye."),
    )
    session, _ = _start(use_cases, started_calls, model)
    session.debtor_says("Yes")
    session.debtor_says("Jane Carter, 1234, March 14 1985")
    session.debtor_says("No, I can't")
    session.debtor_says("Still too much")
    session.debtor_says("No")
    session.debtor_says("My hours were cut last month")
    reply = session.debtor_says("Yes, four works")

    assert "hardship_required" in [a.get("error") for a in model.tool_answers]
    assert reply.call_ended and reply.outcome is CallOutcome.ARRANGEMENT_MADE
    assert _arrangement(pool, session.call_id) == ("plan", [12125, 12125, 12125, 12125])
    with pool.connection() as conn:
        hardship = conn.execute("SELECT situation_description FROM hardship_assessments WHERE call_id = %s",
                                (session.call_id,)).fetchone()
    assert hardship == ("Reduced hours at work",)
    assert _jane_flags(pool)[0] == "PTP"


def test_chat_partial_payment_of_the_debtor(use_cases, started_calls, pool):
    model = GuionModel(
        say("Hi, this call is recorded. Is that okay?"),
        say("", ("record_recording_consent", {"accepted": True})),
        say("Can you verify your identity?"),
        say("", JANE),
        say("How can I help?"),
        say("", ("propose_partial_payment", {"account_ref": "ACC-T001", "amount_dollars": 100})),
        say("$100 now and $385 in 30 days. Does that work?"),
        respond_to_last_offer(True),
        say("", ("end_call", {"outcome": "arrangement_made"})),
        say("Done. Goodbye."),
    )
    session, _ = _start(use_cases, started_calls, model)
    session.debtor_says("Yes")
    session.debtor_says("Jane Carter, 1234, March 14 1985")
    session.debtor_says("I can only pay $100 right now")
    reply = session.debtor_says("Yes")
    assert reply.outcome is CallOutcome.ARRANGEMENT_MADE
    assert _arrangement(pool, session.call_id) == ("partial", [10000, 38500])


def test_chat_dispute_closes_the_call_without_asking_for_payment(use_cases, started_calls, pool):
    model = GuionModel(
        say("Hi, this call is recorded. Is that okay?"),
        say("", ("record_recording_consent", {"accepted": True})),
        say("Can you verify your identity?"),
        say("", JANE),
        say("A payment was returned."),
        say("", ("record_dispute", {"account_ref": "ACC-T001"})),
        say("A representative will review it. Goodbye."),
    )
    session, _ = _start(use_cases, started_calls, model)
    session.debtor_says("Yes")
    session.debtor_says("Jane Carter, 1234, March 14 1985")
    reply = session.debtor_says("I already paid that, it was the bank's mistake")
    assert reply.call_ended and reply.outcome is CallOutcome.DISPUTE
    assert _jane_flags(pool)[1] is True
    assert _arrangement(pool, session.call_id) is None
    assert _call_row(pool, session.call_id)[0] == "dispute"


def test_chat_do_not_call_marks_the_debtor(use_cases, started_calls, pool):
    model = GuionModel(
        say("Hi, this call is recorded. Is that okay?"),
        say("", ("record_recording_consent", {"accepted": True})),
        say("Can you verify your identity?"),
        say("", JANE),
        say("How can I help?"),
        say("", ("mark_do_not_call", {})),
        say("You will not be called again. Goodbye."),
    )
    session, _ = _start(use_cases, started_calls, model)
    session.debtor_says("Yes")
    session.debtor_says("Jane Carter, 1234, March 14 1985")
    reply = session.debtor_says("Stop calling me")
    assert reply.call_ended and reply.outcome is CallOutcome.DO_NOT_CALL
    assert _jane_flags(pool)[2] is True
    assert _call_row(pool, session.call_id)[0] == "do_not_call"


def test_chat_outbound_call_pays_in_full(use_cases, started_calls, pool):
    model = GuionModel(
        say("Hi, may I speak with Jane Carter? This call is recorded. Is that okay?"),
        say("", ("record_recording_consent", {"accepted": True})),
        say("Can you verify your identity?"),
        say("", JANE),
        say("", ("propose_offer", {"account_ref": "ACC-T001"})),
        say("You can pay the full $485.00."),
        respond_to_last_offer(True),
        say("", ("end_call", {"outcome": "arrangement_made"})),
        say("Thank you. Goodbye."),
    )
    session, greeting = _start(use_cases, started_calls, model, CallDirection.OUTBOUND, "ACC-T001")
    assert "Jane Carter" in greeting.text
    session.debtor_says("Speaking, that's fine")
    session.debtor_says("Jane Carter, 1234, March 14 1985")
    reply = session.debtor_says("Sure, I'll pay it all")
    assert reply.outcome is CallOutcome.ARRANGEMENT_MADE
    assert _arrangement(pool, session.call_id) == ("full", [48500])
    with pool.connection() as conn:
        direction = conn.execute("SELECT direction FROM calls WHERE id = %s", (session.call_id,)).fetchone()[0]
    assert direction == "outbound"


def test_chat_do_not_call_then_hang_up_is_saved(use_cases, started_calls, pool):
    """Error E1 (simulación 7): la deudora pide no ser llamada y cuelga antes de que el agente actúe."""
    model = GuionModel(
        say("Hi, may I speak with Jane Carter, please?"),
        say("I'm sorry for the inconvenience."),           # el modelo no guarda nada en este turno
        say("", ("mark_do_not_call", {})),                 # lo guarda con el aviso de cuelgue
        say(""),
    )
    session, _ = _start(use_cases, started_calls, model, CallDirection.OUTBOUND, "ACC-T001")
    session.debtor_says("Please do not call me again!")
    session.hang_up()
    assert session.outcome is CallOutcome.DO_NOT_CALL
    assert _jane_flags(pool)[2] is True
    assert _call_row(pool, session.call_id)[0] == "do_not_call"


def test_chat_caller_who_changes_name_is_closed_as_identity_mismatch(use_cases, started_calls, pool):
    """S1 (simulación 8): dijo "Paul Carter" con otra fecha, falló, y luego probó con "Jane Carter".

    Con S2 ya no se le pide deletrear: falla el nombre de pila y la fecha, así que es un fallo normal.
    """
    model = GuionModel(
        say("Thank you for calling. This call is recorded. Is that okay?"),
        say("", ("record_recording_consent", {"accepted": True})),
        say("Can I have your full name, last four of your SSN and date of birth?"),
        say("", ("verify_identity", {"full_name": "Paul Carter", "ssn_last4": "1234",
                                     "date_of_birth": "1980-01-01"})),
        say("That doesn't match our records. Could you repeat it?"),
        say("", ("verify_identity", {"full_name": "Jane Carter", "ssn_last4": "1234",
                                     "date_of_birth": "1985-03-14"})),
        say("", ("get_account_details", {})),            # aunque lo intente, la llamada ya terminó
        say("I couldn't verify your identity. Please call us back with your own information. Goodbye."),
    )
    session, _ = _start(use_cases, started_calls, model)
    session.debtor_says("Yes")
    session.debtor_says("Paul Carter, 1234, January 1 1980")
    reply = session.debtor_says("Sorry, it's Jane Carter, 1234, March 14 1985")

    outcomes = [a.get("outcome") for a in model.tool_answers]
    assert outcomes[1:3] == ["failed", "identity_mismatch"]
    assert model.tool_answers[3]["error"] == "call_ended"   # no pudo ver la cuenta
    assert reply.call_ended and reply.outcome is CallOutcome.IDENTITY_MISMATCH
    with pool.connection() as conn:
        row = conn.execute("SELECT outcome, identity_verified, verification_attempts FROM calls WHERE id = %s",
                           (session.call_id,)).fetchone()
    assert row == ("identity_mismatch", False, 2)
