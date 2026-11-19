"""Datos de una llamada que el agente necesita conocer. Son los mismos valores que usa el backend
(cobranza.domain.call); llegan por HTTP como texto."""

from enum import Enum


class CallDirection(Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallOutcome(Enum):
    PAYMENT_TAKEN = "payment_taken"
    ARRANGEMENT_MADE = "arrangement_made"
    TRANSFERRED_TO_HUMAN = "transferred_to_human"
    DISPUTE = "dispute"
    DO_NOT_CALL = "do_not_call"
    VERIFICATION_FAILED = "verification_failed"
    WRONG_PARTY = "wrong_party"
    CALLBACK_REQUESTED = "callback_requested"
    NO_ANSWER = "no_answer"
    RECORDING_REFUSED = "recording_refused"
    IDENTITY_MISMATCH = "identity_mismatch"
    DEBTOR_UNAVAILABLE = "debtor_unavailable"
    COLLECTION_HOLD = "collection_hold"
