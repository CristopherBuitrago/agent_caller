"""Interfaz del backend que ejecuta las herramientas de la llamada. No depende de cómo se llega a él.

Implementación: infrastructure/http_call_backend.py (API HTTP del backend, con X-API-Key).
"""

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from cobranza_agent.application.call import CallDirection, CallOutcome
from cobranza_agent.application.conversation_model import ToolCall, ToolResult, ToolSpec


class CallBackendError(Exception):
    """El backend no respondió o respondió algo inesperado. El agente pasa la llamada a una persona."""


@dataclass(frozen=True)
class ToolCatalog:
    """Lo que el backend publica para armar el prompt: herramientas, aviso FDCPA y Hardship Questions."""
    tools: tuple[ToolSpec, ...]
    disclosure: str
    hardship_questions: tuple[str, ...]


class CallTools(Protocol):
    """Una llamada abierta en el backend: ejecuta sus herramientas y guarda lo que pasó en ella."""

    call_id: str

    @property
    def ended(self) -> bool: ...

    @property
    def outcome(self) -> CallOutcome | None: ...

    @property
    def summary(self) -> str | None: ...

    def execute(self, call: ToolCall) -> ToolResult: ...

    def update_transcript(self, text: str) -> None:
        """La conversación hasta ahora; el backend la usa para el resumen al cerrar."""
        ...

    def mark_hung_up(self) -> None:
        """El deudor colgó: desde ahora ninguna herramienta le pide al agente que hable."""
        ...

    def close_without_model(self, outcome: CallOutcome, transfer_reason: str | None = None) -> None:
        """Cierra la llamada si sigue abierta (el modelo falló o nadie eligió resultado)."""
        ...


@dataclass(frozen=True)
class OpenedCall:
    tools: CallTools
    debtor_name: str | None   # saliente: a quién se llama
    today: date


class CallBackend(Protocol):
    def catalog(self) -> ToolCatalog: ...

    def open_call(self, direction: CallDirection, phone: str | None,
                  account: str | None = None) -> OpenedCall:
        """Entrante: con el teléfono. Saliente: con la cuenta (el backend busca el teléfono).
        Si la cuenta no existe, lanza LookupError."""
        ...
