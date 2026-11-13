"""N10: resultados de pago y acuerdos rotos, sin base de datos."""

from datetime import date, datetime, timezone

import pytest

from cobranza.application.interfaces.payment_ledger import RecordedPayment
from cobranza.application.use_cases.payment_results import BreakOverdueArrangements, RecordPaymentResult

NOW = datetime(2026, 12, 12, 15, 0, tzinfo=timezone.utc)


class FakeLedger:
    def __init__(self):
        self.recorded = []
        self.broken_calls = []

    def record_result(self, scheduled_payment_id, reference, amount_cents, status, processed_at):
        self.recorded.append((scheduled_payment_id, reference, amount_cents, status, processed_at))
        return RecordedPayment("arr-1", False)

    def break_overdue(self, due_on_or_before, account_status):
        self.broken_calls.append((due_on_or_before, account_status))
        return ["arr-1"]


def test_payment_result_is_recorded():
    ledger = FakeLedger()
    RecordPaymentResult(ledger).execute("sp-1", "  REF-123 ", 9000, "approved", NOW)
    assert ledger.recorded == [("sp-1", "REF-123", 9000, "approved", NOW)]


@pytest.mark.parametrize("status, amount, reference", [
    ("refunded", 9000, "REF"), ("approved", 0, "REF"), ("approved", 9000, "  "),
])
def test_invalid_payment_results_are_rejected(status, amount, reference):
    with pytest.raises(ValueError):
        RecordPaymentResult(FakeLedger()).execute("sp-1", reference, amount, status, NOW)


def test_arrangements_break_five_days_after_the_due_date_and_go_back_to_nsf():
    ledger = FakeLedger()
    assert BreakOverdueArrangements(ledger).execute(date(2026, 12, 16)) == ["arr-1"]
    assert ledger.broken_calls == [(date(2026, 12, 11), "NSF")]   # cuotas que vencían hasta el 11
