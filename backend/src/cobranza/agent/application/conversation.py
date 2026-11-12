"""Paso 8: la conversación del agente con el deudor.

El mismo flujo sirve para el chat de prueba y, más adelante, para la voz: entra texto del
deudor y sale texto del agente. Entre medio, el modelo pide herramientas y CallTools las
ejecuta con los casos de uso.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from cobranza.application.interfaces.clock import Clock
from cobranza.agent.application.conversation_model import (
    ConversationModel,
    ConversationModelError,
    ModelConversation,
    ModelTurn,
    ToolCall,
    ToolResult,
)
from cobranza.agent.application.tools import DISCLOSURE, TOOL_SPECS, AgentUseCases, CallTools
from cobranza.application.use_cases.register_call import StartCall
from cobranza.domain.call import CallDirection, CallOutcome
from cobranza.domain.hardship import HARDSHIP_QUESTIONS

log = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "agent_system_prompt.md"
# Si el modelo pide más herramientas que esto en un solo turno, algo anda mal: pasa a una persona.
MAX_TOOL_ROUNDS_PER_TURN = 8
FALLBACK_TEXT = "I'm sorry, I'm having trouble on my end. Let me transfer you to a representative."
# Al colgar, un pedido de "no llamar" o una disputa no se puede perder: end_call no acepta esos
# resultados, solo sus propias herramientas (error E1 de las simulaciones).
HANG_UP_EVENT = (
    "The caller hung up. Do not speak. If at any point in this call the caller asked not to be "
    "called again, call mark_do_not_call. If they said they already paid, that the bank made a "
    "mistake, or that the debt is not theirs, call record_dispute. Otherwise call end_call with "
    "the outcome that fits best."
)


def render_system_prompt(company_name: str) -> str:
    """El prompt no cambia entre llamadas, así se puede cachear."""
    questions = "\n".join(f"{i}. {q}" for i, q in enumerate(HARDSHIP_QUESTIONS, start=1))
    return (PROMPT_PATH.read_text(encoding="utf-8")
            .replace("{{COMPANY_NAME}}", company_name)
            .replace("{{DISCLOSURE}}", DISCLOSURE)
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
        self._lines.append(f"Debtor: {text}")
        return self._send(text)

    def hang_up(self) -> None:
        """El deudor colgó. El modelo elige el resultado; si no cierra, se cierra como volver a llamar."""
        if not self.ended:
            self.call_event(HANG_UP_EVENT)
        self._tools.close_without_model(CallOutcome.CALLBACK_REQUESTED)

    def _send(self, user_text: str) -> AgentReply:
        try:
            return self._run(self._conversation.send_user_text(user_text))
        except ConversationModelError:
            log.warning("El modelo no respondió en la llamada %s", self.call_id, exc_info=True)
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
        self._lines.append(f"Agent: {FALLBACK_TEXT}")
        self._tools.close_without_model(CallOutcome.TRANSFERRED_TO_HUMAN)
        return AgentReply(FALLBACK_TEXT, True, self._tools.outcome)

    def _reply(self, text: str) -> AgentReply:
        if text:
            self._lines.append(f"Agent: {text}")
        return AgentReply(text, self.ended, self._tools.outcome)


class StartAgentConversation:
    """Abre la llamada y devuelve la sesión con el saludo del agente."""

    def __init__(self, uc: AgentUseCases, start_call: StartCall, model: ConversationModel,
                 clock: Clock, company_name: str):
        self._uc = uc
        self._start_call = start_call
        self._model = model
        self._clock = clock
        self._system_prompt = render_system_prompt(company_name)

    def execute(self, direction: CallDirection, caller_phone: str,
                account_external_id: str | None = None,
                on_tool: ToolObserver | None = None) -> tuple[AgentSession, AgentReply]:
        call_id = self._start_call.execute(direction, caller_phone, account_external_id)
        session: AgentSession | None = None
        tools = CallTools(self._uc, call_id, direction, caller_phone, account_external_id, clock=self._clock,
                          transcript=lambda: session.transcript() if session else "")
        session = AgentSession(tools, self._model.start(self._system_prompt, list(TOOL_SPECS)), on_tool)
        return session, session.call_event(self._opening_event(direction, account_external_id))

    def _opening_event(self, direction: CallDirection, account_external_id: str | None) -> str:
        today = self._clock.now().date()
        when = f"Today is {today:%A}, {today:%B} {today.day}, {today.year}."
        if direction is CallDirection.INBOUND:
            return f"Inbound call connected. {when} Greet the caller."
        debtor = self._uc.get_debtor_by_account.execute(account_external_id)
        name = f"{debtor.first_name} {debtor.last_name}" if debtor else "the account holder"
        return (f"Outbound call connected. You are calling {name}. {when} Greet the person who "
                "answered.")
