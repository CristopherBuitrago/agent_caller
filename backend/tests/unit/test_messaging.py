"""N1: textos y casos de uso de la mensajería por SMS, sin base de datos."""

from datetime import date, datetime, timedelta, timezone

import pytest

from cobranza.application.interfaces.payment_schedule import ArrangementView, PaymentDue, ScheduledPaymentView
from cobranza.messaging.application.ports import SmsKind, SmsSendError
from cobranza.messaging.application.send_sms import SendArrangementConfirmations, SendDuePaymentLinks
from cobranza.messaging.application.texts import confirmation_text, money, payment_link_text

NOW = datetime(2026, 11, 12, 15, 0, tzinfo=timezone.utc)
COMPANY = "Lakeside Recovery Services"


# --- textos -------------------------------------------------------------------------------

def test_money():
    assert money(9000) == "$90.00" and money(48500) == "$485.00" and money(123456) == "$1,234.56"


@pytest.mark.parametrize("payments, expected", [
    ([(48500, date(2026, 11, 12))], "$485.00 on Nov 12"),
    ([(9000, date(2026, 11, 11)), (39500, date(2026, 12, 11))], "$90.00 on Nov 11 and $395.00 on Dec 11"),
    ([(12125, date(2026, 11, 11))] * 4, "4 monthly payments of $121.25 starting Nov 11"),
    ([(4852, date(2026, 11, 11))] + [(4850, date(2026, 12, 11))] * 9,
     "10 monthly payments starting Nov 11: $48.52, then $48.50 each"),
])
def test_confirmation_text(payments, expected):
    text = confirmation_text(COMPANY, payments)
    assert text == (f"{COMPANY}: your payment arrangement is set: {expected}. "
                    "We'll text you a secure payment link on each date. Reply STOP to opt out.")
    assert "debt" not in text.lower()


def test_payment_link_text_today_and_late():
    today = date(2026, 12, 11)
    assert payment_link_text(COMPANY, 39500, today, today, "https://pay/x") == (
        f"{COMPANY}: your payment of $395.00 is due today. Pay securely here: https://pay/x "
        "Reply STOP to opt out.")
    assert "was due on Dec 10" in payment_link_text(COMPANY, 39500, date(2026, 12, 10), today, "u")


# --- dobles -------------------------------------------------------------------------------

class FakeClock:
    def now(self):
        return NOW


class FakeList:
    def __init__(self, items):
        self.items = items
        self.calls = []

    def execute(self, arg):
        self.calls.append(arg)
        return self.items


class FakeSms:
    """Imita los índices únicos: un mensaje por (tipo, acuerdo o cuota); un fallido se reintenta."""

    def __init__(self):
        self.rows = {}

    def claim(self, kind, debtor_id, arrangement_id, scheduled_payment_id, to_phone, body):
        key = (kind, scheduled_payment_id or arrangement_id)
        row = self.rows.get(key)
        if row and row["status"] != "failed":
            return None
        self.rows[key] = {"id": str(key), "status": "pending", "to": to_phone, "body": body}
        return str(key)

    def _row(self, sms_id):
        return next(r for r in self.rows.values() if r["id"] == sms_id)

    def mark_sent(self, sms_id, provider_message_id, sent_at):
        self._row(sms_id).update(status="sent", provider=provider_message_id, sent_at=sent_at)

    def mark_failed(self, sms_id, error):
        self._row(sms_id).update(status="failed", error=error)


class FakeSender:
    def __init__(self, fail=False):
        self.fail = fail
        self.sent = []

    def send(self, to_phone, body):
        if self.fail:
            raise SmsSendError("provider down")
        self.sent.append((to_phone, body))
        return f"msg-{len(self.sent)}"


class FakeLinks:
    def link_for(self, scheduled_payment_id, amount_cents):
        return f"https://pay.test/{scheduled_payment_id}"


def _arrangement(phone="+13055550001"):
    return ArrangementView("arr-1", "deb-1", phone, NOW, (
        ScheduledPaymentView("sp-1", 1, 9000, date(2026, 11, 12), "pending"),
        ScheduledPaymentView("sp-2", 2, 39500, date(2026, 12, 12), "pending"),
    ))


def _due(sp="sp-2", due=date(2026, 12, 12), phone="+13055550001"):
    return PaymentDue(sp, "arr-1", "deb-1", phone, 2, 39500, due)


# --- confirmaciones -----------------------------------------------------------------------

def test_confirmation_is_sent_once_per_arrangement():
    sms, sender = FakeSms(), FakeSender()
    listing = FakeList([_arrangement()])
    use_case = SendArrangementConfirmations(listing, sms, sender, FakeClock(), COMPANY)
    assert use_case.execute().sent == 1
    assert use_case.execute().skipped == 1          # la tarea vuelve a correr: no repite
    assert sender.sent == [("+13055550001", confirmation_text(
        COMPANY, [(9000, date(2026, 11, 12)), (39500, date(2026, 12, 12))]))]
    assert listing.calls[0] == NOW - timedelta(days=7)


def test_failed_confirmation_is_recorded_and_retried():
    sms = FakeSms()
    listing = FakeList([_arrangement()])
    report = SendArrangementConfirmations(listing, sms, FakeSender(fail=True), FakeClock(), COMPANY).execute()
    assert report.failed == 1
    assert sms.rows[(SmsKind.ARRANGEMENT_CONFIRMATION, "arr-1")]["error"] == "provider down"
    retry = SendArrangementConfirmations(listing, sms, FakeSender(), FakeClock(), COMPANY).execute()
    assert retry.sent == 1


def test_no_phone_is_skipped():
    sender = FakeSender()
    report = SendArrangementConfirmations(FakeList([_arrangement(phone=None)]), FakeSms(), sender,
                                          FakeClock(), COMPANY).execute()
    assert report.skipped == 1 and sender.sent == []


# --- links de pago ------------------------------------------------------------------------

def test_payment_link_is_sent_once_per_installment():
    sms, sender = FakeSms(), FakeSender()
    listing = FakeList([_due()])
    use_case = SendDuePaymentLinks(listing, sms, sender, FakeLinks(), FakeClock(), COMPANY)
    assert use_case.execute(date(2026, 12, 12)).sent == 1
    assert use_case.execute(date(2026, 12, 12)).skipped == 1
    assert listing.calls == [date(2026, 12, 12)] * 2
    assert "https://pay.test/sp-2" in sender.sent[0][1] and "is due today" in sender.sent[0][1]
