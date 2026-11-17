"""Cliente HTTP del backend, con un transporte falso (sin red ni servidor)."""

import json
from datetime import date

import httpx
import pytest

from cobranza_agent.application.call import CallDirection, CallOutcome
from cobranza_agent.application.call_backend import CallBackendError
from cobranza_agent.application.conversation_model import ToolCall
from cobranza_agent.infrastructure.http_call_backend import HttpCallBackend

OPEN = {"ended": False, "outcome": None, "summary": None}


def _backend(handler):
    seen = []

    def record(request):
        seen.append(request)
        return handler(request)

    client = httpx.Client(base_url="http://api", transport=httpx.MockTransport(record))
    return HttpCallBackend("http://api", "secret", client), seen


def _json(request):
    return json.loads(request.content) if request.content else None


def test_every_request_carries_the_api_key():
    backend, seen = _backend(lambda r: httpx.Response(200, json={
        "tools": [{"name": "end_call", "description": "End", "input_schema": {"type": "object"}}],
        "disclosure": "Disclosure.", "hardship_questions": ["Q1"]}))
    catalog = backend.catalog()
    assert seen[0].headers["X-API-Key"] == "secret" and seen[0].url.path == "/api/agent/tools"
    assert catalog.tools[0].name == "end_call" and catalog.disclosure == "Disclosure."
    assert catalog.hardship_questions == ("Q1",)


def test_a_key_is_required():
    with pytest.raises(ValueError):
        HttpCallBackend("http://api", "")


def test_open_call_and_run_a_tool():
    def handler(request):
        if request.url.path == "/api/agent/calls":
            return httpx.Response(201, json={"call_id": "c1", "direction": "outbound",
                                             "debtor_name": "Jane Carter", "today": "2026-11-16"})
        return httpx.Response(200, json={"result": {"error": "identity_not_verified", "next_step": "Verify."},
                                         "is_error": True, "call": OPEN})

    backend, seen = _backend(handler)
    opened = backend.open_call(CallDirection.OUTBOUND, None, "ACC-T001")
    assert _json(seen[0]) == {"direction": "outbound", "phone": None, "account": "ACC-T001"}
    assert opened.debtor_name == "Jane Carter" and opened.today == date(2026, 11, 16)
    result = opened.tools.execute(ToolCall("tu1", "get_account_details", {}))
    assert seen[1].url.path == "/api/agent/calls/c1/tools/get_account_details" and _json(seen[1]) == {}
    assert result.tool_call_id == "tu1" and result.is_error
    assert json.loads(result.content) == {"error": "identity_not_verified", "next_step": "Verify."}


def test_the_call_state_follows_the_backend():
    def handler(request):
        if request.url.path == "/api/agent/calls":
            return httpx.Response(201, json={"call_id": "c1", "debtor_name": None, "today": "2026-11-16"})
        if request.url.path.endswith("/close"):
            return httpx.Response(200, json={"ended": True, "outcome": "transferred_to_human",
                                             "summary": "Transferred."})
        return httpx.Response(200, json=OPEN)

    backend, seen = _backend(handler)
    tools = backend.open_call(CallDirection.INBOUND, "+13055550001").tools
    tools.update_transcript("Debtor: hi")
    tools.mark_hung_up()
    tools.close_without_model(CallOutcome.TRANSFERRED_TO_HUMAN, "Technical problem.")
    tools.close_without_model(CallOutcome.CALLBACK_REQUESTED)        # ya cerrada: no se pide de nuevo
    assert [(r.method, r.url.path) for r in seen[1:]] == [
        ("PUT", "/api/agent/calls/c1/transcript"), ("POST", "/api/agent/calls/c1/hangup"),
        ("POST", "/api/agent/calls/c1/close")]
    assert _json(seen[1]) == {"text": "Debtor: hi"}
    assert _json(seen[3]) == {"outcome": "transferred_to_human", "transfer_reason": "Technical problem."}
    assert tools.ended and tools.outcome is CallOutcome.TRANSFERRED_TO_HUMAN and tools.summary == "Transferred."


def test_attach_log_sends_the_uri():
    backend, seen = _backend(lambda r: httpx.Response(200, json=OPEN))
    backend.attach_log("c1", "/app/call_logs/c1.json")
    assert seen[0].url.path == "/api/agent/calls/c1/transcript"
    assert _json(seen[0]) == {"log_uri": "/app/call_logs/c1.json"}


def test_unknown_account_is_a_lookup_error():
    backend, _ = _backend(lambda r: httpx.Response(404, json={"detail": "No existe la cuenta NOPE"}))
    with pytest.raises(LookupError, match="NOPE"):
        backend.open_call(CallDirection.OUTBOUND, None, "NOPE")


@pytest.mark.parametrize("response", [
    httpx.Response(401, json={"detail": "Clave de API inválida"}),
    httpx.Response(500, text="boom"),
    httpx.Response(200, text="not json"),
])
def test_bad_answers_are_backend_errors(response):
    backend, _ = _backend(lambda r: response)
    with pytest.raises(CallBackendError):
        backend.catalog()


def test_network_errors_are_backend_errors():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    backend, _ = _backend(handler)
    with pytest.raises(CallBackendError):
        backend.catalog()
