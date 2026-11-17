"""Paso 8: la conversación del agente con el deudor.

El mismo flujo sirve para el chat de prueba y, más adelante, para la voz: entra texto del
deudor y sale texto del agente. Entre medio, el modelo pide herramientas y el backend las
ejecuta con sus reglas (por HTTP; ver call_backend.py).
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from cobranza_agent.application.call import CallDirection, CallOutcome
from cobranza_agent.application.call_backend import CallBackend, CallBackendError, CallTools, ToolCatalog
from cobranza_agent.application.conversation_model import (
    ConversationModel,
    ConversationModelError,
    ModelConversation,
    ModelTurn,
    ToolCall,
    ToolResult,
    ToolSpec,
)

log = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "agent_system_prompt.md"
# Si el modelo pide más herramientas que esto en un solo turno, algo anda mal: pasa a una persona.
MAX_TOOL_ROUNDS_PER_TURN = 8
FALLBACK_TEXT = "I'm sorry, I'm having trouble on my end. Let me transfer you to a representative."
TECHNICAL_TRANSFER_REASON = "The agent could not continue the call (technical problem)."
# Al colgar, un pedido de "no llamar" o una disputa no se puede perder: end_call no acepta esos
# resultados, solo sus propias herramientas (error E1 de las simulaciones).
HANG_UP_EVENT = (
    "The caller hung up. Do not speak. If at any point in this call the caller asked not to be "
    "called again, call mark_do_not_call. If they said they already paid, that the bank made a "
    "mistake, or that the debt is not theirs, call record_dispute. Otherwise call end_call with "
    "the outcome that fits best."
)


def render_system_prompt(company_name: str, company_short: str, catalog: ToolCatalog) -> str:
    """El prompt no cambia entre llamadas, así se puede cachear.

    `company_short` (L3): lo único que se dice de la empresa antes de verificar (p. ej. "L.O.F.").
    El aviso FDCPA y las Hardship Questions vienen del backend, que es quien las aplica.
    """
    questions = "\n".join(f"{i}. {q}" for i, q in enumerate(catalog.hardship_questions, start=1))
    return (PROMPT_PATH.read_text(encoding="utf-8")
            .replace("{{COMPANY_NAME}}", company_name)
            .replace("{{COMPANY_SHORT}}", company_short)
            .replace("{{DISCLOSURE}}", catalog.disclosure)
            .replace("{{HARDSHIP_QUESTIONS}}", questions))


@dataclass(frozen=True)
class AgentReply:
    text: str
    call_ended: bool
    outcome: CallOutcome | None


ToolObserver = Callable[[ToolCall, ToolResult], None]


class AgentSession:
    """Una llamada en curso."""

    def __init__(self, tools: CallTools, conversation: ModelConversation,
                 on_tool: ToolObserver | None = None):
        self._tools = tools
        self._conversation = conversation
        self._on_tool = on_tool
        self._lines: list[str] = []

    @property
    def call_id(self) -> str:
        return self._tools.call_id

    @property
    def ended(self) -> bool:
        return self._tools.ended

    @property
    def outcome(self) -> CallOutcome | None:
        return self._tools.outcome

    @property
    def summary(self) -> str | None:
        return self._tools.summary

    def transcript(self) -> str:
        return "\n".join(self._lines)

    def call_event(self, event: str) -> AgentReply:
        """Aviso del sistema telefónico (no lo dijo el deudor)."""
        return self._send(f"<call_event>{event}</call_event>")

    def debtor_says(self, text: str) -> AgentReply:
        if self.ended:
            raise ValueError("La llamada ya terminó")
        self._add_line(f"Debtor: {text}")
        return self._send(text)

    def hang_up(self) -> None:
        """El deudor colgó. El modelo elige el resultado; si no cierra, se cierra como volver a llamar."""
        self._tools.mark_hung_up()
        if not self.ended:
            self.call_event(HANG_UP_EVENT)
        self._tools.close_without_model(CallOutcome.CALLBACK_REQUESTED)

    def _add_line(self, line: str) -> None:
        """Guarda la línea y le pasa la conversación al backend (la usa para el resumen al cerrar)."""
        self._lines.append(line)
        try:
            self._tools.update_transcript(self.transcript())
        except CallBackendError:
            log.warning("No se pudo enviar la conversación de la llamada %s", self.call_id, exc_info=True)

    def _send(self, user_text: str) -> AgentReply:
        try:
            return self._run(self._conversation.send_user_text(user_text))
        except ConversationModelError:
            log.warning("El modelo no respondió en la llamada %s", self.call_id, exc_info=True)
            return self._fail()
        except CallBackendError:
            log.warning("El backend no respondió en la llamada %s", self.call_id, exc_info=True)
            return self._fail()

    def _run(self, turn: ModelTurn) -> AgentReply:
        texts = [turn.text]
        rounds = 0
        while turn.tool_calls:
            rounds += 1
            if rounds > MAX_TOOL_ROUNDS_PER_TURN:
                log.warning("Demasiadas herramientas en un turno de la llamada %s", self.call_id)
                return self._fail()
            results = []
            for call in turn.tool_calls:
                result = self._tools.execute(call)
                if self._on_tool:
                    self._on_tool(call, result)
                results.append(result)
            # Todas las respuestas de herramientas del turno van juntas.
            turn = self._conversation.send_tool_results(results)
            texts.append(turn.text)
        return self._reply(" ".join(t.strip() for t in texts if t and t.strip()))

    def _fail(self) -> AgentReply:
        self._add_line(f"Agent: {FALLBACK_TEXT}")
        try:
            self._tools.close_without_model(CallOutcome.TRANSFERRED_TO_HUMAN, TECHNICAL_TRANSFER_REASON)
        except CallBackendError:
            log.error("No se pudo cerrar la llamada %s en el backend", self.call_id, exc_info=True)
        return AgentReply(FALLBACK_TEXT, True, self._tools.outcome or CallOutcome.TRANSFERRED_TO_HUMAN)

    def _reply(self, text: str) -> AgentReply:
        if text:
            self._add_line(f"Agent: {text}")
        return AgentReply(text, self.ended, self._tools.outcome)


class StartAgentConversation:
    """Abre la llamada en el backend y devuelve la sesión con el saludo del agente."""

    def __init__(self, backend: CallBackend, model: ConversationModel, company_name: str,
                 company_short: str):
        self._backend = backend
        self._model = model
        self._company_name = company_name
        self._company_short = company_short
        self._prompt: tuple[str, list[ToolSpec]] | None = None

    def execute(self, direction: CallDirection, caller_phone: str | None,
                account_external_id: str | None = None,
                on_tool: ToolObserver | None = None) -> tuple[AgentSession, AgentReply]:
        """Saliente: basta la cuenta; el backend busca el teléfono. Si no existe, lanza LookupError."""
        system_prompt, tools = self._system_prompt()
        opened = self._backend.open_call(direction, caller_phone, account_external_id)
        session = AgentSession(opened.tools, self._model.start(system_prompt, tools), on_tool)
        return session, session.call_event(self._opening_event(direction, opened.debtor_name, opened.today))

    def _system_prompt(self) -> tuple[str, list[ToolSpec]]:
        """Se pide al backend una sola vez: el prompt no cambia entre llamadas."""
        if self._prompt is None:
            catalog = self._backend.catalog()
            self._prompt = (render_system_prompt(self._company_name, self._company_short, catalog),
                            list(catalog.tools))
        return self._prompt

    @staticmethod
    def _opening_event(direction: CallDirection, debtor_name: str | None, today: date) -> str:
        when = f"Today is {today:%A}, {today:%B} {today.day}, {today.year}."
        if direction is CallDirection.INBOUND:
            return f"Inbound call connected. {when} Greet the caller."
        return (f"Outbound call connected. You are calling {debtor_name or 'the account holder'}. {when} "
                "Greet the person who answered.")
