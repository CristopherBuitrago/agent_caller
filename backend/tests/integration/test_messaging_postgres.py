"""N1 de punta a punta contra PostgreSQL: acuerdo de Jane (TEST-001) -> SMS de confirmación y links."""

from datetime import date

import pytest

from cobranza.domain.call import CallDirection
from cobranza.domain.identity import VerificationOutcome
from cobranza.messaging.infrastructure.container import build_messaging


class RecordingSender:
    def __init__(self):
        self.sent = []

    def send(self, to_phone, body):
        self.sent.append((to_phone, body))
        return f"msg-{len(self.sent)}"


@pytest.fixture
def jane_arrangement(use_cases, started_calls, pool):
    """Jane acepta USD 90 hoy y el resto (USD 395) a los 30 días. Devuelve (id del acuerdo, fechas)."""
    call = use_cases.start_call.execute(CallDirection.INBOUND, "+13055550001")
    started_calls.append(call)
    use_cases.record_recording_consent.execute(call, True)
    jane = use_cases.find_debtors_by_phone.execute("+13055550001")[0]
    assert use_cases.verify_identity.execute(
        call, jane.id, "Jane Carter", "1234", date(1985, 3, 14)) is VerificationOutcome.VERIFIED
    partial = use_cases.propose_partial_payment.execute(call, "ACC-T001", 9000)
    arrangement_id = use_cases.record_offer_response.execute(call, partial.id, accepted=True)
    return arrangement_id, [p.due_date for p in partial.proposal.payments]


def _sms_rows(pool, arrangement_id):
    with pool.connection() as conn:
        return conn.execute(
            """SELECT kind, status, to_phone, provider_message_id, sent_at IS NOT NULL, body
               FROM sms_messages WHERE arrangement_id = %s ORDER BY created_at""",
            (arrangement_id,),
        ).fetchall()


def test_new_arrangement_gets_one_confirmation(use_cases, pool, jane_arrangement):
    arrangement_id, dates = jane_arrangement
    sender = RecordingSender()
    messaging = build_messaging(pool, use_cases, sender=sender)

    messaging.send_confirmations.execute()
    messaging.send_confirmations.execute()  # la tarea vuelve a correr

    rows = _sms_rows(pool, arrangement_id)
    assert len(rows) == 1
    kind, status, phone, provider_id, sent, body = rows[0]
    assert (kind, status, phone, sent) == ("arrangement_confirmation", "sent", "+13055550001", True)
    assert provider_id.startswith("msg-")
    assert "$90.00 on" in body and "$395.00 on" in body and "debt" not in body.lower()
    assert sum(arrangement_body == body for _, arrangement_body in sender.sent) == 1


def test_each_installment_gets_its_link_on_its_date(use_cases, pool, jane_arrangement):
    arrangement_id, (first_due, second_due) = jane_arrangement
    messaging = build_messaging(pool, use_cases, sender=RecordingSender())

    messaging.send_due_payment_links.execute(first_due)
    messaging.send_due_payment_links.execute(first_due)  # no repite
    links = [r for r in _sms_rows(pool, arrangement_id) if r[0] == "payment_link"]
    assert len(links) == 1 and "$90.00 is due today" in links[0][5]

    messaging.send_due_payment_links.execute(second_due)
    links = [r for r in _sms_rows(pool, arrangement_id) if r[0] == "payment_link"]
    assert len(links) == 2 and "$395.00 is due today" in links[1][5]
    assert all(r[1] == "sent" for r in links)


def test_do_not_call_still_gets_payment_texts(use_cases, pool, jane_arrangement):
    """Decisión del 2026-11-12: "no llamar" no detiene los SMS de un acuerdo que el deudor aceptó."""
    arrangement_id, (first_due, _) = jane_arrangement
    with pool.connection() as conn:
        conn.execute("UPDATE debtors SET do_not_call = true WHERE external_id = 'TEST-001'")
    messaging = build_messaging(pool, use_cases, sender=RecordingSender())
    messaging.send_due_payment_links.execute(first_due)
    assert [r[0] for r in _sms_rows(pool, arrangement_id)] == ["payment_link"]


def test_reminder_three_days_before_the_second_installment(use_cases, pool, jane_arrangement):
    """N10: aviso informativo 3 días antes; el link llega el día de la cuota."""
    from datetime import timedelta
    arrangement_id, (_, second_due) = jane_arrangement
    messaging = build_messaging(pool, use_cases, sender=RecordingSender())
    messaging.send_payment_reminders.execute(second_due - timedelta(days=3))
    messaging.send_payment_reminders.execute(second_due - timedelta(days=3))   # no repite
    reminders = [r for r in _sms_rows(pool, arrangement_id) if r[0] == "payment_reminder"]
    assert len(reminders) == 1 and reminders[0][1] == "sent"
    assert "$395.00 is due on" in reminders[0][5] and "http" not in reminders[0][5]
