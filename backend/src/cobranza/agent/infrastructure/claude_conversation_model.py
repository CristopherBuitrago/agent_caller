"""Implementación de ConversationModel con Claude (API de Anthropic).

Claude Haiku 5.5 conversa; si falla o rechaza un turno, ese turno lo responde Claude Sonnet 5.5.
El prompt y las herramientas no cambian durante la llamada, así que se cachean: en cada turno
el modelo vuelve a leer todo, pero lo repetido cuesta la décima parte.
"""

import logging

import anthropic

from cobranza.agent.application.conversation_model import (
    ConversationModelError,
    ModelTurn,
    ToolCall,
    ToolResult,
    ToolSpec,
)
from cobranza.infrastructure.services.claude_call_summarizer import BACKUP_MODEL, PRIMARY_MODEL

log = logging.getLogger(__name__)

MAX_TOKENS = 4096
# En una llamada importa la rapidez: el flujo y las reglas ya los fijan el prompt y las herramientas.
EFFORT = "low"


class ClaudeConversationModel:
    def __init__(self, client: anthropic.Anthropic, primary: str = PRIMARY_MODEL,
                 backup: str | None = BACKUP_MODEL):
        self._client = client
        self._models = tuple(m for m in (primary, backup) if m)

    def start(self, system_prompt: str, tools: list[ToolSpec]) -> "ClaudeConversation":
        return ClaudeConversation(self._client, self._models, system_prompt, tools)


class ClaudeConversation:
    def __init__(self, client: anthropic.Anthropic, models: tuple[str, ...], system_prompt: str,
                 tools: list[ToolSpec]):
        self._client = client
        self._models = models
        self._system = system_prompt
        self._tools = [{"name": t.name, "description": t.description, "input_schema": t.input_schema}
                       for t in tools]
        self._messages: list[dict] = []

    def send_user_text(self, text: str) -> ModelTurn:
        self._messages.append({"role": "user", "content": text})
        return self._request()

    def send_tool_results(self, results: list[ToolResult]) -> ModelTurn:
        self._messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": r.tool_call_id, "content": r.content,
             "is_error": r.is_error}
            for r in results
        ]})
        return self._request()

    def _request(self) -> ModelTurn:
        for model in self._models:
            try:
                response = self._client.messages.create(
                    model=model,
                    max_tokens=MAX_TOKENS,
                    system=self._system,
                    tools=self._tools,
                    messages=self._messages,
                    cache_control={"type": "ephemeral"},
                    output_config={"effort": EFFORT},
                )
            except anthropic.APIError:
                log.warning("Falló %s; se intenta con el siguiente modelo", model, exc_info=True)
                continue
            if response.stop_reason == "refusal":
                log.warning("%s rechazó el turno; se intenta con el siguiente modelo", model)
                continue
            # Se devuelve el contenido completo (incluido el razonamiento), como pide la API.
            self._messages.append({"role": "assistant", "content": response.content})
            return ModelTurn(
                text="".join(b.text for b in response.content if b.type == "text").strip(),
                tool_calls=tuple(ToolCall(b.id, b.name, dict(b.input))
                                 for b in response.content if b.type == "tool_use"),
            )
        raise ConversationModelError("Ningún modelo respondió el turno")
