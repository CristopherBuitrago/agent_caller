"""N1: confirmación del acuerdo y link de pago de cada cuota por SMS.

Corre como tarea programada (messaging/infrastructure/run.py). Usa solo casos de uso del
núcleo; nunca lee las tablas del núcleo directamente.

Los SMS se envían aunque el deudor esté marcado do_not_call: una llamada no es un SMS y el
deudor aceptó el acuerdo (decisión del 2026-11-12). Darse de baja ("STOP") lo maneja el
proveedor de SMS.
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from cobranza.application.interfaces.clock import Clock
from cobranza.application.use_cases.payment_schedule import ListNewArrangements, ListPaymentsDue
from cobranza.messaging.application.ports import (
    PaymentLinkProvider,
    SmsKind,
    SmsRepository,
    SmsSender,
    SmsSendError,
)
from cobranza.messaging.application.texts import confirmation_text, payment_link_text

log = logging.getLogger(__name__)

# Cuántos días hacia atrás se buscan acuerdos sin confirmación (por si la tarea no corrió).
CONFIRMATION_LOOKBACK = timedelta(days=7)


@dataclass
class SendReport:
    sent: int = 0
    failed: int = 0
    skipped: int = 0  # ya enviado, en curso o sin teléfono


class _Delivery:
    def __init__(self, sms: SmsRepository, sender: SmsSender, clock: Clock):
        self._sms = sms
        self._sender = sender
        self._clock = clock

    def deliver(self, report: SendReport, kind: SmsKind, debtor_id: str, arrangement_id: str,
                scheduled_payment_id: str | None, phone: str | None, body: str) -> None:
        if not phone:
            report.skipped += 1
            log.warning("Sin teléfono para el SMS %s del acuerdo %s", kind.value, arrangement_id)
            return
        sms_id = self._sms.claim(kind, debtor_id, arrangement_id, scheduled_payment_id, phone, body)
        if sms_id is None:
            report.skipped += 1
            return
        try:
            provider_id = self._sender.send(phone, body)
        except SmsSendError as e:
            self._sms.mark_failed(sms_id, str(e))
            report.failed += 1
            log.warning("No se pudo enviar el SMS %s", sms_id, exc_info=True)
            return
        self._sms.mark_sent(sms_id, provider_id, self._clock.now())
        report.sent += 1


class SendArrangementConfirmations:
    """Envía la confirmación de cada acuerdo nuevo que todavía no la tiene."""

    def __init__(self, list_new_arrangements: ListNewArrangements, sms: SmsRepository,
                 sender: SmsSender, clock: Clock, company_name: str):
        self._list = list_new_arrangements
        self._delivery = _Delivery(sms, sender, clock)
        self._clock = clock
        self._company = company_name

    def execute(self) -> SendReport:
        report = SendReport()
        for arrangement in self._list.execute(self._clock.now() - CONFIRMATION_LOOKBACK):
            if not arrangement.payments:
                report.skipped += 1
                continue
            body = confirmation_text(self._company, [(p.amount_cents, p.due_date) for p in arrangement.payments])
            self._delivery.deliver(report, SmsKind.ARRANGEMENT_CONFIRMATION, arrangement.debtor_id,
                                   arrangement.id, None, arrangement.phone, body)
        return report


class SendDuePaymentLinks:
    """Envía el link de pago de cada cuota pendiente que vence hasta `as_of` (una sola vez por cuota)."""

    def __init__(self, list_payments_due: ListPaymentsDue, sms: SmsRepository, sender: SmsSender,
                 links: PaymentLinkProvider, clock: Clock, company_name: str):
        self._list = list_payments_due
        self._delivery = _Delivery(sms, sender, clock)
        self._links = links
        self._company = company_name

    def execute(self, as_of: date) -> SendReport:
        report = SendReport()
        for payment in self._list.execute(as_of):
            link = self._links.link_for(payment.scheduled_payment_id, payment.amount_cents)
            body = payment_link_text(self._company, payment.amount_cents, payment.due_date, as_of, link)
            self._delivery.deliver(report, SmsKind.PAYMENT_LINK, payment.debtor_id, payment.arrangement_id,
                                   payment.scheduled_payment_id, payment.phone, body)
        return report
