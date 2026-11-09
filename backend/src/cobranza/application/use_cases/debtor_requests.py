"""Función 7: disputas y pedidos de "no llamar". Ambas marcan los datos y cierran la llamada."""

from cobranza.application.interfaces.call_repository import CallRepository
from cobranza.application.interfaces.debtor_repository import DebtorRepository
from cobranza.application.use_cases.register_call import EndCall
from cobranza.domain.arrangement import ArrangementRuleError, RuleViolation
from cobranza.domain.call import CallDirection, CallOutcome


class RecordDispute:
    """El deudor disputa la cuenta, por ejemplo "yo sí pagué" o "fue error del banco".

    No se le cobra más hasta que una persona lo revise; el agente lo transfiere al terminar.
    Solo una persona quita la marca.
    """

    def __init__(self, calls: CallRepository, debtors: DebtorRepository, end_call: EndCall):
        self._calls = calls
        self._debtors = debtors
        self._end_call = end_call

    def execute(self, call_id: str, account_external_id: str, transcript: str | None = None) -> str | None:
        """Devuelve el resumen de la llamada."""
        call = self._calls.get(call_id)
        if call is None or not call.is_open:
            raise ValueError(f"Llamada desconocida o cerrada: {call_id}")
        if call.recording_consent is not True:
            raise ArrangementRuleError(RuleViolation.RECORDING_CONSENT_MISSING)

        debtor = self._debtors.get_by_account(account_external_id)
        if debtor is None:
            raise ValueError(f"Cuenta desconocida: {account_external_id}")
        state = self._calls.get_verification_state(call_id)
        if state is None or not state.identity_verified or state.debtor_id != debtor.id:
            raise ArrangementRuleError(RuleViolation.IDENTITY_NOT_VERIFIED)

        account = next(a for a in debtor.accounts if a.external_id == account_external_id)
        self._debtors.mark_disputed(account.id)
        # Un deudor puede tener varias cuentas: la llamada deja constancia de cuál disputó.
        self._calls.link_account(call_id, account.id)
        return self._end_call.execute(call_id, CallOutcome.DISPUTE, transcript)


class MarkDoNotCall:
    """El deudor pide que no lo llamen más.

    En una saliente se llamó al deudor del job, así que se respeta aunque no se haya verificado.
    En una entrante exige verificación, para que nadie bloquee las llamadas de otra persona.
    """

    def __init__(self, calls: CallRepository, debtors: DebtorRepository, end_call: EndCall):
        self._calls = calls
        self._debtors = debtors
        self._end_call = end_call

    def execute(self, call_id: str, transcript: str | None = None) -> str | None:
        """Devuelve el resumen de la llamada."""
        call = self._calls.get(call_id)
        if call is None or not call.is_open:
            raise ValueError(f"Llamada desconocida o cerrada: {call_id}")

        state = self._calls.get_verification_state(call_id)
        verified = state is not None and state.identity_verified
        if call.debtor_id is None or (call.direction is CallDirection.INBOUND and not verified):
            raise ArrangementRuleError(RuleViolation.IDENTITY_NOT_VERIFIED)

        self._debtors.mark_do_not_call(call.debtor_id)
        # Sin consentimiento de grabación, el único cierre permitido es recording_refused.
        outcome = CallOutcome.RECORDING_REFUSED if call.recording_consent is False else CallOutcome.DO_NOT_CALL
        return self._end_call.execute(call_id, outcome, transcript)
