"""Las herramientas del agente de voz: lo que el modelo puede pedir durante una llamada.

Viven en el núcleo y se publican por HTTP (cobranza.infrastructure.api), así las usa nuestro
agente (carpeta agente/) o cualquier plataforma de voz externa. Cada herramienta llama a un caso de uso. El modelo solo conversa: los montos, las fechas, el
orden de las ofertas y lo que se guarda los deciden los casos de uso. Cada respuesta incluye
`next_step`, una instrucción corta de qué hacer después, para que el modelo no improvise.
"""

import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo
from typing import Any

from cobranza.application.interfaces.clock import Clock
from cobranza.application.interfaces.negotiation_log import LoggedProposal
from cobranza.application.use_cases.contact_history import GetLastContact
from cobranza.application.use_cases.debtor_requests import MarkDoNotCall, RecordCollectionHold, RecordDispute
from cobranza.application.use_cases.lookup_debtor import (
    FindDebtorsByName,
    FindDebtorsByPhone,
    GetDebtorByAccount,
    GetDebtorById,
)
from cobranza.application.use_cases.negotiate_arrangement import (
    ProposeNextOffer,
    ProposePartialPayment,
    RecordHardshipAssessment,
    RecordOfferResponse,
    UnknownProposalError,
)
from cobranza.application.use_cases.register_call import EndCall, RecordRecordingConsent, ScheduleCallback
from cobranza.application.use_cases.verify_identity import VerifyIdentity
from cobranza.domain.arrangement import (
    LAST_INSTALLMENTS_BEFORE_HARDSHIP,
    end_of_month,
    first_payment_month_end,
    latest_first_payment_date,
    LAST_OFFER,
    REGULAR_MIN_PARTIAL_PAYMENT_PCT,
    ArrangementRuleError,
    ArrangementType,
    is_down_payment_plan,
    RuleViolation,
)
from cobranza.domain.call import CallbackTimeError, CallDirection, CallOutcome
from cobranza.domain.debtor import AccountSummary, CollectionHold, DebtorSummary
from cobranza.domain.hardship import (
    HARDSHIP_QUESTION_COUNT,
    HARDSHIP_QUESTIONS,
    HardshipAnswerError,
    HardshipAnswers,
    HardshipDuration,
)
from cobranza.domain.identity import VerificationOutcome, names_match

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


# Aviso de cobranza (FDCPA). Se dice tal cual, justo después de verificar la identidad.
DISCLOSURE = ("This is an attempt to collect a debt, and any information obtained will be used "
              "for that purpose. This communication is from a debt collector.")


@dataclass(frozen=True)
class AgentUseCases:
    """Los casos de uso que necesitan las herramientas. Los arma infrastructure/api/app.py."""
    find_debtors_by_phone: FindDebtorsByPhone
    get_debtor_by_account: GetDebtorByAccount
    record_recording_consent: RecordRecordingConsent
    verify_identity: VerifyIdentity
    end_call: EndCall
    propose_next_offer: ProposeNextOffer
    propose_partial_payment: ProposePartialPayment
    record_offer_response: RecordOfferResponse
    record_hardship_assessment: RecordHardshipAssessment
    record_dispute: RecordDispute
    mark_do_not_call: MarkDoNotCall
    record_collection_hold: RecordCollectionHold
    get_last_contact: GetLastContact
    schedule_callback: ScheduleCallback
    # Solo demos en el navegador (sin teléfono): buscar al deudor de una entrante por el nombre dicho.
    find_debtors_by_name: FindDebtorsByName | None = None
    # Solo demos: el deudor encontrado por SSN y fecha, sin teléfono.
    get_debtor_by_id: GetDebtorById | None = None


# --- definición de las herramientas (lo que ve el modelo) ---------------------------------

# Las ofertas más bajas de cada etapa: 3 cuotas antes de las Hardship Questions y, después, el pago
# inicial más 12 cuotas (N4 y N5).
# N9: zona horaria si no se conoce la del deudor (confirmado por el desarrollador, 2026-11-13).
_DEFAULT_ZONE = ZoneInfo("America/New_York")

_LOWEST_OFFER_OF_STAGE = frozenset({LAST_INSTALLMENTS_BEFORE_HARDSHIP, LAST_OFFER})

# B6 y duda 7 (jefe, 2026-11-17): la empresa solo maneja el código NSF (Not Sufficient Funds) y es la
# razón real del rebote: el agente la dice como un hecho. Con cualquier otro valor no se da motivo, y
# nunca se dice el código.
_NSF_RETURN_CODE = "NSF"


def _return_reason(account: AccountSummary) -> str | None:
    if (account.nsf_return_code or "").strip().upper() != _NSF_RETURN_CODE:
        return None
    where = "on your card" if (account.payment_method or "").strip().upper() == "CARD" else "in your account"
    return f"there were not enough funds {where}"

_DATE = {"type": "string", "description": "Date as YYYY-MM-DD."}
_ACCOUNT_REF = {"type": "string", "description": "account_ref returned by get_account_details."}


def _spec(name: str, description: str, properties: dict | None = None,
          required: tuple[str, ...] = ()) -> ToolSpec:
    return ToolSpec(name, description, {
        "type": "object", "properties": properties or {}, "required": list(required),
        "additionalProperties": False,
    })


END_OUTCOMES = {
    CallOutcome.ARRANGEMENT_MADE, CallOutcome.WRONG_PARTY, CallOutcome.CALLBACK_REQUESTED,
    CallOutcome.VERIFICATION_FAILED, CallOutcome.RECORDING_REFUSED, CallOutcome.DEBTOR_UNAVAILABLE,
}

