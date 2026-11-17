"""API y página web del chat de prueba, con una sesión falsa (sin Claude ni base de datos)."""

from fastapi.testclient import TestClient

from cobranza_agent.application.conversation import AgentReply
from cobranza_agent.application.conversation_model import ToolCall, ToolResult
from cobranza_agent.infrastructure.call_log import CallLogStore
from cobranza_agent.infrastructure.web import create_app
from cobranza_agent.application.call import CallDirection, CallOutcome


class FakeSession:
    def __init__(self, on_tool):
        self.call_id = "call-1"
        self.ended = False
        self.outcome = None
        self.summary = None
        self.heard = []
        self._on_tool = on_tool

    def debtor_says(self, text):
        self.heard.append(text)
        self._on_tool(ToolCall("t1", "verify_identity", {}), ToolResult("t1", '{"outcome": "verified"}'))
        if text == "bye":
            self.ended, self.outcome = True, CallOutcome.CALLBACK_REQUESTED
        return AgentReply(f"You said: {text}", self.ended, self.outcome)

    def hang_up(self):
        self.ended, self.outcome, self.summary = True, CallOutcome.CALLBACK_REQUESTED, "Short call."


def _client(store=None, saved=None):
    opened = []

    def open_call(direction, phone, account, on_tool):
        if account == "NOPE":
            raise LookupError("No existe la cuenta NOPE")
        session = FakeSession(on_tool)
        opened.append((direction, phone, account, session))
        return session, AgentReply("Thank you for calling L.O.F.", False, None)

    on_saved = (lambda call_id, uri: saved.append((call_id, uri))) if saved is not None else None
    return TestClient(create_app(open_call, store=store, on_log_saved=on_saved)), opened


def test_page_is_served():
    client, _ = _client()
    page = client.get("/")
    assert page.status_code == 200 and "Iniciar llamada" in page.text


def test_full_chat_flow():
    client, opened = _client()
    start = client.post("/api/calls", json={"direction": "inbound", "phone": "+13055550001"}).json()
    assert start["call_id"] == "call-1" and start["reply"] == "Thank you for calling L.O.F."
    assert opened[0][:3] == (CallDirection.INBOUND, "+13055550001", None)

    answer = client.post("/api/calls/call-1/messages", json={"text": "Jane Carter"}).json()
    assert answer["reply"] == "You said: Jane Carter" and not answer["ended"]
    assert answer["tools"][0]["name"] == "verify_identity"   # se muestran las herramientas del turno
    again = client.post("/api/calls/call-1/messages", json={"text": "hi"}).json()
    assert len(again["tools"]) == 1                           # solo las nuevas, no las anteriores

    end = client.post("/api/calls/call-1/hangup").json()
    assert end["outcome"] == "callback_requested" and end["summary"] == "Short call."
    assert client.post("/api/calls/call-1/messages", json={"text": "hello?"}).status_code == 404


def test_outbound_needs_an_existing_account():
    client, opened = _client()
    assert client.post("/api/calls", json={"direction": "outbound"}).status_code == 422
    assert client.post("/api/calls", json={"direction": "outbound", "account": "NOPE"}).status_code == 404
    ok = client.post("/api/calls", json={"direction": "outbound", "account": "ACC-T001"})
    assert ok.status_code == 200 and opened[0][0] is CallDirection.OUTBOUND


def test_inbound_needs_a_phone_and_messages_cannot_be_empty():
    client, _ = _client()
    assert client.post("/api/calls", json={"direction": "inbound"}).status_code == 422
    client.post("/api/calls", json={"direction": "inbound", "phone": "+13055550001"})
    assert client.post("/api/calls/call-1/messages", json={"text": ""}).status_code == 422


def test_no_messages_after_the_agent_ends_the_call():
    client, _ = _client()
    client.post("/api/calls", json={"direction": "inbound", "phone": "+13055550001"})
    assert client.post("/api/calls/call-1/messages", json={"text": "bye"}).json()["ended"]
    assert client.post("/api/calls/call-1/messages", json={"text": "wait"}).status_code == 409


def test_unknown_call_is_404():
    client, _ = _client()
    assert client.post("/api/calls/nope/messages", json={"text": "hi"}).status_code == 404
    assert client.post("/api/calls/nope/hangup").status_code == 404


# --- historial ---------------------------------------------------------------------------

def test_history_saves_the_whole_conversation(tmp_path):
    saved = []
    client, _ = _client(CallLogStore(tmp_path), saved)
    client.post("/api/calls", json={"direction": "inbound", "phone": "+13055550001", "label": "Jane"})
    client.post("/api/calls/call-1/messages", json={"text": "Jane Carter"})
    client.post("/api/calls/call-1/hangup")

    assert saved == [("call-1", str(tmp_path / "call-1.json"))]   # transcript_uri, una sola vez
    listed = client.get("/api/history").json()
    assert listed[0]["call_id"] == "call-1" and listed[0]["outcome"] == "callback_requested"
    detail = client.get("/api/history/call-1").json()
    kinds = [e["type"] for e in detail["events"]]
    assert kinds == ["system", "agent", "debtor", "tool", "agent", "system"]
    assert detail["scenario"]["label"] == "Jane" and detail["summary"] == "Short call."


def test_history_is_saved_after_every_turn(tmp_path):
    client, _ = _client(CallLogStore(tmp_path))
    client.post("/api/calls", json={"direction": "inbound", "phone": "+13055550001"})
    client.post("/api/calls/call-1/messages", json={"text": "hello"})
    detail = client.get("/api/history/call-1").json()               # sin colgar todavía
    assert detail["outcome"] is None and [e["type"] for e in detail["events"]][-1] == "agent"


def test_history_pages_and_unknown_calls(tmp_path):
    client, _ = _client(CallLogStore(tmp_path))
    assert "Historial de llamadas" in client.get("/historial").text
    assert client.get("/api/history").json() == []
    assert client.get("/api/history/nope").status_code == 404
