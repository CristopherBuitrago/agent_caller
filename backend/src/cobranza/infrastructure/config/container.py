"""Contenedor: el único lugar que conecta cada caso de uso con las implementaciones de sus interfaces.

Para cambiar a la base real se cambian los repositorios aquí, y nada más.
"""

from dataclasses import dataclass

import anthropic
from psycopg_pool import ConnectionPool

from cobranza.application.interfaces.call_summarizer import CallSummarizer
from cobranza.application.use_cases.lookup_debtor import FindDebtorsByPhone, GetDebtorByAccount
from cobranza.application.use_cases.negotiate_arrangement import (
    CreateArrangement,
    ProposeArrangement,
    ProposePartialPayment,
    RecordHardshipAssessment,
    _ArrangementGate,
)
from cobranza.application.use_cases.register_call import EndCall, RecordRecordingConsent, StartCall
from cobranza.application.use_cases.verify_identity import VerifyIdentity
from cobranza.infrastructure.repositories.postgres_arrangement_repository import PostgresArrangementRepository
from cobranza.infrastructure.repositories.postgres_call_repository import PostgresCallRepository
from cobranza.infrastructure.repositories.postgres_debtor_repository import PostgresDebtorRepository
from cobranza.infrastructure.repositories.postgres_hardship_repository import PostgresHardshipRepository
from cobranza.infrastructure.repositories.postgres_identity_repository import PostgresIdentityRepository
from cobranza.infrastructure.services.claude_call_summarizer import (
    BACKUP_MODEL,
    PRIMARY_MODEL,
    ClaudeCallSummarizer,
)
from cobranza.infrastructure.services.fallback_call_summarizer import FallbackCallSummarizer
from cobranza.infrastructure.services.hmac_pii_hasher import HmacSha256PiiHasher
from cobranza.infrastructure.services.phonenumbers_phone_service import PhonenumbersPhoneService
from cobranza.infrastructure.services.system_clock import SystemClock


@dataclass(frozen=True)
class UseCases:
    find_debtors_by_phone: FindDebtorsByPhone
    get_debtor_by_account: GetDebtorByAccount
    verify_identity: VerifyIdentity
    start_call: StartCall
    record_recording_consent: RecordRecordingConsent
    end_call: EndCall
    propose_arrangement: ProposeArrangement
    propose_partial_payment: ProposePartialPayment
    create_arrangement: CreateArrangement
    record_hardship_assessment: RecordHardshipAssessment


def build_use_cases(pool: ConnectionPool, pii_hmac_key: str,
                    summarizer: CallSummarizer | None = None) -> UseCases:
    """`summarizer` se puede reemplazar (p. ej. en pruebas).

    Por defecto: Claude Haiku 5.5 y, si rechaza o falla, Claude Sonnet 5.5.
    Credenciales de Claude: ANTHROPIC_API_KEY (o un perfil de `ant auth login`).
    """
    debtors = PostgresDebtorRepository(pool)
    calls = PostgresCallRepository(pool)
    phones = PhonenumbersPhoneService()
    clock = SystemClock()
    if summarizer is None:
        client = anthropic.Anthropic()
        summarizer = FallbackCallSummarizer(
            primary=ClaudeCallSummarizer(client, PRIMARY_MODEL),
            backup=ClaudeCallSummarizer(client, BACKUP_MODEL),
        )
    get_debtor_by_account = GetDebtorByAccount(debtors, phones)
    arrangements = PostgresArrangementRepository(pool)
    hardships = PostgresHardshipRepository(pool)
    gate = _ArrangementGate(calls, arrangements, get_debtor_by_account, clock, hardships)
    return UseCases(
        find_debtors_by_phone=FindDebtorsByPhone(debtors, phones),
        get_debtor_by_account=get_debtor_by_account,
        propose_arrangement=ProposeArrangement(gate),
        propose_partial_payment=ProposePartialPayment(gate),
        create_arrangement=CreateArrangement(gate, arrangements),
        record_hardship_assessment=RecordHardshipAssessment(gate, hardships),
        verify_identity=VerifyIdentity(
            PostgresIdentityRepository(pool), calls, HmacSha256PiiHasher(pii_hmac_key), clock,
        ),
        start_call=StartCall(calls, debtors, phones, clock),
        record_recording_consent=RecordRecordingConsent(calls),
        end_call=EndCall(calls, summarizer, clock),
    )
