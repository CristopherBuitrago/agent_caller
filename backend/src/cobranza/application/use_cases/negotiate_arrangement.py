"""Funciones 4 y 5: negociar el acuerdo de pago y registrar las Hardship Questions."""

from dataclasses import dataclass
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from cobranza.application.interfaces.arrangement_repository import ArrangementRepository
from cobranza.application.interfaces.call_repository import CallRepository
from cobranza.application.interfaces.clock import Clock
from cobranza.application.interfaces.hardship_repository import HardshipRepository
from cobranza.application.interfaces.negotiation_log import LoggedProposal, NegotiationLog
from cobranza.application.use_cases.lookup_debtor import GetDebtorByAccount
from cobranza.domain.arrangement import (
    DOWN_PAYMENT_OFFER,
    LAST_INSTALLMENTS_BEFORE_HARDSHIP,
    LAST_OFFER,
    MAX_INSTALLMENTS,
    STATUS_AFTER_ARRANGEMENT,
    ArrangementProposal,
    ArrangementRuleError,
    RuleViolation,
    build_down_payment_plan,
    build_full,
    build_partial,
    build_plan,
    is_last_resort_partial,
    requires_hardship,
    validate_proposal,
)
from cobranza.domain.debtor import AccountSummary, DebtorSummary
from cobranza.domain.hardship import HardshipAnswers


# B1 (2026-11-13): las Hardship Questions de un deudor valen 30 días, en cualquier llamada.
HARDSHIP_VALID_FOR = timedelta(days=30)


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
        """B1: valen las Hardship Questions que el deudor contestó en los últimos 30 días, en esta
        o en otra llamada, para no repetírselas."""
        debtor_id = self.verified_debtor_id(call_id)
        since = self._clock.now() - HARDSHIP_VALID_FOR
        if not self._hardships.exists_for_debtor_since(debtor_id, since):
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
    """La oferta que le toca al agente: 1 = todo de una, 2 = 2 cuotas, ..., 10 = 10 cuotas y
    11 = primer pago del 10% más 12 cuotas mensuales (N5).

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
        if offer_number > LAST_OFFER:
            return None
        balance = context.account.current_balance_cents
        first_due = first_due or context.today
        if offer_number == 1:
            return build_full(balance, first_due, context.today)
        if offer_number == DOWN_PAYMENT_OFFER:
            return build_down_payment_plan(balance, first_due, context.today)
        return build_plan(balance, offer_number, first_due, context.today)


# La oferta más baja antes de las Hardship Questions y la más baja de todas: nunca se saltan.
_LAST_OFFER_OF_STAGE = frozenset({LAST_INSTALLMENTS_BEFORE_HARDSHIP, LAST_OFFER})


class ProposeNextOffer:
    """La siguiente oferta que le toca al deudor: la más rápida que todavía no rechazó.

    El sistema elige el número de oferta y la guarda en el registro de la llamada, así la IA
    solo puede presentar lo que devuelve esta función.
    """

    def __init__(self, propose: ProposeArrangement, log: NegotiationLog):
        self._propose = propose
        self._log = log

    def execute(self, call_id: str, account_external_id: str, first_due: date | None = None,
                stated_max_payment_cents: int | None = None) -> LoggedProposal | None:
        """Devuelve None cuando el deudor ya rechazó todas las ofertas de cuotas.

        `stated_max_payment_cents` (N4, opción A'): lo máximo que el deudor dijo poder pagar por
        cuota. Las ofertas con una cuota mayor se saltan y quedan en el registro como rechazadas,
        con el motivo. Nunca se salta la última oferta de cada etapa (3 cuotas antes de las
        Hardship Questions y 10 después): decir un monto bajo no evita esas preguntas.
        """
        rejected = self._log.rejected_offer_numbers(call_id, account_external_id)
        for offer_number in (n for n in range(1, LAST_OFFER + 1) if n not in rejected):
            proposal = self._propose.execute(call_id, account_external_id, offer_number, first_due)
            if proposal is None:
                return None
            if (stated_max_payment_cents is not None and offer_number not in _LAST_OFFER_OF_STAGE
                    and proposal.payments[0].amount_cents > stated_max_payment_cents):
                self._log.save_skipped(call_id, account_external_id, offer_number, proposal,
                                       f"payment above the {stated_max_payment_cents} cents the debtor "
                                       "said they can pay")
                continue
            return self._log.save(call_id, account_external_id, offer_number, proposal)
        return None


class ProposePartialPayment:
    """Pago parcial con el monto que dijo el deudor.

    Desde 10% se acepta en cualquier momento. Menos del 10% es el último recurso: exige las
    Hardship Questions y que el deudor ya haya rechazado todas las ofertas de cuotas, según
    el registro de la llamada (no lo decide quien llama a esta función).
    """

    def __init__(self, gate: _ArrangementGate, log: NegotiationLog):
        self._gate = gate
        self._log = log

    def execute(self, call_id: str, account_external_id: str, amount_cents: int,
                first_due: date | None = None, remainder_due: date | None = None,
                stated_max_payment_cents: int | None = None) -> LoggedProposal:
        """`stated_max_payment_cents` (N6): lo que el deudor dijo poder pagar por cuota; si el resto
        no cabe en un pago, se reparte en cuotas mensuales. Más de 3 pagos exige las Hardship Questions."""
        context = self._gate.check(call_id, account_external_id)
        proposal = build_partial(
            context.account.current_balance_cents, amount_cents,
            first_due or context.today, context.today, remainder_due, stated_max_payment_cents,
        )
        if requires_hardship(proposal):
            self._gate.check_hardship_done(call_id)
        if is_last_resort_partial(proposal):
            rejected = self._log.rejected_offer_numbers(call_id, account_external_id)
            if not set(range(1, LAST_OFFER + 1)) <= rejected:
                raise ArrangementRuleError(RuleViolation.OFFERS_NOT_EXHAUSTED)
        return self._log.save(call_id, account_external_id, None, proposal)


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


class UnknownProposalError(ValueError):
    """El id no corresponde a una propuesta presentada en esta llamada."""


class RecordOfferResponse:
    """El deudor acepta o rechaza una propuesta presentada en la llamada.

    Aceptar crea el acuerdo con la propuesta guardada, nunca con montos que envíe la IA.
    """

    def __init__(self, log: NegotiationLog, create: CreateArrangement):
        self._log = log
        self._create = create

    def execute(self, call_id: str, proposal_id: str, accepted: bool) -> str | None:
        """Devuelve el id del acuerdo si se aceptó; None si se rechazó."""
        logged = self._log.get(call_id, proposal_id)
        if logged is None:
            raise UnknownProposalError(proposal_id)
        if logged.rejected:
            raise ValueError(f"La propuesta {proposal_id} ya fue rechazada")
        if not accepted:
            self._log.mark_rejected(call_id, proposal_id)
            return None
        return self._create.execute(call_id, logged.account_external_id, logged.proposal)
