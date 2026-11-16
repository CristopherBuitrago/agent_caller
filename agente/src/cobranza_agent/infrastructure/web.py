"""API y página web del chat de prueba (demo en el navegador o el celular), con historial.

Usa el mismo agente que el chat de terminal: Claude conversa y las herramientas aplican las reglas.

Uso (desde backend/, con la base levantada y ANTHROPIC_API_KEY en backend/.env):
    docker compose up web        ->  http://localhost:8000   (historial: /historial)

Endpoints:
    POST /api/calls                    abre una llamada y devuelve el saludo del agente
    POST /api/calls/{call_id}/messages lo que dice el deudor -> respuesta del agente
    POST /api/calls/{call_id}/hangup   el deudor cuelga -> resultado y resumen
    GET  /api/history                  llamadas guardadas (más recientes primero)
    GET  /api/history/{call_id}        conversación completa de una llamada, con sus herramientas

Las llamadas abiertas viven en memoria de este proceso (sirve para la demo con un solo servidor).
El historial se guarda en archivos JSON (CALL_LOG_DIR) y su ruta queda en calls.transcript_uri.
"""

import os
import threading
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from cobranza_agent.application.conversation import AgentReply, AgentSession, ToolObserver
from cobranza_agent.application.conversation_model import ToolCall, ToolResult
from cobranza_agent.infrastructure.call_log import CallLog, CallLogStore
from cobranza.domain.call import CallDirection

STATIC = Path(__file__).resolve().parent / "static"
# Lo que se muestra de cada herramienta en el chat (las respuestas largas se cortan).
MAX_TOOL_RESULT_CHARS = 400

# Abre una llamada: (dirección, teléfono, cuenta del job, observador de herramientas) -> sesión y saludo.
# Si la cuenta no existe, lanza LookupError.
OpenCall = Callable[[CallDirection, str | None, str | None, ToolObserver],
                    tuple[AgentSession, AgentReply]]
# Se llama una vez por llamada con la ruta de su historial (para calls.transcript_uri).
OnLogSaved = Callable[[str, str], None]


class StartCallRequest(BaseModel):
    direction: Literal["inbound", "outbound"] = "inbound"
    phone: str | None = Field(None, description="Entrante: teléfono desde el que llama el deudor")
    account: str | None = Field(None, description="Saliente: cuenta del job (p. ej. ACC-T001)")
    label: str | None = Field(None, max_length=120, description="Nombre del caso, para el historial")


class MessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


@dataclass
class _OpenCall:
    session: AgentSession
    log: CallLog
    tools: list[dict] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def take_tools(self) -> list[dict]:
        taken, self.tools = self.tools, []
        return taken


