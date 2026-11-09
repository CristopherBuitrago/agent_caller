"""Función 1 de punta a punta contra PostgreSQL. Usa los casos TEST-xxx de db/init/002_seed_mock.sql."""


def _only(debtors):
    assert len(debtors) == 1
    return debtors[0]


# --- llamadas entrantes -------------------------------------------------------

def test_nsf_simple_is_collectable(find_by_phone):
    jane = _only(find_by_phone("+13055550001"))
    assert (jane.first_name, jane.last_name) == ("Jane", "Carter")
    account = jane.accounts[0]
    assert account.status == "NSF"
    assert account.current_balance_cents == 48500
    assert account.account_number_masked == "****4821"
    assert jane.can_collect(account)


def test_phone_in_any_format_is_found(find_by_phone):
    assert _only(find_by_phone("(305) 555-0001")).external_id == "TEST-001"
    assert _only(find_by_phone("305.555.0001")).external_id == "TEST-001"


def test_unknown_phone_returns_empty(find_by_phone):
    assert find_by_phone("+19995550199") == []


def test_found_by_secondary_phone(find_by_phone):
    assert _only(find_by_phone("+15125550012")).external_id == "TEST-002"


def test_multiple_accounts_all_returned(find_by_phone):
    mark = _only(find_by_phone("+15125550002"))
    assert sorted(a.status for a in mark.accounts) == ["NSF", "NSF"]
    assert len(mark.collectable_accounts) == 2


def test_shared_phone_returns_every_debtor(find_by_phone):
    assert sorted(d.first_name for d in find_by_phone("+16025550007")) == ["Ana", "Luis"]


def test_missing_timezone_is_inferred(find_by_phone):
    lucy = _only(find_by_phone("+12125550003"))  # 212 = Nueva York
    assert lucy.us_state is None
    assert (lucy.timezone, lucy.timezone_inferred) == ("America/New_York", True)


def test_stored_timezone_is_not_marked_inferred(find_by_phone):
    jane = _only(find_by_phone("+13055550001"))
    assert (jane.timezone, jane.timezone_inferred) == ("America/New_York", False)


def test_attempt_status_goes_to_human(find_by_phone):
    grace = _only(find_by_phone("+16175550009"))  # 617 = Boston
    assert grace.accounts[0].status == "fourth_attempt"
    assert grace.collectable_accounts == ()
    assert grace.timezone == "America/New_York"


def test_paid_goes_to_human(find_by_phone):
    tom = _only(find_by_phone("+12065550006"))
    assert tom.accounts[0].status == "PAID"
    assert tom.collectable_accounts == ()


def test_disputed_is_not_collectable(find_by_phone):
    carl = _only(find_by_phone("+13125550004"))
    assert carl.accounts[0].is_disputed
    assert carl.collectable_accounts == ()


def test_do_not_call_is_not_collectable(find_by_phone):
    rosa = _only(find_by_phone("+14155550005"))
    assert rosa.do_not_call
    assert rosa.collectable_accounts == ()


# --- llamadas salientes -------------------------------------------------------

def test_get_by_account_returns_owner_with_all_accounts(get_by_account):
    mark = get_by_account("ACC-T002b")
    assert mark.external_id == "TEST-002"
    assert {a.external_id for a in mark.accounts} == {"ACC-T002a", "ACC-T002b"}


def test_get_by_unknown_account_returns_none(get_by_account):
    assert get_by_account("ACC-DOES-NOT-EXIST") is None
