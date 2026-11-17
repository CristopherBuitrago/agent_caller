"""API HTTP de las herramientas del agente, con casos de uso falsos (sin base ni Claude)."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from cobranza.application.agent_tools import DISCLOSURE, TOOL_SPECS
from cobranza.domain.call import CallDirection, CallOutcome
from cobranza.domain.hardship import HARDSHIP_QUESTIONS
from cobranza.infrastructure.api.app import ApiDeps, create_app
from test_agent_tools import VERIFY_JANE, Stub, _use_cases

KEY = "test-key"
AUTH = {"X-API-Key": KEY}


class _Clock:
    def now(self):
        return datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)


def _api(**use_case_args):
    uc = _use_cases(**use_case_args)
    start_call = Stub(lambda direction, phone, account=None: f"call-{len(start_call.calls)}")
    deps = ApiDeps(uc, start_call, Stub(), _Clock(), callback_number="+18005550199")
    return TestClient(create_app(lambda: deps, KEY)), deps


def _open(client, **body):
    response = client.post("/api/agent/calls", json={"direction": "inbound", "phone": "+13055550001", **body},
                           headers=AUTH)
    assert response.status_code == 201, response.text
    return response.json()


def _tool(client, call_id, name, **tool_input):
    response = client.post(f"/api/agent/calls/{call_id}/tools/{name}", json=tool_input, headers=AUTH)
    assert response.status_code == 200, response.text
    return response.json()


# --- autenticación ---------------------------------------------------------------------------

@pytest.mark.parametrize("method, path", [
    ("get", "/api/agent/tools"), ("post", "/api/agent/calls"), ("get", "/api/agent/calls/x"),
    ("post", "/api/agent/calls/x/tools/end_call"), ("put", "/api/agent/calls/x/transcript"),
    ("post", "/api/agent/calls/x/hangup"), ("post", "/api/agent/calls/x/close"),
])
@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "wrong"}])
def test_every_endpoint_needs_the_api_key(method, path, headers):
    client, _ = _api()
    assert getattr(client, method)(path, headers=headers).status_code == 401


def test_the_app_does_not_start_without_a_key():
    with pytest.raises(ValueError):
        create_app(lambda: None, "")


# --- herramientas y llamadas -----------------------------------------------------------------

def test_tools_list_has_every_tool_the_disclosure_and_the_hardship_questions():
    client, _ = _api()
    body = client.get("/api/agent/tools", headers=AUTH).json()
    assert [t["name"] for t in body["tools"]] == [s.name for s in TOOL_SPECS]
    assert all(t["input_schema"]["additionalProperties"] is False for t in body["tools"])
    assert body["disclosure"] == DISCLOSURE
    assert body["hardship_questions"] == list(HARDSHIP_QUESTIONS)


def test_open_inbound_call():
    client, deps = _api()
    body = _open(client)
    assert body == {"call_id": "call-1", "direction": "inbound", "debtor_name": None, "today": "2026-11-16"}
    assert deps.start_call.calls == [(CallDirection.INBOUND, "+13055550001", None)]


def test_open_outbound_call_uses_the_debtor_phone_and_returns_the_name():
    client, deps = _api()
    body = _open(client, direction="outbound", phone=None, account="ACC-deb-1")
    assert body["debtor_name"] == "Jane Carter"
    assert deps.start_call.calls == [(CallDirection.OUTBOUND, "+13055550001", "ACC-deb-1")]


def test_open_call_needs_phone_or_account_and_the_account_must_exist():
    client, deps = _api()
    assert client.post("/api/agent/calls", json={"direction": "inbound"}, headers=AUTH).status_code == 422
    assert client.post("/api/agent/calls", json={"direction": "outbound"}, headers=AUTH).status_code == 422
    deps.tools_use_cases.get_debtor_by_account._fn = lambda account: None
    response = client.post("/api/agent/calls", json={"direction": "outbound", "account": "ACC-X"}, headers=AUTH)
    assert response.status_code == 404 and deps.start_call.calls == []


def test_tool_runs_with_the_same_rules_and_next_step():
    client, _ = _api()
    call_id = _open(client)["call_id"]
    early = _tool(client, call_id, "get_account_details")
    assert early["is_error"] and early["result"]["error"] == "identity_not_verified"
    _tool(client, call_id, "record_recording_consent", accepted=True)
    verified = _tool(client, call_id, "verify_identity", **VERIFY_JANE)
    assert not verified["is_error"] and DISCLOSURE in verified["result"]["next_step"]
    assert verified["call"] == {"call_id": call_id, "ended": False, "outcome": None, "summary": None,
                                "transferred": False}


def test_unknown_tool_and_invalid_input_are_errors_for_the_model():
    client, _ = _api()
    call_id = _open(client)["call_id"]
    unknown = _tool(client, call_id, "send_money")
    assert unknown["is_error"] and unknown["result"]["error"] == "unknown_tool"
    invalid = _tool(client, call_id, "verify_identity", full_name="Jane")
    assert invalid["is_error"] and invalid["result"]["error"] == "invalid_input"
    response = client.post(f"/api/agent/calls/{call_id}/tools/end_call", json=[1, 2], headers=AUTH)
    assert response.status_code == 422


def test_unknown_call_is_404():
    client, _ = _api()
    assert client.get("/api/agent/calls/nope", headers=AUTH).status_code == 404
    assert client.post("/api/agent/calls/nope/tools/end_call", json={}, headers=AUTH).status_code == 404


def test_closing_tool_ends_the_call_with_the_summary_and_the_transcript():
    client, deps = _api()
    call_id = _open(client)["call_id"]
    client.put(f"/api/agent/calls/{call_id}/transcript", json={"text": "Debtor: hi\nAgent: hello"},
               headers=AUTH)
    _tool(client, call_id, "record_recording_consent", accepted=True)
    ended = _tool(client, call_id, "transfer_to_human", reason="Asked for a person")
    assert ended["call"]["ended"] and ended["call"]["outcome"] == "transferred_to_human"
    assert ended["call"]["summary"] == "summary" and ended["call"]["transferred"]
    assert deps.tools_use_cases.end_call.calls[-1] == (
        call_id, CallOutcome.TRANSFERRED_TO_HUMAN, "Debtor: hi\nAgent: hello", "Asked for a person")
    after = _tool(client, call_id, "end_call", outcome="callback_requested")
    assert after["is_error"] and after["result"]["error"] == "call_ended"
    assert client.get(f"/api/agent/calls/{call_id}", headers=AUTH).json()["outcome"] == "transferred_to_human"


def test_log_uri_is_attached_once():
    client, deps = _api()
    call_id = _open(client)["call_id"]
    for _ in range(2):
        client.put(f"/api/agent/calls/{call_id}/transcript", json={"log_uri": "/app/call_logs/x.json"},
                   headers=AUTH)
    assert deps.attach_transcript.calls == [(call_id, "/app/call_logs/x.json")]


def test_after_hang_up_no_tool_asks_the_agent_to_speak():
    client, _ = _api()
    call_id = _open(client)["call_id"]
    client.post(f"/api/agent/calls/{call_id}/hangup", headers=AUTH)
    answer = _tool(client, call_id, "mark_do_not_call")
    assert answer["result"]["next_step"] == "The caller already hung up. Do not say anything."
    assert answer["call"]["outcome"] == "do_not_call"


def test_close_without_the_model_saves_the_reason():
    client, deps = _api()
    call_id = _open(client)["call_id"]
    _tool(client, call_id, "record_recording_consent", accepted=True)
    body = client.post(f"/api/agent/calls/{call_id}/close", headers=AUTH, json={
        "outcome": "transferred_to_human", "transfer_reason": "The agent could not continue."}).json()
    assert body["ended"] and body["outcome"] == "transferred_to_human"
    assert deps.tools_use_cases.end_call.calls[-1][-1] == "The agent could not continue."


def test_close_only_accepts_transfer_or_callback():
    client, _ = _api()
    call_id = _open(client)["call_id"]
    response = client.post(f"/api/agent/calls/{call_id}/close", json={"outcome": "arrangement_made"},
                           headers=AUTH)
    assert response.status_code == 422


def test_close_without_recording_consent_ends_as_recording_refused():
    client, _ = _api()
    call_id = _open(client)["call_id"]
    _tool(client, call_id, "record_recording_consent", accepted=False)
    body = client.post(f"/api/agent/calls/{call_id}/close", json={"outcome": "callback_requested"},
                       headers=AUTH).json()
    assert body["outcome"] == "recording_refused"