def create_app(open_call: OpenCall, lifespan=None, store: CallLogStore | None = None,
               on_log_saved: OnLogSaved | None = None) -> FastAPI:
    app = FastAPI(title="Agente de cobranza NSF: chat de prueba", lifespan=lifespan)
    calls: dict[str, _OpenCall] = {}

    def get(call_id: str) -> _OpenCall:
        call = calls.get(call_id)
        if call is None:
            raise HTTPException(404, "Llamada desconocida")
        return call

    def save(call: _OpenCall, first: bool = False) -> None:
        if store is None:
            return
        path = store.save(call.log)
        if first and on_log_saved is not None:
            on_log_saved(call.log.call_id, str(path))

    def reply(call: _OpenCall, answer: AgentReply) -> dict:
        call.log.agent(answer.text)
        if answer.call_ended:
            call.log.end(answer.outcome.value if answer.outcome else None, call.session.summary)
        save(call)
        return {"call_id": call.log.call_id, "reply": answer.text, "ended": answer.call_ended,
                "outcome": answer.outcome.value if answer.outcome else None, "tools": call.take_tools()}

    @app.get("/", response_class=HTMLResponse)
    def page() -> str:
        return (STATIC / "chat.html").read_text(encoding="utf-8")

    @app.get("/historial", response_class=HTMLResponse)
    def history_page() -> str:
        return (STATIC / "history.html").read_text(encoding="utf-8")

    @app.post("/api/calls")
    def start(body: StartCallRequest) -> dict:
        if body.direction == "inbound" and not body.phone:
            raise HTTPException(422, "Una llamada entrante necesita el teléfono")
        if body.direction == "outbound" and not body.account:
            raise HTTPException(422, "Una llamada saliente necesita la cuenta")
        pending: list[tuple[ToolCall, ToolResult]] = []   # herramientas antes de que exista la llamada
        holder: dict[str, _OpenCall] = {}

        def on_tool(tool_call: ToolCall, result: ToolResult) -> None:
            if "call" not in holder:
                pending.append((tool_call, result))
                return
            _record_tool(holder["call"], tool_call, result)

        direction = CallDirection.INBOUND if body.direction == "inbound" else CallDirection.OUTBOUND
        try:
            session, answer = open_call(direction, body.phone, body.account, on_tool)
        except LookupError as e:
            raise HTTPException(404, str(e)) from None
        scenario = body.model_dump()
        log = CallLog(session.call_id, scenario)
        who = f"desde {body.phone}" if direction is CallDirection.INBOUND else f"a la cuenta {body.account}"
        log.system(f"Llamada {'entrante' if direction is CallDirection.INBOUND else 'saliente'} {who}")
        call = holder["call"] = _OpenCall(session, log)
        for tool_call, result in pending:
            _record_tool(call, tool_call, result)
        calls[session.call_id] = call
        save(call, first=True)
        return reply(call, answer)

    @app.post("/api/calls/{call_id}/messages")
    def message(call_id: str, body: MessageRequest) -> dict:
        call = get(call_id)
        with call.lock:
            if call.session.ended:
                raise HTTPException(409, "La llamada ya terminó")
            text = body.text.strip()
            call.log.debtor(text)
            return reply(call, call.session.debtor_says(text))

    @app.post("/api/calls/{call_id}/hangup")
    def hangup(call_id: str) -> dict:
        call = get(call_id)
        with call.lock:
            if not call.session.ended:
                call.log.system("El deudor colgó")
            call.session.hang_up()
            outcome = call.session.outcome.value if call.session.outcome else None
            if call.log.ended_at is None:
                call.log.end(outcome, call.session.summary)
            save(call)
            result = {"call_id": call_id, "ended": True, "outcome": outcome,
                      "summary": call.session.summary, "tools": call.take_tools()}
        calls.pop(call_id, None)
        return result

    @app.get("/api/history")
    def history() -> list[dict]:
        return store.list() if store else []

    @app.get("/api/history/{call_id}")
    def history_detail(call_id: str) -> dict:
        data = store.get(call_id) if store else None
        if data is None:
            raise HTTPException(404, "No hay historial de esa llamada")
        return data

    return app


def _record_tool(call: _OpenCall, tool_call: ToolCall, result: ToolResult) -> None:
    call.tools.append({"name": tool_call.name, "error": result.is_error,
                       "result": result.content[:MAX_TOOL_RESULT_CHARS]})
    call.log.tool(tool_call.name, dict(tool_call.input), result.content, result.is_error)


def _production_app() -> FastAPI:
    """App real: PostgreSQL + Claude. Se arma al arrancar el servidor."""
    from psycopg_pool import ConnectionPool

    from cobranza_agent.infrastructure.container import build_agent
    from cobranza.infrastructure.config.container import build_use_cases

    state: dict = {}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("Falta ANTHROPIC_API_KEY (en backend/.env)")
        with ConnectionPool(os.environ["DATABASE_URL"], min_size=1, max_size=4) as pool:
            state["use_cases"] = build_use_cases(pool, os.environ["PII_HMAC_KEY"])
            state["agent"] = build_agent(state["use_cases"])
            yield

    def open_call(direction: CallDirection, phone: str | None, account: str | None,
                  on_tool: ToolObserver) -> tuple[AgentSession, AgentReply]:
        if direction is CallDirection.OUTBOUND:
            debtor = state["use_cases"].get_debtor_by_account.execute(account)
            if debtor is None:
                raise LookupError(f"No existe la cuenta {account}")
            phone = debtor.phone_primary
        return state["agent"].execute(direction, phone, account, on_tool=on_tool)

    def on_log_saved(call_id: str, uri: str) -> None:
        state["use_cases"].attach_transcript.execute(call_id, uri)

    store = CallLogStore(Path(os.environ.get("CALL_LOG_DIR", "call_logs")))
    return create_app(open_call, lifespan, store, on_log_saved)


app = _production_app()
