"""Función 3: registrar la llamada (inicio, consentimiento de grabación y cierre)."""

import logging

from cobranza.application.interfaces.call_repository import CallRepository
from cobranza.application.interfaces.call_summarizer import CallSummarizer, SummarizationError
from cobranza.application.interfaces.clock import Clock
from cobranza.application.interfaces.debtor_repository import DebtorRepository
from cobranza.application.interfaces.phone_service import PhoneService
from cobranza.domain.call import CallDirection, CallOutcome, check_can_close

log = logging.getLogger(__name__)


class StartCall:
    def __init__(self, calls: CallRepository, debtors: DebtorRepository, phones: PhoneService, clock: Clock):
        self._calls = calls
        self._debtors = debtors
        self._phones = phones
        self._clock = clock

    def execute(self, direction: CallDirection, caller_phone: str,
                account_external_id: str | None = None) -> str:
        """Entrante: el deudor se asocia después, al verificar. Saliente: viene la cuenta del job."""
        debtor_id = account_id = None
        if direction is CallDirection.OUTBOUND:
            if account_external_id is None:
                raise ValueError("Una llamada saliente necesita la cuenta del job")
            debtor = self._debtors.get_by_account(account_external_id)
            if debtor is None:
                raise ValueError(f"Cuenta desconocida: {account_external_id}")
            debtor_id = debtor.id
            account_id = next(a.id for a in debtor.accounts if a.external_id == account_external_id)

        phone = self._phones.normalize(caller_phone) or caller_phone
        return self._calls.create(direction, phone, self._clock.now(), debtor_id, account_id)


class RecordRecordingConsent:
    def __init__(self, calls: CallRepository):
        self._calls = calls

    def execute(self, call_id: str, accepted: bool) -> bool:
        """Devuelve si la llamada puede continuar. Si es False, el agente debe cerrar con RECORDING_REFUSED."""
        call = self._calls.get(call_id)
        if call is None or not call.is_open:
            raise ValueError(f"Llamada desconocida o cerrada: {call_id}")
        self._calls.set_recording_consent(call_id, accepted)
        return accepted


class EndCall:
    def __init__(self, calls: CallRepository, summarizer: CallSummarizer, clock: Clock):
        self._calls = calls
        self._summarizer = summarizer
        self._clock = clock

    def execute(self, call_id: str, outcome: CallOutcome, transcript: str | None = None) -> str | None:
        """Cierra la llamada. Devuelve el resumen generado, o None si no hubo transcripción o falló."""
        call = self._calls.get(call_id)
        if call is None:
            raise ValueError(f"Llamada desconocida: {call_id}")
        check_can_close(call, outcome)

        summary = None
        if transcript and transcript.strip():
            try:
                summary = self._summarizer.summarize(transcript)
            except SummarizationError:
                # El resultado de la llamada nunca se pierde por un fallo del resumen.
                log.warning("No se pudo resumir la llamada %s", call_id, exc_info=True)

        self._calls.close(call_id, outcome, summary, self._clock.now())
        return summary