TOOL_SPECS: tuple[ToolSpec, ...] = (
    _spec("record_recording_consent",
          "Call with accepted true right after saying the recording notice (do not wait for an answer). "
          "Call with accepted false only if the caller still refuses to be recorded after you explain "
          "that it is required.",
          {"accepted": {"type": "boolean"}}, ("accepted",)),
    _spec("verify_identity",
          "Verify the caller with the last 4 digits of the SSN and the date of birth. Call it once you "
          "have both. Add full_name only if the caller gave their name (for example, after saying "
          "no to the name confirmation).",
          {"ssn_last4": {"type": "string", "description": "Exactly 4 digits."},
           "date_of_birth": _DATE,
           "full_name": {"type": "string", "description": "Optional. Only if the caller said it."},
           "name_was_spelled": {"type": "boolean",
                                "description": "True if the caller already spelled the last name."}},
          ("ssn_last4", "date_of_birth")),
    _spec("confirm_identity",
          "After verify_identity returns confirm_name and you asked \"Am I speaking with [name]?\": "
          "confirmed true if they clearly said yes, false if they said no.",
          {"confirmed": {"type": "boolean"}}, ("confirmed",)),
    _spec("get_account_details",
          "Get the verified debtor's accounts: creditor, balance and the returned payment."),
    _spec("propose_offer",
          "Get the next payment option the system allows. Present exactly what it returns.",
          {"account_ref": _ACCOUNT_REF,
           "first_payment_date": {**_DATE, "description": "Optional date the debtor wants for "
                                  "the first payment. Omit it to use today."},
           "max_payment_dollars": {"type": "number", "description": "Optional. The most the debtor "
                                   "said they can pay per payment. Options above it are skipped, "
                                   "but the system always keeps its lowest options."}},
          ("account_ref",)),
    _spec("record_offer_response",
          "Record whether the debtor accepted or declined a proposal. Accepting creates the "
          "agreement: use accepted true only after a clear yes, without doubts or conditions.",
          {"proposal_id": {"type": "string"}, "accepted": {"type": "boolean"}},
          ("proposal_id", "accepted")),
    _spec("propose_partial_payment",
          "Build a partial payment with the amount the debtor said they can pay now.",
          {"account_ref": _ACCOUNT_REF,
           "amount_dollars": {"type": "number"},
           "first_payment_date": {**_DATE, "description": "Optional. Omit it to use today."},
           "remainder_date": {**_DATE, "description": "Optional. Omit it to use 30 days later."},
           "max_payment_dollars": {"type": "number", "description": "Optional. The most the debtor "
                                   "said they can pay per month. If the rest does not fit in one "
                                   "payment, the system splits it into monthly payments."}},
          ("account_ref", "amount_dollars")),
    _spec("record_hardship_answers",
          "Save the debtor's answer to one hardship question, right after they answer it. Question 1: "
          "situation_description (and situation_started). Question 2: duration_type (leave it empty if "
          "unclear). Question 3: household_support. Question 4: offered_amount_dollars (empty if they "
          "offer nothing). Question 5: arrangement_answer. The result tells you the next question.",
          {"question_number": {"type": "integer", "minimum": 1, "maximum": HARDSHIP_QUESTION_COUNT},
           "situation_description": {"type": "string"},
           "situation_started": {"type": "string", "description": "In the debtor's words."},
           "duration_type": {"type": "string", "enum": [d.value for d in HardshipDuration]},
           "household_support": {"type": "boolean"},
           "offered_amount_dollars": {"type": "number"},
           "arrangement_answer": {"type": "string", "description": "Answer to question 5, in the "
                                  "debtor's words."},
           "notes": {"type": "string"}},
          ("question_number",)),
    _spec("record_dispute",
          "The debtor says they already paid, the bank made a mistake, or the debt is not "
          "theirs. Marks the account as disputed and ends the call.",
          {"account_ref": _ACCOUNT_REF}, ("account_ref",)),
    _spec("mark_do_not_call",
          "The debtor explicitly asked not to be called again. Saves it and ends the call."),
    _spec("record_collection_hold",
          "The law requires stopping collection: the debtor says an attorney is handling this debt, says "
          "they filed for bankruptcy, or someone says the debtor has died. Records it, stops all collection "
          "for the debtor and ends the call.",
          {"reason": {"type": "string", "enum": [h.value for h in CollectionHold]},
           "details": {"type": "string", "description": "Attorney name and phone, bankruptcy case number, "
                       "or who reported the death and their relationship to the debtor."}},
          ("reason",)),
    _spec("get_last_contact",
          "When the verified debtor complains about being called too often, get the date and time "
          "of our last call from the system. Never guess it."),
    _spec("schedule_callback",
          "The person asked to be called back on a specific day and time (or a third party said "
          "when the debtor will be available). Saves it and ends the call.",
          {"date": _DATE,
           "time": {"type": "string", "description": "Time as HH:MM, 24-hour, in the debtor's local time."},
           "note": {"type": "string", "description": "Optional short note, for example who asked."}},
          ("date", "time")),
    _spec("transfer_to_human",
          "Transfer the call to a representative. Ends your part of the call.",
          {"reason": {"type": "string"}}, ("reason",)),
    _spec("end_call",
          "End the call with its outcome. wrong_party and debtor_unavailable are only for outbound "
          "calls where someone other than the debtor answered.",
          {"outcome": {"type": "string", "enum": sorted(o.value for o in END_OUTCOMES)}},
          ("outcome",)),
)

# Qué hacer cuando un caso de uso rechaza la acción por una regla.
_NEXT_STEP_BY_RULE = {
    RuleViolation.RECORDING_CONSENT_MISSING:
        "The caller has not accepted the recording. Do not discuss any account.",
    RuleViolation.IDENTITY_NOT_VERIFIED:
        "Identity is not verified. Verify it with verify_identity before discussing the debt.",
    RuleViolation.ACCOUNT_NOT_COLLECTABLE:
        "You cannot handle this account. Transfer with transfer_to_human.",
    RuleViolation.ACTIVE_ARRANGEMENT_EXISTS:
        "This account already has a payment arrangement. Tell the debtor and offer to transfer "
        "to a representative if they need changes.",
    RuleViolation.HARDSHIP_REQUIRED:
        "Before more options, ask the hardship questions one at a time, save the answers with "
        "record_hardship_answers, then call propose_offer again.",
    RuleViolation.OFFERS_NOT_EXHAUSTED:
        "Amounts this low are only possible after every installment option was declined. "
        "Continue with propose_offer.",
    RuleViolation.AMOUNT_BELOW_FLOOR:
        "The amount is below the minimum. Tell the debtor the minimum and ask if they can "
        "reach it.",
    RuleViolation.AMOUNT_NOT_PARTIAL:
        "That amount covers the full balance. Use propose_offer instead.",
    RuleViolation.FIRST_PAYMENT_DATE_OUT_OF_RANGE:
        "That date is not available. Follow first_payment_date_rule and ask for a date in that range.",
    RuleViolation.REMAINDER_DATE_OUT_OF_RANGE:
        "The rest must be paid within 30 days of the first payment. Ask for an earlier date.",
}


# --- formato de montos y fechas para decirlos en voz alta ----------------------------------

def dollars(cents: int) -> str:
    return f"${cents // 100:,}.{cents % 100:02d}"


def _spoken_date(value: date) -> str:
    return f"{value:%A}, {value:%B} {value.day}, {value.year}"


