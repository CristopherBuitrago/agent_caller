"""Implementación de CallBackend con la API HTTP del backend (cobranza.infrastructure.api).

Cada pedido lleva la clave en el encabezado X-API-Key. Si el backend no responde o responde algo
inesperado, se lanza CallBackendError y el agente pasa la llamada a una persona.
"""

import json
import logging
from datetime import date
from typing import Any

import httpx

from cobranza_agent.application.call import CallDirection, CallOutcome
from cobranza_agent.application.call_backend import CallBackendError, OpenedCall, ToolCatalog
from cobranza_agent.application.conversation_model import ToolCall, ToolResult, ToolSpec

log = logging.getLogger(__name__)

# Una herramienta puede esperar al resumen con Claude al cerrar la llamada.
TIMEOUT_SECONDS = 60.0


class HttpCallBackend:
    def __init__(self, base_url: str, api_key: str, client: httpx.Client | None = None):
        """`client` se puede reemplazar (p. ej. en pruebas, con la app del backend en memoria)."""
        if not api_key:
            raise ValueError("Falta la clave de la API del backend (AGENT_API_KEY)")
        self._client = client or httpx.Client(base_url=base_url, timeout=TIMEOUT_SECONDS)
        self._headers = {"X-API-Key": api_key}

    def catalog(self) -> ToolCatalog:
        body = self.request("GET", "/api/agent/tools")
        return ToolCatalog(
            tools=tuple(ToolSpec(t["name"], t["description"], t["input_schema"]) for t in body["tools"]),
            disclosure=body["disclosure"],
            hardship_questions=tuple(body["hardship_questions"]),
        )

    def open_call(self, direction: CallDirection, phone: str | None,
                  account: str | None = None) -> OpenedCall:
        body = self.request("POST", "/api/agent/calls",
                            {"direction": direction.value, "phone": phone, "account": account})
        return OpenedCall(HttpCallTools(self, body["call_id"]), body.get("debtor_name"),
                          date.fromisoformat(body["today"]))

    def attach_log(self, call_id: str, uri: str) -> None:
        """Ruta del historial de la llamada (queda en calls.transcript_uri)."""
        self.request("PUT", f"/api/agent/calls/{call_id}/transcript", {"log_uri": uri})

    def request(self, method: str, path: str, payload: Any = None) -> Any:
        try:
            response = self._client.request(method, path, headers=self._headers,
                                            json=payload)
        except httpx.HTTPError as e:
            raise CallBackendError(f"{method} {path}: {e}") from e
        if response.status_code == 404 and path == "/api/agent/calls":
            raise LookupError(_detail(response))
        if response.status_code >= 400:
            raise CallBackendError(f"{method} {path}: {response.status_code} {_detail(response)}")
        try:
            return response.json()
        except ValueError as e:
            raise CallBackendError(f"{method} {path}: la respuesta no es JSON") from e


class HttpCallTools:
    """Una llamada abierta en el backend. Guarda el último estado que devolvió."""

    def __init__(self, backend: HttpCallBackend, call_id: str):
        self._backend = backend
        self.call_id = call_id
        self.ended = False
        self.outcome: CallOutcome | None = None
        self.summary: str | None = None

    def execute(self, call: ToolCall) -> ToolResult:
        body = self._backend.request("POST", f"/api/agent/calls/{self.call_id}/tools/{call.name}",
                                     dict(call.input))
        self._update(body["call"])
        return ToolResult(call.id, json.dumps(body["result"], ensure_ascii=False), bool(body["is_error"]))

    def update_transcript(self, text: str) -> None:
        self._backend.request("PUT", f"/api/agent/calls/{self.call_id}/transcript", {"text": text})

    def mark_hung_up(self) -> None:
        self._update(self._backend.request("POST", f"/api/agent/calls/{self.call_id}/hangup"))

    def close_without_model(self, outcome: CallOutcome, transfer_reason: str | None = None) -> None:
        if self.ended:
            return
        self._update(self._backend.request("POST", f"/api/agent/calls/{self.call_id}/close",
                                           {"outcome": outcome.value, "transfer_reason": transfer_reason}))

    def _update(self, state: dict) -> None:
        self.ended = bool(state["ended"])
        self.outcome = CallOutcome(state["outcome"]) if state.get("outcome") else None
        self.summary = state.get("summary")


def _detail(response: httpx.Response) -> str:
    try:
        return str(response.json().get("detail", ""))
    except ValueError:
        return response.text[:200]
