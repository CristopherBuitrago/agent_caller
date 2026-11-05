"""Dominio y casos de uso de la Función 1, sin base de datos (repositorio en memoria)."""

import dataclasses

from cobranza.infrastructure.services.phonenumbers_phone_service import PhonenumbersPhoneService
from cobranza.application.use_cases.lookup_debtor import FindDebtorsByPhone, GetDebtorByAccount
from cobranza.domain.debtor import AccountSummary, DebtorSummary


def _account(status="NSF", disputed=False, ext="ACC-1") -> AccountSummary:
    return AccountSummary(
        id=ext, external_id=ext, creditor_name="Acme", account_number_masked="****0001",
        current_balance_cents=10000, status=status, payment_method="ACH",
        nsf_amount_cents=9000, nsf_fee_cents=1000, nsf_date=None, nsf_return_code="R01",
        is_disputed=disputed,
    )


def _debtor(phone="+12125550100", timezone=None, do_not_call=False, accounts=None) -> DebtorSummary:
    return DebtorSummary(
        id="d1", external_id="DEB-1", first_name="Jane", last_name="Doe", phone_primary=phone,
        us_state=None, timezone=timezone, timezone_inferred=False, do_not_call=do_not_call,
        accounts=tuple(accounts if accounts is not None else [_account()]),
    )


class InMemoryDebtorRepository:
    def __init__(self, debtors):
        self.debtors = debtors
        self.phone_queries = []

    def find_by_phone(self, phone_e164):
        self.phone_queries.append(phone_e164)
        return [d for d in self.debtors if d.phone_primary == phone_e164]

    def get_by_account(self, account_external_id):
        return next(
            (d for d in self.debtors if any(a.external_id == account_external_id for a in d.accounts)),
            None,
        )


phones = PhonenumbersPhoneService()


# --- dominio ------------------------------------------------------------------

def test_collectable_statuses():
    for status in ["NSF", "first_attempt", "second_attempt", "third_attempt", "fourth_attempt"]:
        debtor = _debtor(accounts=[_account(status)])
        assert debtor.can_collect(debtor.accounts[0]), status
    for status in ["PAID", "CLOSED", "DISPUTED", "PAYMENT_PLAN", "anything_else"]:
        debtor = _debtor(accounts=[_account(status)])
        assert not debtor.can_collect(debtor.accounts[0]), status


def test_disputed_or_do_not_call_blocks_collection():
    assert _debtor(accounts=[_account(disputed=True)]).collectable_accounts == ()
    assert _debtor(do_not_call=True).collectable_accounts == ()


def test_only_collectable_accounts_are_listed():
    debtor = _debtor(accounts=[_account("NSF", ext="A"), _account("PAID", ext="B")])
    assert [a.external_id for a in debtor.collectable_accounts] == ["A"]


def test_summaries_never_expose_dob_or_ssn():
    fields = {f.name for f in dataclasses.fields(DebtorSummary)} | {
        f.name for f in dataclasses.fields(AccountSummary)
    }
    assert not {f for f in fields if "dob" in f or "ssn" in f or "birth" in f}


# --- casos de uso -------------------------------------------------------------

def test_phone_is_normalized_before_querying_repository():
    repo = InMemoryDebtorRepository([_debtor()])
    result = FindDebtorsByPhone(repo, phones).execute("(212) 555-0100")
    assert len(result) == 1
    assert repo.phone_queries == ["+12125550100"]


def test_invalid_phone_never_reaches_repository():
    repo = InMemoryDebtorRepository([_debtor()])
    assert FindDebtorsByPhone(repo, phones).execute("not a phone") == []
    assert repo.phone_queries == []


def test_missing_timezone_is_inferred_from_area_code():
    repo = InMemoryDebtorRepository([_debtor(phone="+13125550100")])  # 312 = Chicago
    debtor = FindDebtorsByPhone(repo, phones).execute("+13125550100")[0]
    assert debtor.timezone == "America/Chicago"
    assert debtor.timezone_inferred


def test_stored_timezone_is_kept():
    repo = InMemoryDebtorRepository([_debtor(timezone="America/Denver")])
    debtor = FindDebtorsByPhone(repo, phones).execute("+12125550100")[0]
    assert debtor.timezone == "America/Denver"
    assert not debtor.timezone_inferred


def test_get_by_account_also_infers_timezone():
    repo = InMemoryDebtorRepository([_debtor(phone="+14155550100", accounts=[_account(ext="X")])])
    debtor = GetDebtorByAccount(repo, phones).execute("X")
    assert debtor.timezone == "America/Los_Angeles"
    assert GetDebtorByAccount(repo, phones).execute("missing") is None
