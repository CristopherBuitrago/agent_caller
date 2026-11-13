"""Contenedor del agente de voz: arma la conversación sobre los casos de uso del núcleo."""

import os

import anthropic

from cobranza.agent.application.conversation import StartAgentConversation
from cobranza.agent.application.conversation_model import ConversationModel
from cobranza.agent.application.tools import AgentUseCases
from cobranza.agent.infrastructure.claude_conversation_model import ClaudeConversationModel
from cobranza.infrastructure.config.container import UseCases
from cobranza.infrastructure.services.system_clock import SystemClock

# L3: el nombre completo solo se dice al deudor verificado; antes, solo las siglas.
DEFAULT_COMPANY_NAME = "Live Oak Financial"
DEFAULT_COMPANY_SHORT = "L.O.F."


def build_agent(use_cases: UseCases, model: ConversationModel | None = None,
                company_name: str = DEFAULT_COMPANY_NAME,
                company_short: str = DEFAULT_COMPANY_SHORT,
                callback_number: str | None = None) -> StartAgentConversation:
    """Arma el agente conversacional sobre los casos de uso.

    `model` se puede reemplazar (p. ej. en pruebas). Por defecto: Claude Haiku 5.5 y, si un
    turno falla o se rechaza, Claude Sonnet 5.5.

    `callback_number` (N12): la línea de entrada que atiende el agente, para quien no logra
    verificarse. Si no se pasa, se toma de AGENT_CALLBACK_NUMBER; si tampoco existe, no se ofrece.
    """
    callback_number = callback_number or os.environ.get("AGENT_CALLBACK_NUMBER") or None
    agent_use_cases = AgentUseCases(
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
        get_last_contact=use_cases.get_last_contact,
    )
    return StartAgentConversation(
        agent_use_cases, use_cases.start_call,
        model or ClaudeConversationModel(anthropic.Anthropic()), SystemClock(), company_name,
        company_short, callback_number,
    )