def _spoken_time(value: datetime) -> str:
    """15:05 -> "3:05 PM"."""
    hour = value.hour % 12 or 12
    return f"{hour}:{value.minute:02d} {'AM' if value.hour < 12 else 'PM'}"


def _parse_date(value: str | None, field: str) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise _ToolInputError(f"{field} must be a date as YYYY-MM-DD") from None


class _ToolInputError(ValueError):
    """El modelo mandó un dato mal formado; se le pide repetirlo."""


# Hallazgo 5 de las simulaciones con Haiku (2026-11-18): el agente no sabía cómo se paga y transfería.
# Describe lo que hace el sistema: SMS de confirmación y link de pago (N1) y aviso 3 días antes (N10,
# REMINDER_DAYS_BEFORE de la mensajería). El pago con tarjeta por teléfono (Función 6) todavía no
# existe. Antes del piloto, Vaspian (SMS) y el procesador (link) tienen que estar conectados.
HOW_PAYMENTS_WORK = (
    "After the plan is set up, you'll get a text message confirming the amounts and dates. For each "
    "payment that is at least three days away, you'll get a reminder text three days before, and on each "
    "payment date a text with a secure link to pay online. Nobody will call you to take the payment over "
    "the phone.")  # hallazgo 6: con un pago mañana, el aviso de 3 días antes no llega


def _in_collection_order(accounts) -> list[AccountSummary]:
    """Primero el pago rebotado más antiguo (supuesto del 2026-11-20); las cuentas sin fecha, al final."""
    return sorted(accounts, key=lambda a: (a.nsf_date is None, a.nsf_date or date.max))


def _describe(logged: LoggedProposal) -> dict[str, Any]:
    proposal = logged.proposal
    if proposal.type is ArrangementType.FULL:
        option = "pay the full balance"
    elif is_down_payment_plan(proposal):
        option = (f"a first payment now and then {len(proposal.payments) - 1} equal monthly "
                  "payments")
    elif proposal.type is ArrangementType.PLAN:
        option = f"{len(proposal.payments)} equal monthly payments"
    elif len(proposal.payments) > 2:
        option = (f"a partial payment now and the rest in {len(proposal.payments) - 1} equal "
                  "monthly payments")
    else:
        option = "a partial payment now and the rest later"
    return {
        "proposal_id": logged.id,
        "option": option,
        "total": dollars(proposal.total_amount_cents),
        "payments": [
            {"number": p.sequence, "amount": dollars(p.amount_cents),
             "date": p.due_date.isoformat(), "date_spoken": _spoken_date(p.due_date)}
            for p in proposal.payments
        ],
        "how_payments_work": HOW_PAYMENTS_WORK,
    }


# --- ejecución ----------------------------------------------------------------------------

