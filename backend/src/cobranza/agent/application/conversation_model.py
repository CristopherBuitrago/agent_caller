"""Interfaz del modelo que conversa con el deudor. No depende de ningún proveedor.

Implementación: infrastructure/services/claude_conversation_model.py
"""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolSpec:
    """Una herramienta que el modelo puede pedir. input_schema es JSON Schema."""
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass(frozen=True)
class ModelTurn:
    """Lo que respondió el modelo: texto para el deudor y/o herramientas a ejecutar."""
    text: str
    tool_calls: tuple[ToolCall, ...] = field(default_factory=tuple)


class ConversationModelError(Exception):
    """El modelo no respondió (red, API, rechazo). El agente transfiere a una persona."""


class ModelConversation(Protocol):
    """Una conversación en curso; guarda su propio historial."""

    def send_user_text(self, text: str) -> ModelTurn: ...

    def send_tool_results(self, results: list[ToolResult]) -> ModelTurn:
        """Devuelve los resultados de todas las herramientas del turno anterior, juntos."""
        ...


class ConversationModel(Protocol):
    def start(self, system_prompt: str, tools: list[ToolSpec]) -> ModelConversation: ...
