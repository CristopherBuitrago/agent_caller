"""API HTTP de las herramientas del agente de voz.

Las usa nuestro agente (carpeta agente/) y las puede usar cualquier plataforma de voz externa:
las reglas, los montos y las fechas siguen saliendo de este backend.

Uso (desde la raíz del repositorio, con la base levantada):
    docker compose up api        ->  http://localhost:8001   (documentación: /docs)

Endpoints (todos piden el encabezado X-API-Key; sin la clave correcta responden 401):
    GET  /api/agent/tools                          herramientas, aviso FDCPA y Hardship Questions
    POST /api/agent/calls                          abre una llamada -> call_id
    POST /api/agent/calls/{call_id}/tools/{name}   ejecuta una herramienta (el cuerpo son sus campos)
    GET  /api/agent/calls/{call_id}                estado: si terminó, el resultado y el resumen
    PUT  /api/agent/calls/{call_id}/transcript     conversación hasta ahora (para el resumen) y
                                                   ruta del historial
    POST /api/agent/calls/{call_id}/hangup         el deudor colgó: ninguna herramienta pide hablar
    POST /api/agent/calls/{call_id}/close          cierra sin el modelo (falló o nadie eligió resultado)

Los errores de una herramienta (regla incumplida, dato mal formado, herramienta desconocida,
llamada terminada) responden 200 con is_error true y un next_step: son instrucciones para el
modelo, no fallas del servidor.

Las llamadas abiertas viven en memoria de este proceso: sirve con un solo servidor.
Necesita AGENT_API_KEY, DATABASE_URL y PII_HMAC_KEY. AGENT_CALLBACK_NUMBER es opcional (N12).
"""

import hmac
import json
import os
import threading
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Literal

from fastapi import Body, Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from cobranza.application.agent_tools import TOOL_SPECS, DISCLOSURE, AgentUseCases, CallTools, ToolCall
from cobranza.application.interfaces.clock import Clock
from cobranza.application.use_cases.register_call import AttachTranscript, StartCall
from cobranza.domain.call import CallDirection, CallOutcome
from cobranza.domain.hardship import HARDSHIP_QUESTIONS

# Una llamada terminada se puede consultar durante este tiempo; después se borra de la memoria.
ENDED_CALL_TTL_SECONDS = 3600


@dataclass(frozen=True)
class ApiDeps:
    """Lo que necesita la API. En producción lo arma `production_app`; en pruebas, dobles."""
    tools_use_cases: AgentUseCases
    start_call: StartCall
    attach_transcript: AttachTranscript
    clock: Clock
    callback_number: str | None = None
    # Demo en el navegador: la entrante busca al deudor por el nombre dicho (DEMO_LOOKUP_BY_NAME).
    lookup_by_name: bool = False


class OpenCallRequest(BaseModel):
    direction: Literal["inbound", "outbound"]
    phone: str | None = Field(None, description="Entrante: teléfono desde el que llama el deudor")
    account: str | None = Field(None, description="Saliente: cuenta del job (p. ej. ACC-T001)")


class TranscriptRequest(BaseModel):
    text: str | None = Field(None, description="La conversación hasta ahora, una línea por turno")
    log_uri: str | None = Field(None, description="Ruta del historial de la llamada (calls.transcript_uri)")


class CloseRequest(BaseModel):
    # Lo único con lo que se puede cerrar una llamada sin el modelo.
    outcome: Literal["transferred_to_human", "callback_requested"]
    transfer_reason: str | None = Field(None, max_length=500)


@dataclass
class _ApiCall:
    tools: CallTools
    transcript: str = ""
    log_attached: bool = False
    ended_at: float | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def state(self) -> dict[str, Any]:
        return {"call_id": self.tools.call_id, "ended": self.tools.ended,
                "outcome": self.tools.outcome.value if self.tools.outcome else None,
                "summary": self.tools.summary, "transferred": self.tools.transferred}