class CallTools:
    """Ejecuta las herramientas de una llamada y guarda lo que pasó en ella."""

    def __init__(self, uc: AgentUseCases, call_id: str, direction: CallDirection,
                 caller_phone: str, outbound_account: str | None,
                 transcript: Callable[[], str], clock: Clock | None = None,
                 callback_number: str | None = None, lookup_by_name: bool = False):
        self._uc = uc
        self._lookup_by_name = lookup_by_name   # demo: entrante sin teléfono conocido
        self._clock = clock
        self._callback_number = callback_number  # N12: línea de entrada que atiende el agente
        self.call_id = call_id
        self._direction = direction
        self._caller_phone = caller_phone
        self._outbound_account = outbound_account
        self._transcript = transcript
        self._debtor: DebtorSummary | None = None  # deudor verificado
        self._names_given: list[str] = []  # nombres que dio quien llama en cada intento de verificación
        self._refusal_explained = False    # se le explicó que la grabación es obligatoria
        # SSN y fecha coincidieron con este deudor; falta que quien llama confirme el nombre.
        self._pending_identity: tuple[DebtorSummary, str, date] | None = None
        self._proposals: dict[str, LoggedProposal] = {}
        self._arrangement_made = False
        self._arranged_accounts: set[str] = set()   # cuentas con acuerdo en esta llamada
        self._recording_refused = False
        self._recording_notice_given = False  # en salientes, se da cuando la persona confirma ser el deudor
        self._third_party_rechecked = False   # hallazgo 4: ya se le pidió confirmar quién contestó
        self.ended = False
        self.outcome: CallOutcome | None = None
        self.summary: str | None = None
        self.transferred = False  # B3: se pasó a una persona (además del resultado)
        # B9: el deudor colgó; ninguna herramienta debe pedirle al agente que hable.
        self.caller_hung_up = False

    def execute(self, call: ToolCall) -> ToolResult:
        handler = getattr(self, f"_tool_{call.name}", None)
        if handler is None:
            return self._result(call, {"error": "unknown_tool"}, error=True)
        if self.ended:
            return self._result(call, {"error": "call_ended",
                                       "next_step": "The call is over. Only say goodbye."}, error=True)
        try:
            inspect.signature(handler).bind(**call.input)
        except TypeError:
            return self._result(call, {"error": "invalid_input",
                                       "next_step": "Check the tool's fields and call it again."}, error=True)
        try:
            return self._result(call, handler(**call.input))
        except ArrangementRuleError as e:
            return self._result(call, self._rule_error(e.violation, call.input), error=True)
        except (_ToolInputError, UnknownProposalError) as e:
            return self._result(call, {"error": "invalid_input", "detail": str(e)}, error=True)
        except ValueError as e:
            return self._result(call, {"error": "not_allowed", "detail": str(e),
                                       "next_step": "If you cannot continue, use transfer_to_human."},
                                error=True)

    def close_without_model(self, outcome: CallOutcome, transfer_reason: str | None = None) -> None:
        """Cierra la llamada sin el modelo (falló o el deudor colgó). Sin grabación, solo recording_refused."""
        if not self.ended:
            if self._recording_refused:
                self._close(CallOutcome.RECORDING_REFUSED)
            else:
                self._close(outcome, transfer_reason)

    # --- herramientas ---

    def _tool_record_recording_consent(self, accepted: bool) -> dict:
        if not accepted and not self._refusal_explained:
            # Prueba de voz (2026-11-22): el modelo cerró como recording_refused a un deudor que solo
            # estaba molesto. La negativa se guarda solo si la repite después de la explicación.
            self._refusal_explained = True
            return {"recorded": False, "next_step": "Only if the caller clearly said they do not want "
                    "to be recorded, say: \"I understand. Recording is a requirement for every call, to "
                    "protect both you and us. May we continue?\" If they still refuse, call "
                    "record_recording_consent with accepted false again. If they did not talk about the "
                    "recording, ignore this and continue the call normally."}
        self._uc.record_recording_consent.execute(self.call_id, accepted)
        if not accepted:
            self._recording_refused = True
            return {"recorded": True, "next_step": "Do not mention any account. Say goodbye politely "
                    "and call end_call with outcome recording_refused."}
        self._recording_notice_given = True
        return {"recorded": True, "next_step": "Verify identity before discussing anything else."}

    def _tool_verify_identity(self, ssn_last4: str, date_of_birth: str, full_name: str | None = None,
                              name_was_spelled: bool = False) -> dict:
        dob = _parse_date(date_of_birth, "date_of_birth")
        if dob is None:
            raise _ToolInputError("date_of_birth is required")
        if not (full_name or "").strip():
            # Flujo del 2026-11-22: con SSN y fecha se busca al deudor y se confirma el nombre.
            return self._verify_by_data(str(ssn_last4).strip(), dob)
        return self._verify(full_name, str(ssn_last4).strip(), dob, name_was_spelled)

    def _verify_by_data(self, ssn: str, dob: date) -> dict:
        candidates = self._identity_candidates(ssn, dob)
        match = next((d for d in candidates if self._uc.verify_identity.identity_matches(d.id, ssn, dob)), None)
        if match is not None:
            if self._direction is CallDirection.OUTBOUND:
                # En salientes el deudor ya confirmó su nombre al saludar.
                return self._verify(f"{match.first_name} {match.last_name}", ssn, dob)
            self._pending_identity = (match, ssn, dob)
            name = f"{match.first_name} {match.last_name}"
            return {"outcome": "confirm_name", "debtor_name": name,
                    "next_step": f'Say exactly: "Thank you. Am I speaking with {name}?" and wait for the '
                                 "answer. Then call confirm_identity with confirmed true or false."}
        if not candidates:
            return {"outcome": "not_found", "next_step": "Say the information did not match our "
                    "records and ask again for the last four digits of the Social Security number and "
                    "the date of birth, then call verify_identity again. If it still does not match, "
                    "offer to transfer to a representative with transfer_to_human."}
        # No coincide: es un intento fallido normal contra el deudor del teléfono o de la cuenta.
        debtor = candidates[0]
        return self._verify(f"{debtor.first_name} {debtor.last_name}", ssn, dob)

    def _identity_candidates(self, ssn: str, dob: date) -> list[DebtorSummary]:
        if self._direction is CallDirection.OUTBOUND:
            debtor = self._uc.get_debtor_by_account.execute(self._outbound_account)
            return [debtor] if debtor else []
        candidates = self._uc.find_debtors_by_phone.execute(self._caller_phone)
        if not candidates and self._lookup_by_name and self._uc.get_debtor_by_id is not None:
            ids = self._uc.verify_identity.debtor_ids_with_identity(ssn, dob)
            candidates = [d for d in (self._uc.get_debtor_by_id.execute(i) for i in ids) if d]
        return candidates

    def _tool_confirm_identity(self, confirmed: bool) -> dict:
        if self._pending_identity is None:
            raise _ToolInputError("Call verify_identity first")
        debtor, ssn, dob = self._pending_identity
        self._pending_identity = None
        if not confirmed:
            return {"confirmed": False, "next_step": "Ask for their full name, then call "
                    "verify_identity with full_name, ssn_last4 and date_of_birth."}
        return self._verify(f"{debtor.first_name} {debtor.last_name}", ssn, dob)

    def _verify(self, full_name: str, ssn_last4: str, dob: date, name_was_spelled: bool = False) -> dict:
        debtor = self._debtor_to_verify(full_name)
        if debtor is None:
            return {"outcome": "not_found", "next_step": "No account matches this phone number. "
                    "Offer to transfer to a representative with transfer_to_human."}
        outcome = self._uc.verify_identity.execute(
            self.call_id, debtor.id, full_name, str(ssn_last4).strip(), dob, name_was_spelled,
            tuple(self._names_given))
        if outcome is not VerificationOutcome.INVALID_INPUT:
            # Un nombre inventado por el modelo no cuenta para detectar cambios de nombre (S1).
            self._names_given.append(full_name)
        if outcome is VerificationOutcome.VERIFIED:
            self._debtor = debtor
        elif outcome is VerificationOutcome.IDENTITY_MISMATCH:
            self._close(CallOutcome.IDENTITY_MISMATCH)
        next_step = _VERIFICATION_NEXT_STEP[outcome]
        result: dict[str, Any] = {"outcome": outcome.value}
        if outcome is VerificationOutcome.FAILED:
            # B8: el agente sabe cuántos intentos quedan; si es el último, se lo dice al deudor.
            left = self._uc.verify_identity.attempts_left(self.call_id, debtor.id)
            result["attempts_left"] = left
            if left == 1:
                mismatched = self._uc.verify_identity.mismatched_items(
                    debtor.id, full_name, str(ssn_last4).strip(), dob)
                result["mismatched"] = mismatched
                next_step = _last_attempt_next_step(mismatched, str(ssn_last4).strip())
        if outcome in _OFFER_CALLBACK_NUMBER and self._callback_number:
            # N12: quien no logra verificarse recibe el número de la línea que atiende el agente.
            next_step += (f' Before saying goodbye, say: "If you\'d like, you can call us back at '
                          f'{spoken_phone(self._callback_number)} whenever you have your information handy."')
        result["next_step"] = next_step
        return result

    def _tool_get_account_details(self) -> dict:
        debtor = self._require_debtor()
        ordered = _in_collection_order(debtor.collectable_accounts)
        collectable = [self._account_view(a) for a in ordered]
        others = len(debtor.accounts) - len(collectable)
        result: dict[str, Any] = {"debtor_first_name": debtor.first_name, "accounts": collectable}
        if collectable:
            result["how_payments_work"] = HOW_PAYMENTS_WORK   # hallazgo 5: por si pregunta antes de una oferta
        if others:
            result["other_accounts"] = (f"{others} other account(s) must be handled by a "
                                        "representative. Do not give their details.")
        if len(ordered) > 1:
            # Varias deudas (decisión del padrastro, 2026-11-20): se anuncia el orden antes de empezar.
            first, rest = ordered[0], ordered[1:]
            then = " and ".join(a.creditor_name for a in rest)
            result["next_step"] = (
                "Explain calmly that payments were returned by the bank and why, using each "
                "returned_payment reason as a fact (do not soften it or suggest it may be wrong), and "
                "give each creditor and balance. Then say you will start with the "
                f"{first.creditor_name} balance and then look at {then}, and end your turn with: "
                f"\"Would you like to take care of the {first.creditor_name} balance today?\" Call "
                f"propose_offer with account_ref {first.external_id} only after they answer, so the "
                "offer goes in your next turn. If the debtor already said how much they can pay, call "
                "propose_offer now with max_payment_dollars. If there is no reason and they ask why a "
                "payment was returned, say a representative can give them the details.")
            return result
        result["next_step"] = (
            "Explain calmly that a recent payment was returned by the bank and why, using the "
            "returned_payment reason as a fact (do not soften it or suggest it may be wrong), give "
            "the creditor and the balance, and end your turn with: \"Would you like to take care of "
            "it today?\" Call propose_offer only after they answer, so the offer goes in your next "
            "turn. If the debtor already said how much they can pay, call propose_offer now with "
            "max_payment_dollars. If there is no reason and they ask why it was returned, say a "
            "representative can give them the details." if collectable else
            "You cannot handle these accounts. Transfer with transfer_to_human.")
        return result

    def _tool_propose_offer(self, account_ref: str, first_payment_date: str | None = None,
                            max_payment_dollars: float | None = None) -> dict:
        self._require_own_account(account_ref)
        max_cents = round(float(max_payment_dollars) * 100) if max_payment_dollars is not None else None
        logged = self._uc.propose_next_offer.execute(
            self.call_id, account_ref, _parse_date(first_payment_date, "first_payment_date"), max_cents)
        if logged is None:
            # N5 y N6 (b): sin más planes, el agente prueba el parcial de último recurso; si tampoco,
            # lo atiende una persona. Así los cobradores se dedican a los estados que les tocan.
            return {"offers_exhausted": True, "next_step": "There are no more installment options. "
                    "Ask how much they could pay now and how much per month after that, and call "
                    "propose_partial_payment with both amounts. If they cannot pay anything, tell "
                    "them a representative will help them and call transfer_to_human."}
        self._proposals[logged.id] = logged
        window = self._first_payment_window()
        if logged.offer_number in _LOWEST_OFFER_OF_STAGE:
            # Es cierto decir que es la opción más baja disponible ahora; nunca se inventa una regla.
            return {**_describe(logged), **window, "lowest_option_available_now": True, "next_step":
                    "Present this as the lowest option you have available right now. Do not mention "
                    "any minimum percentage or rule. If the debtor accepts, call record_offer_response "
                    "with accepted true; if they say it is not possible, call it with accepted false "
                    "and then call propose_offer again."}
        return {**_describe(logged), **window, "next_step": "Present this option as the fastest way "
                "to resolve it. If the debtor accepts, call record_offer_response with accepted true; "
                "if they say it is not possible, call it with accepted false."}

    def _first_payment_window(self) -> dict[str, str]:
        """N8: hasta cuándo puede ir el primer pago, en la fecha local del deudor. Siempre se intenta hoy."""
        if self._clock is None or self._debtor is None:
            return {}
        now = self._clock.now()
        today = (now.astimezone(ZoneInfo(self._debtor.timezone)).date()
                 if self._debtor.timezone else now.date())
        latest = latest_first_payment_date(today)
        month_end = first_payment_month_end(today)
        this_month_end = end_of_month(today)
        # N8 (2026-11-13): si pide tiempo, el primer pago va el último día del mes y las cuotas
        # siguientes también caen el último día de cada mes. Desde el 2026-11-24 puede ir hasta 2 días
        # después, solo si el deudor no puede antes.
        if month_end == this_month_end:
            note = (f"Try to get the first payment today. If they need time, offer the last day of the "
                    f"month, {_spoken_date(month_end)}, and call propose_offer again with that "
                    "first_payment_date; any later payments will also fall on the last day of each month.")
        else:
            note = (f"Try to get the first payment today. If they need time, first offer "
                    f"{_spoken_date(this_month_end)}; only if they cannot, offer {_spoken_date(month_end)}. "
                    "Call propose_offer again with that first_payment_date; any later payments will also "
                    "fall on the last day of each month.")
        note += (f" Only if they cannot pay by then, the latest possible date is {_spoken_date(latest)}; "
                 "later payments then fall on that same day of each month.")
        return {"latest_first_payment_date": latest.isoformat(), "first_payment_date_rule": note}

    def _tool_record_offer_response(self, proposal_id: str, accepted: bool) -> dict:
        arrangement_id = self._uc.record_offer_response.execute(self.call_id, proposal_id, accepted)
        if not accepted:
            return {"recorded": True, "next_step": _DECLINED_NEXT_STEP}
        self._arrangement_made = True
        logged = self._proposals.get(proposal_id)
        if logged:
            self._arranged_accounts.add(logged.account_external_id)
        result = {"arrangement_id": arrangement_id,
                  **({"payments": _describe(logged)["payments"]} if logged else {})}
        next_step = ("Repeat the amounts and dates, thank the debtor, and tell them in your own "
                     f'words: "{HOW_PAYMENTS_WORK}"')
        pending = self._accounts_without_arrangement()
        if pending:
            # Prueba por celular (2026-11-19): con dos deudas, el agente cerraba la primera y colgaba.
            other = pending[0]
            result["other_accounts"] = [self._account_view(a) for a in pending]
            next_step += (f" Then tell them they also have the {other.creditor_name} balance of "
                          f"{dollars(other.current_balance_cents)} and ask if they would like to take care "
                          f"of it too. If yes, call propose_offer with account_ref {other.external_id}. "
                          "If not, call end_call with outcome arrangement_made. If the answer is not a "
                          "clear yes or no (for example, \"we're done, right?\"), ask: \"Should we "
                          f"leave the {other.creditor_name} balance for another time?\"")
        else:
            next_step += " Then call end_call with outcome arrangement_made."
        return {**result, "next_step": next_step}

    def _accounts_without_arrangement(self) -> list[AccountSummary]:
        """Las otras cuentas que el agente puede cobrar y que todavía no tienen acuerdo en esta llamada."""
        if self._debtor is None:
            return []
        return [a for a in _in_collection_order(self._debtor.collectable_accounts)
                if a.external_id not in self._arranged_accounts]

    def _tool_propose_partial_payment(self, account_ref: str, amount_dollars: float,
                                      first_payment_date: str | None = None,
                                      remainder_date: str | None = None,
                                      max_payment_dollars: float | None = None) -> dict:
        self._require_own_account(account_ref)
        max_cents = round(float(max_payment_dollars) * 100) if max_payment_dollars is not None else None
        logged = self._uc.propose_partial_payment.execute(
            self.call_id, account_ref, round(float(amount_dollars) * 100),
            _parse_date(first_payment_date, "first_payment_date"),
            _parse_date(remainder_date, "remainder_date"), max_cents)
        self._proposals[logged.id] = logged
        return {**_describe(logged), "next_step": "Present this plan, making clear the rest is still "
                "owed on the dates shown. Then call record_offer_response."}

    def _tool_record_hardship_answers(self, question_number: int,
                                      situation_description: str | None = None,
                                      situation_started: str | None = None,
                                      duration_type: str | None = None,
                                      household_support: bool | None = None,
                                      offered_amount_dollars: float | None = None,
                                      arrangement_answer: str | None = None,
                                      notes: str | None = None) -> dict:
        try:
            duration = HardshipDuration(duration_type) if duration_type else None
        except ValueError:
            raise _ToolInputError("duration_type must be temporary or long_term") from None
        offered = round(float(offered_amount_dollars) * 100) if offered_amount_dollars is not None else None
        answers = HardshipAnswers(
            situation_description=situation_description, situation_started=situation_started,
            duration_type=duration, household_support=household_support,
            offered_amount_cents=offered, notes=notes, arrangement_answer=arrangement_answer)
        try:
            answered = self._uc.record_hardship_assessment.execute(self.call_id, int(question_number), answers)
        except HardshipAnswerError as e:
            answered = self._uc.record_hardship_assessment.questions_answered(self.call_id)
            return {"error": "hardship_answer_not_saved", "detail": str(e),
                    "next_step": _next_hardship_question(answered)}
        if answered >= HARDSHIP_QUESTION_COUNT:
            return {"saved": True, "questions_answered": answered,
                    "next_step": "Thank them for sharing, then call propose_offer."}
        return {"saved": True, "questions_answered": answered, "next_step": _next_hardship_question(answered)}

    def _tool_record_dispute(self, account_ref: str) -> dict:
        self._require_own_account(account_ref)
        self.summary = self._uc.record_dispute.execute(self.call_id, account_ref, self._transcript())
        self._mark_ended(CallOutcome.DISPUTE)
        return {"recorded": True, "next_step": "Tell them a representative will review it, thank them "
                f"and say goodbye. Do not ask for any payment. {ALREADY_CLOSED}"}

    def _tool_get_last_contact(self) -> dict:
        """N13: la fecha real de la última llamada, en la hora local del deudor."""
        debtor = self._require_debtor()
        contact = self._uc.get_last_contact.execute(debtor.id, self.call_id)
        if contact is None:
            return {"last_call": None, "next_step": "Say you don't see a previous call from us in "
                    "your records, apologize for the inconvenience and continue. Only mark do not "
                    "call if they explicitly ask for it."}
        when = (contact.started_at.astimezone(ZoneInfo(debtor.timezone)) if debtor.timezone
                else contact.started_at)
        spoken = f"{_spoken_date(when.date())} at {_spoken_time(when)}"
        reason = (", when we set up a payment arrangement; that's why we're following up"
                  if contact.arrangement_made else "")
        return {"last_call": when.isoformat(), "arrangement_made": contact.arrangement_made,
                "next_step": f'Say: "According to our records, our last call was on {spoken}{reason}." '
                "Do not add anything that is not in this result. Then continue. Only mark do not "
                "call if they explicitly ask for it."}

    def _tool_schedule_callback(self, date: str, time: str, note: str | None = None) -> dict:
        """N9 / B2: guarda el día y la hora pedidos (hora local del deudor) y cierra la llamada."""
        day = _parse_date(date, "date")
        try:
            hour, minute = (int(part) for part in str(time).strip().split(":"))
            debtor = self._debtor or self._debtor_for_callback()
            zone = ZoneInfo(debtor.timezone) if debtor and debtor.timezone else _DEFAULT_ZONE
            local_when = datetime(day.year, day.month, day.day, hour, minute, tzinfo=zone)
        except ValueError:
            raise _ToolInputError("time must be HH:MM in 24-hour format") from None
        try:
            self._uc.schedule_callback.execute(self.call_id, local_when, note)
        except CallbackTimeError:
            return {"error": "invalid_callback_time", "next_step": "That time is not available. Ask for "
                    "another day and time between 8 AM and 9 PM their time, within the next 30 days."}
        self._close(CallOutcome.CALLBACK_REQUESTED)
        spoken = f"{_spoken_date(local_when.date())} at {_spoken_time(local_when)}"
        if self._debtor is None:
            # Sin verificar (por ejemplo, contestó un familiar): solo la frase fija (hallazgo 2).
            return {"scheduled": True, "callback": local_when.isoformat(), "next_step":
                    f'Say exactly: "Thank you, we\'ll try again on {spoken}. Goodbye." '
                    f"{NOTHING_BEFORE_VERIFICATION} {ALREADY_CLOSED}"}
        return {"scheduled": True, "callback": local_when.isoformat(), "next_step":
                f'Confirm: "We\'ll call back on {spoken}." Then say goodbye. {ALREADY_CLOSED}'}

    def _debtor_for_callback(self) -> DebtorSummary | None:
        """Sin verificación: el deudor de la cuenta (saliente) o el primero de ese teléfono (entrante)."""
        if self._direction is CallDirection.OUTBOUND:
            return self._uc.get_debtor_by_account.execute(self._outbound_account)
        candidates = self._uc.find_debtors_by_phone.execute(self._caller_phone)
        return candidates[0] if candidates else None

    def _tool_mark_do_not_call(self) -> dict:
        self.summary = self._uc.mark_do_not_call.execute(self.call_id, self._transcript())
        self._mark_ended(CallOutcome.RECORDING_REFUSED if self._recording_refused
                         else CallOutcome.DO_NOT_CALL)
        return {"recorded": True, "next_step": "Confirm politely that they will not be called "
                f"again and say goodbye. {ALREADY_CLOSED}"}

    def _tool_record_collection_hold(self, reason: str, details: str | None = None) -> dict:
        """Prueba de ataque (2026-11-19): abogado, bancarrota o fallecido frenan la cobranza."""
        try:
            hold = CollectionHold(reason)
        except ValueError:
            raise _ToolInputError("reason must be attorney, bankruptcy or deceased") from None
        self.summary = self._uc.record_collection_hold.execute(self.call_id, hold, details, self._transcript())
        self._mark_ended(CallOutcome.RECORDING_REFUSED if self._recording_refused
                         else CallOutcome.COLLECTION_HOLD)
        say = _COLLECTION_HOLD_SENTENCE[hold]
        return {"recorded": True, "next_step": f'Say exactly: "{say}" Do not discuss the debt any further. '
                f"{NOTHING_BEFORE_VERIFICATION if self._debtor is None else ''} {ALREADY_CLOSED}".replace("  ", " ")}

    def _tool_transfer_to_human(self, reason: str) -> dict:
        if self._recording_refused:
            raise ValueError("Without recording consent the call can only end as recording_refused")
        # B3: si ya se cerró un acuerdo, el resultado sigue siendo el acuerdo; el motivo dice por qué
        # se transfirió (B4), para que el cobrador no tenga que volver a preguntar.
        outcome = CallOutcome.ARRANGEMENT_MADE if self._arrangement_made else CallOutcome.TRANSFERRED_TO_HUMAN
        self._close(outcome, reason)
        return {"transferring": True, "next_step": "Tell them you are transferring them to a "
                "representative now."}

    def _tool_end_call(self, outcome: str) -> dict:
        try:
            call_outcome = CallOutcome(outcome)
        except ValueError:
            raise _ToolInputError(f"Unknown outcome: {outcome}") from None
        if call_outcome not in END_OUTCOMES:
            raise _ToolInputError(f"Use the matching tool for {outcome}")
        if call_outcome is CallOutcome.ARRANGEMENT_MADE and not self._arrangement_made:
            raise ValueError("No arrangement was accepted in this call")
        if (call_outcome in _THIRD_PARTY_OUTCOMES and self._direction is CallDirection.OUTBOUND
                and self._debtor is None and self._recording_notice_given and not self._third_party_rechecked):
            # Hallazgo 4 (simulación 7 con Haiku): el agente dio el aviso de grabación, que en salientes
            # solo se da cuando la persona confirma ser el deudor, y en el mismo turno cerró como "otra
            # persona". La primera vez se le pide confirmar; si la persona dice que no es, la segunda vale.
            self._third_party_rechecked = True
            debtor = self._debtor_for_callback()
            name = f"{debtor.first_name} {debtor.last_name}" if debtor else "the account holder"
            return {"error": "confirm_who_answered", "next_step":
                    "Do not end the call yet: you already treated this person as the debtor (you gave the "
                    f'recording notice). If you are not sure who you are speaking with, ask: "Am I speaking '
                    f'with {name}?" Only if they clearly say they are not, call end_call again.'}
        if call_outcome in _THIRD_PARTY_OUTCOMES and (
                self._direction is CallDirection.INBOUND or self._debtor is not None):
            # "Contestó otra persona" solo existe en salientes y antes de verificar al deudor. Si no,
            # la llamada queda como volver a llamar (prueba con la API real del 2026-11-15).
            call_outcome = CallOutcome.CALLBACK_REQUESTED
        self._close(call_outcome)
        if call_outcome in _THIRD_PARTY_OUTCOMES:
            return {"ended": True, "next_step": f'Say exactly: "{THIRD_PARTY_GOODBYE}" '
                    f"{NOTHING_BEFORE_VERIFICATION} {ALREADY_CLOSED}"}
        return {"ended": True, "next_step": "Say a short goodbye if you have not already."}

    # --- apoyo ---

    def _debtor_to_verify(self, spoken_name: str) -> DebtorSummary | None:
        if self._direction is CallDirection.OUTBOUND:
            return self._uc.get_debtor_by_account.execute(self._outbound_account)
        candidates = self._uc.find_debtors_by_phone.execute(self._caller_phone)
        if not candidates and self._lookup_by_name and self._uc.find_debtors_by_name is not None:
            candidates = self._uc.find_debtors_by_name.execute(spoken_name)
        # Un teléfono puede ser compartido: se verifica a quien coincide con el nombre dicho.
        return next((d for d in candidates if names_match(spoken_name, d.first_name, d.last_name)),
                    candidates[0] if candidates else None)

    def _require_debtor(self) -> DebtorSummary:
        if self._debtor is None:
            raise ArrangementRuleError(RuleViolation.IDENTITY_NOT_VERIFIED)
        return self._debtor

    def _require_own_account(self, account_ref: str) -> AccountSummary:
        account = next((a for a in self._require_debtor().accounts if a.external_id == account_ref), None)
        if account is None:
            raise _ToolInputError("Unknown account_ref. Use one from get_account_details.")
        return account

    @staticmethod
    def _account_view(account: AccountSummary) -> dict:
        view = {
            "account_ref": account.external_id,
            "creditor": account.creditor_name,
            "account_ending_in": account.account_number_masked[-4:],
            "balance": dollars(account.current_balance_cents),
            "minimum_partial_payment": dollars(
                -(-account.current_balance_cents * REGULAR_MIN_PARTIAL_PAYMENT_PCT // 100)),
        }
        if account.nsf_amount_cents is not None:
            view["returned_payment"] = {
                "amount": dollars(account.nsf_amount_cents),
                "returned_payment_fee": dollars(account.nsf_fee_cents),
                "date": account.nsf_date.isoformat() if account.nsf_date else None,
            }
            reason = _return_reason(account)
            if reason:
                view["returned_payment"]["reason"] = reason
        return view

    def _rule_error(self, violation: RuleViolation, tool_input: dict) -> dict:
        result: dict[str, Any] = {"error": violation.value,
                                  "next_step": _NEXT_STEP_BY_RULE.get(violation, "Use transfer_to_human.")}
        if violation is RuleViolation.HARDSHIP_REQUIRED:
            # Hallazgo 3: el sistema le da al agente la pregunta exacta que toca.
            answered = self._uc.record_hardship_assessment.questions_answered(self.call_id)
            result["next_step"] = ("Before more options, the hardship questions are needed. "
                                   + _next_hardship_question(answered))
        if violation is RuleViolation.AMOUNT_BELOW_FLOOR and self._debtor is not None:
            account = next((a for a in self._debtor.accounts
                            if a.external_id == tool_input.get("account_ref")), None)
            if account is not None:
                result["minimum_amount"] = self._account_view(account)["minimum_partial_payment"]
        if violation is RuleViolation.FIRST_PAYMENT_DATE_OUT_OF_RANGE:
            result.update(self._first_payment_window())
        return result

    def _close(self, outcome: CallOutcome, transfer_reason: str | None = None) -> None:
        if transfer_reason:
            self.summary = self._uc.end_call.execute(self.call_id, outcome, self._transcript(),
                                                     transfer_reason=transfer_reason)
        else:
            self.summary = self._uc.end_call.execute(self.call_id, outcome, self._transcript())
        self._mark_ended(outcome)
        self.transferred = bool(transfer_reason)

    def _mark_ended(self, outcome: CallOutcome) -> None:
        self.ended = True
        self.outcome = outcome

    def _result(self, call: ToolCall, content: dict, error: bool = False) -> ToolResult:
        if self.caller_hung_up and "next_step" in content:
            content = {**content, "next_step": HUNG_UP_NEXT_STEP}
        return ToolResult(call.id, json.dumps(content, ensure_ascii=False), is_error=error)


def _next_hardship_question(answered: int) -> str:
    """Hallazgo 3: la siguiente Hardship Question, exacta, para hacerlas en orden y una por una."""
    if answered >= HARDSHIP_QUESTION_COUNT:
        return "All the hardship questions are answered. Call propose_offer."
    number = answered + 1
    return (f'Ask question {number} of {HARDSHIP_QUESTION_COUNT}, kindly and on its own: '
            f'"{HARDSHIP_QUESTIONS[number - 1]}" Wait for the answer, then call record_hardship_answers '
            f"with question_number {number}. If the debtor already answered it earlier in the call, do "
            f"not ask it again: save that answer with question_number {number}.")


# Hallazgo 2 de las simulaciones con Haiku (2026-11-18): sin una frase exacta, el agente improvisaba
# "I can't discuss any account", que le confirma a un tercero que existe una cuenta.
NOT_VERIFIED_SENTENCE = "I'm sorry, I wasn't able to verify your identity, so I can't continue with this call."
NOTHING_BEFORE_VERIFICATION = ("Do not mention any account, balance, payment, debt, collection or the "
                               "creditor, not even to say you cannot discuss them.")
THIRD_PARTY_GOODBYE = "Thank you for your time. Goodbye."
# Prueba de ataque (2026-11-19): la frase fija al frenar la cobranza por un caso legal.
_COLLECTION_HOLD_SENTENCE = {
    CollectionHold.ATTORNEY: "Thank you. We'll contact your attorney from now on. Goodbye.",
    CollectionHold.BANKRUPTCY: ("Thank you for letting us know. We'll stop collection activity while a "
                                "representative reviews it. Goodbye."),
    CollectionHold.DECEASED: "I'm sorry for your loss. We'll update our records. Goodbye.",
}
# Hallazgo 6: estas herramientas ya cierran la llamada; el agente intentaba cerrarla otra vez con end_call
# y repetía la despedida (o decía "the call has ended").
ALREADY_CLOSED = "The call is already closed: do not call end_call and do not say that the call has ended."

_VERIFICATION_NEXT_STEP = {
    VerificationOutcome.VERIFIED:
        f'Say "This is" and the company full name, then this sentence exactly: "{DISCLOSURE}" '
        'Then call get_account_details.',
    VerificationOutcome.NAME_RETRY:
        "Ask the caller to spell their last name letter by letter, then call verify_identity again "
        "with name_was_spelled true.",
    VerificationOutcome.FAILED:
        "Say the information did not match our records, without saying which item, and ask them "
        "to repeat it. Then call verify_identity again.",
    VerificationOutcome.MAX_ATTEMPTS_REACHED:
        f'Say exactly: "{NOT_VERIFIED_SENTENCE}" {NOTHING_BEFORE_VERIFICATION} Then call end_call with '
        "outcome verification_failed.",
    VerificationOutcome.LOCKED:
        "Say exactly: \"I'm sorry, I wasn't able to verify your identity, so I'll transfer you to a "
        f'representative who can help." {NOTHING_BEFORE_VERIFICATION} Then call transfer_to_human.',
    VerificationOutcome.IDENTITY_MISMATCH:
        "The call is now closed. Say exactly: \"I'm sorry, I wasn't able to verify your identity. "
        'Please call us back with your own information." Do not say which item did not match. '
        f"{NOTHING_BEFORE_VERIFICATION} Then say goodbye.",
    VerificationOutcome.INVALID_INPUT:
        "Those are not details the caller gave. Never guess or use placeholders. Ask the caller for "
        "their full name, the last four digits of their Social Security number and their date of "
        "birth, wait for the answer, then call verify_identity with exactly what they said. This did "
        "not count as an attempt.",
}
# B9: tras rechazar una propuesta, si el deudor dio otro monto se arma un parcial con ese monto.
_DECLINED_NEXT_STEP = ("If the debtor offered a different amount they can pay, call "
                       "propose_partial_payment with that amount. If they asked for a number of "
                       "payments (for example, 3 installments), do not offer another option yet: ask "
                       "\"How much could you comfortably pay each month?\" and then call propose_offer "
                       "with max_payment_dollars. Otherwise call propose_offer for the next option.")
_THIRD_PARTY_OUTCOMES = frozenset({CallOutcome.WRONG_PARTY, CallOutcome.DEBTOR_UNAVAILABLE})
HUNG_UP_NEXT_STEP = "The caller already hung up. Do not say anything."
_LAST_ATTEMPT_NEXT_STEP = (
    "Say the information did not match our records, without saying which item, then say exactly: "
    "\"No problem, let's try once more. Please take your time, I can try one more time on this call.\" "
    "Ask for the full name, the last four digits of the SSN and the date of birth again, then call "
    "verify_identity again.")
def _last_attempt_next_step(mismatched: list[str], ssn_heard: str) -> str:
    """Antes del último intento se pregunta solo por lo que no coincidió (usuario, 2026-11-22)."""
    if not mismatched:
        return _LAST_ATTEMPT_NEXT_STEP
    steps = []
    if "ssn_last4" in mismatched:
        steps.append(f'Say: "To confirm it better, are the last four digits of your Social Security '
                     f'number {" ".join(ssn_heard)}?" and wait for yes or no. If no, ask for the last '
                     "four digits again.")
    if "date_of_birth" in mismatched:
        steps.append('Ask only: "Could you tell me your date of birth again?"')
    if "full_name" in mismatched:
        steps.append("Ask them to spell their first and last name, letter by letter.")
    return (" ".join(steps) + " Do not ask again for the other items: they matched. Then call "
            "verify_identity with the items that matched exactly as before and the new answers. "
            "This is the last attempt on this call.")


# N12: al cerrar sin verificar, se ofrece el número para devolver la llamada (si está configurado).
_OFFER_CALLBACK_NUMBER = frozenset({VerificationOutcome.MAX_ATTEMPTS_REACHED,
                                    VerificationOutcome.IDENTITY_MISMATCH})


def spoken_phone(e164: str) -> str:
    """"+18005550199" -> "1-800-555-0199" (para decirlo en voz). Otros formatos se dejan igual."""
    digits = "".join(ch for ch in e164 if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        return f"1-{digits[1:4]}-{digits[4:7]}-{digits[7:]}"
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return e164
