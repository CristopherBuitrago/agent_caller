"""Contenedor del agente de voz: arma la conversación con Claude sobre la API del backend."""

import os

import anthropic

from cobranza_agent.application.call_backend import CallBackend
from cobranza_agent.application.conversation import StartAgentConversation
from cobranza_agent.application.conversation_model import ConversationModel
from cobranza_agent.infrastructure.claude_conversation_model import ClaudeConversationModel
from cobranza_agent.infrastructure.http_call_backend import HttpCallBackend

# L3: el nombre completo solo se dice al deudor verificado; antes, solo las siglas.
DEFAULT_COMPANY_NAME = "Live Oac Financial"
DEFAULT_COMPANY_SHORT = "L.O.F."
DEFAULT_BACKEND_URL = "http://localhost:8001"


def build_backend() -> HttpCallBackend:
    """La API del backend: BACKEND_URL (por defecto http://localhost:8001) y AGENT_API_KEY."""
    return HttpCallBackend(os.environ.get("BACKEND_URL", DEFAULT_BACKEND_URL),
                           os.environ.get("AGENT_API_KEY", ""))


def build_agent(backend: CallBackend | None = None, model: ConversationModel | None = None,
                company_name: str = DEFAULT_COMPANY_NAME,
                company_short: str = DEFAULT_COMPANY_SHORT) -> StartAgentConversation:
    """Arma el agente conversacional.

    `backend` y `model` se pueden reemplazar (p. ej. en pruebas). Por defecto: la API del backend
    (build_backend) y Claude Haiku 5.5 con Claude Sonnet 5.5 si un turno falla o se rechaza.

    El número para devolver la llamada (N12, AGENT_CALLBACK_NUMBER) lo configura el backend.
    """
    return StartAgentConversation(
        backend or build_backend(), model or ClaudeConversationModel(anthropic.Anthropic()),
        company_name, company_short,
    )