def create_app(deps: Callable[[], ApiDeps], api_key: str, lifespan=None) -> FastAPI:
    """`deps` se pide en cada llamada nueva (en producción existe solo después del arranque)."""
    if not api_key:
        raise ValueError("Falta la clave de la API (AGENT_API_KEY)")
    app = FastAPI(title="Cobranza NSF: herramientas del agente", lifespan=lifespan)
    calls: dict[str, _ApiCall] = {}
    calls_lock = threading.Lock()

    def require_key(x_api_key: str | None = Header(None)) -> None:
        if x_api_key is None or not hmac.compare_digest(x_api_key.encode(), api_key.encode()):
            raise HTTPException(401, "Clave de API inválida o ausente (encabezado X-API-Key)")

    def get(call_id: str) -> _ApiCall:
        call = calls.get(call_id)
        if call is None:
            raise HTTPException(404, "Llamada desconocida")
        return call

    def forget_old_calls() -> None:
        limit = time.monotonic() - ENDED_CALL_TTL_SECONDS
        with calls_lock:
            for call_id in [k for k, c in calls.items() if c.ended_at and c.ended_at < limit]:
                del calls[call_id]

    def after_change(call: _ApiCall) -> dict[str, Any]:
        if call.tools.ended and call.ended_at is None:
            call.ended_at = time.monotonic()
        return call.state()

    auth = [Depends(require_key)]

    @app.get("/api/agent/tools", dependencies=auth)
    def tools() -> dict:
        return {
            "tools": [{"name": s.name, "description": s.description, "input_schema": s.input_schema}
                      for s in TOOL_SPECS],
            "disclosure": DISCLOSURE,
            "hardship_questions": list(HARDSHIP_QUESTIONS),
        }

    @app.post("/api/agent/calls", dependencies=auth, status_code=201)
    def open_call(body: OpenCallRequest) -> dict:
        forget_old_calls()
        d = deps()
        debtor_name = None
        if body.direction == "inbound":
            if not body.phone:
                raise HTTPException(422, "Una llamada entrante necesita el teléfono")
            direction, phone = CallDirection.INBOUND, body.phone
        else:
            if not body.account:
                raise HTTPException(422, "Una llamada saliente necesita la cuenta")
            debtor = d.tools_use_cases.get_debtor_by_account.execute(body.account)
            if debtor is None:
                raise HTTPException(404, f"No existe la cuenta {body.account}")
            direction, phone = CallDirection.OUTBOUND, debtor.phone_primary
            debtor_name = f"{debtor.first_name} {debtor.last_name}"
        call_id = d.start_call.execute(direction, phone, body.account if body.direction == "outbound" else None)
        holder: dict[str, _ApiCall] = {}
        tools = CallTools(d.tools_use_cases, call_id, direction, phone,
                          body.account if direction is CallDirection.OUTBOUND else None,
                          transcript=lambda: holder["call"].transcript, clock=d.clock,
                          callback_number=d.callback_number, lookup_by_name=d.lookup_by_name)
        holder["call"] = call = _ApiCall(tools)
        with calls_lock:
            calls[call_id] = call
        return {"call_id": call_id, "direction": direction.value, "debtor_name": debtor_name,
                "today": d.clock.now().date().isoformat()}

    @app.get("/api/agent/calls/{call_id}", dependencies=auth)
    def call_state(call_id: str) -> dict:
        return get(call_id).state()

    @app.post("/api/agent/calls/{call_id}/tools/{name}", dependencies=auth)
    def run_tool(call_id: str, name: str, tool_input: dict[str, Any] | None = Body(None)) -> dict:
        call = get(call_id)
        with call.lock:
            result = call.tools.execute(ToolCall(f"http-{name}", name, tool_input or {}))
            return {"result": json.loads(result.content), "is_error": result.is_error,
                    "call": after_change(call)}

    @app.put("/api/agent/calls/{call_id}/transcript", dependencies=auth)
    def transcript(call_id: str, body: TranscriptRequest) -> dict:
        call = get(call_id)
        with call.lock:
            if body.text is not None:
                call.transcript = body.text
            if body.log_uri and not call.log_attached:
                deps().attach_transcript.execute(call_id, body.log_uri)
                call.log_attached = True
            return call.state()

    @app.post("/api/agent/calls/{call_id}/hangup", dependencies=auth)
    def hangup(call_id: str) -> dict:
        call = get(call_id)
        with call.lock:
            call.tools.caller_hung_up = True
            return call.state()

    @app.post("/api/agent/calls/{call_id}/close", dependencies=auth)
    def close(call_id: str, body: CloseRequest) -> dict:
        call = get(call_id)
        with call.lock:
            call.tools.close_without_model(CallOutcome(body.outcome), body.transfer_reason)
            return after_change(call)

    return app


def build_api_deps(use_cases, clock: Clock, callback_number: str | None = None,
                   lookup_by_name: bool = False) -> ApiDeps:
    """Arma las dependencias de la API con los casos de uso del contenedor del núcleo."""
    return ApiDeps(
        tools_use_cases=AgentUseCases(
            find_debtors_by_phone=use_cases.find_debtors_by_phone,
            get_debtor_by_account=use_cases.get_debtor_by_account,
            record_recording_consent=use_cases.record_recording_consent,
            verify_identity=use_cases.verify_identity,
            end_call=use_cases.end_call,
            propose_next_offer=use_cases.propose_next_offer,
            propose_partial_payment=use_cases.propose_partial_payment,
            record_offer_response=use_cases.record_offer_response,
            record_hardship_assessment=use_cases.record_hardship_assessment,
            record_dispute=use_cases.record_dispute,
            mark_do_not_call=use_cases.mark_do_not_call,
            record_collection_hold=use_cases.record_collection_hold,
            get_last_contact=use_cases.get_last_contact,
            schedule_callback=use_cases.schedule_callback,
            find_debtors_by_name=use_cases.find_debtors_by_name,
            get_debtor_by_id=use_cases.get_debtor_by_id,
        ),
        start_call=use_cases.start_call,
        attach_transcript=use_cases.attach_transcript,
        clock=clock,
        callback_number=callback_number,
        lookup_by_name=lookup_by_name,
    )


def production_app() -> FastAPI:
    """App real: PostgreSQL + resumen con Claude. La arranca uvicorn con --factory (ver docker-compose.yml)."""
    from psycopg_pool import ConnectionPool

    from cobranza.infrastructure.config.container import build_use_cases
    from cobranza.infrastructure.services.system_clock import SystemClock

    state: dict[str, ApiDeps] = {}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        with ConnectionPool(os.environ["DATABASE_URL"], min_size=1, max_size=4) as pool:
            state["deps"] = build_api_deps(
                build_use_cases(pool, os.environ["PII_HMAC_KEY"]), SystemClock(),
                os.environ.get("AGENT_CALLBACK_NUMBER") or None,
                os.environ.get("DEMO_LOOKUP_BY_NAME", "").lower() == "true")
            yield

    return create_app(lambda: state["deps"], os.environ.get("AGENT_API_KEY", ""), lifespan)

