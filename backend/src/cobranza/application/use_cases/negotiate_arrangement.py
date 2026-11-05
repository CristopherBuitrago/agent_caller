"""Funciones 4 y 5: negociar el acuerdo de pago y registrar las Hardship Questions."""

from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo

from cobranza.application.interfaces.arrangement_repository import ArrangementRepository
from cobranza.application.interfaces.call_repository import CallRepository
from cobranza.application.interfaces.clock import Clock
from cobranza.application.interfaces.hardship_repository import HardshipRepository
from cobranza.application.use_cases.lookup_debtor import GetDebtorByAccount
from cobranza.domain.arrangement import (
    LAST_INSTALLMENTS_BEFORE_HARDSHIP,
    MAX_INSTALLMENTS,
    STATUS_AFTER_ARRANGEMENT,
    ArrangementProposal,
    ArrangementRuleError,
    RuleViolation,
    build_full,
    build_partial,
    build_plan,
    is_last_resort_partial,
    requires_hardship,
    validate_proposal,
)
from cobranza.domain.debtor import AccountSummary, DebtorSummary
from cobranza.domain.hardship import HardshipAnswers


@dataclass(frozen=True)
class _Context:
    account: AccountSummary
    today: date  # fecha local del deudor


class _ArrangementGate:
    """Condiciones comunes: llamada abierta y grabada, identidad verificada y cuenta cobrable."""

    def __init__(self, calls: CallRepository, arrangements: ArrangementRepository,
                 get_debtor: GetDebtorByAccount, clock: Clock, hardships: HardshipRepository):
        self._calls = calls
        self._arrangements = arrangements
        self._get_debtor = get_debtor
        self._clock = clock
        self._hardships = hardships

    def check_recorded_call(self, call_id: str) -> None:
        call = self._calls.get(call_id)
        if call is None or not call.is_open:
            raise ValueError(f"Llamada desconocida o cerrada: {call_id}")
        if call.recording_consent is not True:
            raise ArrangementRuleError(RuleViolation.RECORDING_CONSENT_MISSING)

    def verified_debtor_id(self, call_id: str) -> str:
        state = self._calls.get_verification_state(call_id)
        if state is None or not state.identity_verified or state.debtor_id is None:
            raise ArrangementRuleError(RuleViolation.IDENTITY_NOT_VERIFIED)
        return state.debtor_id

    def check_hardship_done(self, call_id: str) -> None:
        if not self._hardships.exists_for_call(call_id):
            raise ArrangementRuleError(RuleViolation.HARDSHIP_REQUIRED)

    def check(self, call_id: str, account_external_id: str) -> _Context:
        self.check_recorded_call(call_id)

        debtor = self._get_debtor.execute(account_external_id)
        if debtor is None:
            raise ValueError(f"Cuenta desconocida: {account_external_id}")
        # La identidad verificada debe ser la del dueño de esta cuenta.
        if self.verified_debtor_id(call_id) != debtor.id:
            raise ArrangementRuleError(RuleViolation.IDENTITY_NOT_VERIFIED)

        account = next(a for a in debtor.accounts if a.external_id == account_external_id)
        # Va primero: con un acuerdo activo la cuenta queda en PTP y tampoco sería cobrable.
        if self._arrangements.has_active_arrangement(account.id):
            raise ArrangementRuleError(RuleViolation.ACTIVE_ARRANGEMENT_EXISTS)
        if not debtor.can_collect(account):
            raise ArrangementRuleError(RuleViolation.ACCOUNT_NOT_COLLECTABLE)
        return _Context(account, self._local_today(debtor))

    def _local_today(self, debtor: DebtorSummary) -> date:
        now = self._clock.now()
        return now.astimezone(ZoneInfo(debtor.timezone)).date() if debtor.timezone else now.date()


class ProposeArrangement:
    """La oferta que le toca al agente: 1 = todo de una, 2 = 2 cuotas, 3 = 3 cuotas...

    Desde la oferta 4 exige que las Hardship Questions ya estén registradas en la llamada.
    """

    def __init__(self, gate: _ArrangementGate):
        self._gate = gate

    def execute(self, call_id: str, account_external_id: str, offer_number: int,
                first_due: date | None = None) -> ArrangementProposal | None:
        """Devuelve None cuando ya no quedan ofertas de cuotas."""
        if offer_number < 1:
            raise ValueError("offer_number empieza en 1")
        context = self._gate.check(call_id, account_external_id)
        if offer_number > LAST_INSTALLMENTS_BEFORE_HARDSHIP:
            self._gate.check_hardship_done(call_id)
        if offer_number > MAX_INSTALLMENTS:
            return None
        balance = context.account.current_balance_cents
        first_due = first_due or context.today
        if offer_number == 1:
            return build_full(balance, first_due, context.today)
        return build_plan(balance, offer_number, first_due, context.today)


class ProposePartialPayment:
    """Pago parcial con el monto que dijo el deudor.

    Desde 10% se acepta en cualquier momento. Menos del 10% es el último recurso: exige las
    Hardship Questions y que el deudor ya haya rechazado todas las ofertas de cuotas.
    """

    def __init__(self, gate: _ArrangementGate):
        self._gate = gate

    def execute(self, call_id: str, account_external_id: str, amount_cents: int,
                first_due: date | None = None, remainder_due: date | None = None,
                all_offers_rejected: bool = False) -> ArrangementProposal:
        context = self._gate.check(call_id, account_external_id)
        proposal = build_partial(
            context.account.current_balance_cents, amount_cents,
            first_due or context.today, context.today, remainder_due,
        )
        if is_last_resort_partial(proposal):
            self._gate.check_hardship_done(call_id)
            if not all_offers_rejected:
                raise ArrangementRuleError(RuleViolation.OFFERS_NOT_EXHAUSTED)
        return proposal


class RecordHardshipAssessment:
    """Guarda las respuestas; se puede repetir en la llamada para completarlas."""

    def __init__(self, gate: _ArrangementGate, hardships: HardshipRepository):
        self._gate = gate
        self._hardships = hardships

    def execute(self, call_id: str, answers: HardshipAnswers) -> None:
        self._gate.check_recorded_call(call_id)
        self._hardships.save(call_id, self._gate.verified_debtor_id(call_id), answers)


class CreateArrangement:
    """Guarda lo que el deudor aceptó. Revalida contra el saldo actual antes de guardar."""

    def __init__(self, gate: _ArrangementGate, arrangements: ArrangementRepository):
        self._gate = gate
        self._arrangements = arrangements

    def execute(self, call_id: str, account_external_id: str, proposal: ArrangementProposal) -> str:
        context = self._gate.check(call_id, account_external_id)
        validate_proposal(proposal, context.account.current_balance_cents, context.today)
        if requires_hardship(proposal):
            self._gate.check_hardship_done(call_id)
        return self._arrangements.create(call_id, context.account.id, proposal, STATUS_AFTER_ARRANGEMENT)
