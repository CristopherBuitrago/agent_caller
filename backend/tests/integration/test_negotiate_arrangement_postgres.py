"""Función 4 de punta a punta contra PostgreSQL. Usa los casos TEST-xxx de db/init/002_seed_mock.sql."""

from datetime import date

import pytest

from cobranza.domain.arrangement import ArrangementRuleError, ArrangementType, RuleViolation as R
from cobranza.domain.call import CallDirection
from cobranza.domain.hardship import HardshipAnswers, HardshipDuration
from cobranza.domain.identity import VerificationOutcome


@pytest.fixture
def verified_jane(use_cases, started_calls):
    """Llamada con grabación aceptada e identidad verificada. Jane debe USD 485 (ACC-T001)."""
    call = use_cases.start_call.execute(CallDirection.INBOUND, "+13055550001")
    started_calls.append(call)
    use_cases.record_recording_consent.execute(call, True)
    jane = use_cases.find_debtors_by_phone.execute("+13055550001")[0]
    assert use_cases.verify_identity.execute(
        call, jane.id, "Jane Carter", "1234", date(1985, 3, 14)) is VerificationOutcome.VERIFIED
    return call


def _saved(pool, arrangement_id):
    with pool.connection() as conn:
        arrangement = conn.execute(
            "SELECT type, total_amount_cents, status FROM payment_arrangements WHERE id = %s",
            (arrangement_id,),
        ).fetchone()
        payments = conn.execute(
            """SELECT sequence, amount_cents, status FROM scheduled_payments
               WHERE arrangement_id = %s ORDER BY sequence""",
            (arrangement_id,),
        ).fetchall()
    return arrangement, payments


def test_plan_is_saved_with_its_payments(use_cases, verified_jane, pool):
    proposal = use_cases.propose_arrangement.execute(verified_jane, "ACC-T001", 3)
    arrangement_id = use_cases.create_arrangement.execute(verified_jane, "ACC-T001", proposal)
    arrangement, payments = _saved(pool, arrangement_id)
    assert arrangement == ("plan", 48500, "active")
    assert payments == [(1, 16168, "pending"), (2, 16166, "pending"), (3, 16166, "pending")]


def test_full_order_ends_in_a_last_resort_partial(use_cases, verified_jane, pool):
    with pytest.raises(ArrangementRuleError) as e:
        use_cases.propose_arrangement.execute(verified_jane, "ACC-T001", 4)
    assert e.value.violation is R.HARDSHIP_REQUIRED

    answers = HardshipAnswers(situation_description="Reduced hours", situation_started="in October",
                              duration_type=HardshipDuration.TEMPORARY, household_support=True,
                              offered_amount_cents=2500, recommended_plan="partial")
    use_cases.record_hardship_assessment.execute(verified_jane, answers)
    with pool.connection() as conn:
        saved = conn.execute(
            """SELECT situation_started, duration_type, household_support, offered_amount_cents
               FROM hardship_assessments WHERE call_id = %s""",
            (verified_jane,),
        ).fetchone()
    assert saved == ("in October", "temporary", True, 2500)
    assert len(use_cases.propose_arrangement.execute(verified_jane, "ACC-T001", 4).payments) == 4

    # El deudor rechaza las 10 ofertas de cuotas; el sistema lo lleva en el registro de la llamada.
    while (offer := use_cases.propose_next_offer.execute(verified_jane, "ACC-T001")) is not None:
        use_cases.record_offer_response.execute(verified_jane, offer.id, accepted=False)
    assert offer is None

    partial = use_cases.propose_partial_payment.execute(verified_jane, "ACC-T001", 2500)  # ~5,15%
    arrangement_id = use_cases.record_offer_response.execute(verified_jane, partial.id, accepted=True)
    arrangement, payments = _saved(pool, arrangement_id)
    assert arrangement == ("partial", 48500, "active")
    assert [p[1] for p in payments] == [2500, 46000]


def test_creating_an_arrangement_moves_the_account_to_ptp(use_cases, verified_jane, pool):
    proposal = use_cases.propose_arrangement.execute(verified_jane, "ACC-T001", 2)
    use_cases.create_arrangement.execute(verified_jane, "ACC-T001", proposal)
    with pool.connection() as conn:
        status = conn.execute("SELECT status FROM accounts WHERE external_id = 'ACC-T001'").fetchone()[0]
    assert status == "PTP"


def test_failed_save_does_not_change_the_account_status(use_cases, verified_jane, pool):
    from cobranza.infrastructure.repositories.postgres_arrangement_repository import (
        PostgresArrangementRepository,
    )
    proposal = use_cases.propose_arrangement.execute(verified_jane, "ACC-T001", 1)
    use_cases.create_arrangement.execute(verified_jane, "ACC-T001", proposal)
    jane = use_cases.find_debtors_by_phone.execute("+13055550001")[0]
    with pytest.raises(ArrangementRuleError):
        PostgresArrangementRepository(pool).create(verified_jane, jane.accounts[0].id, proposal, "OTHER")
    with pool.connection() as conn:
        status = conn.execute("SELECT status FROM accounts WHERE external_id = 'ACC-T001'").fetchone()[0]
    assert status == "PTP"


def test_second_active_arrangement_is_rejected(use_cases, verified_jane):
    proposal = use_cases.propose_arrangement.execute(verified_jane, "ACC-T001", 1)
    assert proposal.type is ArrangementType.FULL
    use_cases.create_arrangement.execute(verified_jane, "ACC-T001", proposal)
    with pytest.raises(ArrangementRuleError) as e:
        use_cases.create_arrangement.execute(verified_jane, "ACC-T001", proposal)
    assert e.value.violation is R.ACTIVE_ARRANGEMENT_EXISTS


def test_database_also_blocks_a_second_active_arrangement(use_cases, verified_jane, pool):
    from cobranza.infrastructure.repositories.postgres_arrangement_repository import (
        PostgresArrangementRepository,
    )
    proposal = use_cases.propose_arrangement.execute(verified_jane, "ACC-T001", 1)
    use_cases.create_arrangement.execute(verified_jane, "ACC-T001", proposal)
    jane = use_cases.find_debtors_by_phone.execute("+13055550001")[0]
    with pytest.raises(ArrangementRuleError) as e:
        PostgresArrangementRepository(pool).create(verified_jane, jane.accounts[0].id, proposal, "PTP")
    assert e.value.violation is R.ACTIVE_ARRANGEMENT_EXISTS


def test_cannot_negotiate_the_account_of_another_debtor(use_cases, verified_jane):
    with pytest.raises(ArrangementRuleError) as e:
        use_cases.propose_arrangement.execute(verified_jane, "ACC-T002a", 1)  # es de Mark
    assert e.value.violation is R.IDENTITY_NOT_VERIFIED


def test_cannot_negotiate_without_verification(use_cases, started_calls):
    call = use_cases.start_call.execute(CallDirection.INBOUND, "+13055550001")
    started_calls.append(call)
    use_cases.record_recording_consent.execute(call, True)
    with pytest.raises(ArrangementRuleError) as e:
        use_cases.propose_arrangement.execute(call, "ACC-T001", 1)
    assert e.value.violation is R.IDENTITY_NOT_VERIFIED


# --- ProposeNextOffer, ProposePartialPayment y RecordOfferResponse contra PostgreSQL (2026-11-11)

def _account_status(pool):
    with pool.connection() as conn:
        return conn.execute("SELECT status FROM accounts WHERE external_id = 'ACC-T001'").fetchone()[0]


def _due_dates(pool, arrangement_id):
    with pool.connection() as conn:
        return [r[0] for r in conn.execute(
            "SELECT due_date FROM scheduled_payments WHERE arrangement_id = %s ORDER BY sequence",
            (arrangement_id,)).fetchall()]


def test_next_offer_then_accept_saves_a_monthly_plan(use_cases, verified_jane, pool):
    first = use_cases.propose_next_offer.execute(verified_jane, "ACC-T001")
    assert first.offer_number == 1 and first.proposal.type is ArrangementType.FULL
    assert use_cases.record_offer_response.execute(verified_jane, first.id, accepted=False) is None
    assert _account_status(pool) == "NSF"  # rechazar no cambia la cuenta

    second = use_cases.propose_next_offer.execute(verified_jane, "ACC-T001")
    assert second.offer_number == 2
    arrangement_id = use_cases.record_offer_response.execute(verified_jane, second.id, accepted=True)
    arrangement, payments = _saved(pool, arrangement_id)
    assert arrangement == ("plan", 48500, "active")
    assert payments == [(1, 24250, "pending"), (2, 24250, "pending")]
    dates = _due_dates(pool, arrangement_id)
    assert dates == [p.due_date for p in second.proposal.payments]
    assert _account_status(pool) == "PTP"


def test_accepting_twice_leaves_a_single_arrangement(use_cases, verified_jane, pool):
    offer = use_cases.propose_next_offer.execute(verified_jane, "ACC-T001")
    use_cases.record_offer_response.execute(verified_jane, offer.id, accepted=True)
    with pytest.raises(ArrangementRuleError) as e:
        use_cases.record_offer_response.execute(verified_jane, offer.id, accepted=True)
    assert e.value.violation is R.ACTIVE_ARRANGEMENT_EXISTS
    with pool.connection() as conn:
        count = conn.execute("SELECT count(*) FROM payment_arrangements WHERE call_id = %s",
                             (verified_jane,)).fetchone()[0]
    assert count == 1


def test_regular_partial_is_saved_with_the_remainder_at_thirty_days(use_cases, verified_jane, pool):
    partial = use_cases.propose_partial_payment.execute(verified_jane, "ACC-T001", 10000)
    arrangement_id = use_cases.record_offer_response.execute(verified_jane, partial.id, accepted=True)
    arrangement, payments = _saved(pool, arrangement_id)
    assert arrangement == ("partial", 48500, "active")
    assert [p[1] for p in payments] == [10000, 38500]
    first, rest = _due_dates(pool, arrangement_id)
    assert (rest - first).days == 30
    assert _account_status(pool) == "PTP"


def test_partial_below_ten_percent_is_refused_before_hardship(use_cases, verified_jane, pool):
    with pytest.raises(ArrangementRuleError) as e:
        use_cases.propose_partial_payment.execute(verified_jane, "ACC-T001", 4800)  # ~9,9%
    assert e.value.violation is R.HARDSHIP_REQUIRED
    assert _account_status(pool) == "NSF"


def test_partial_below_ten_percent_needs_every_offer_rejected(use_cases, verified_jane):
    use_cases.record_hardship_assessment.execute(verified_jane, HardshipAnswers(
        situation_description="Lost job", duration_type=HardshipDuration.TEMPORARY))
    with pytest.raises(ArrangementRuleError) as e:
        use_cases.propose_partial_payment.execute(verified_jane, "ACC-T001", 2500)
    assert e.value.violation is R.OFFERS_NOT_EXHAUSTED


def test_proposal_cannot_be_answered_from_another_call(use_cases, verified_jane, started_calls):
    from cobranza.application.use_cases.negotiate_arrangement import UnknownProposalError
    offer = use_cases.propose_next_offer.execute(verified_jane, "ACC-T001")
    other = use_cases.start_call.execute(CallDirection.INBOUND, "+13055550001")
    started_calls.append(other)
    with pytest.raises(UnknownProposalError):
        use_cases.record_offer_response.execute(other, offer.id, accepted=True)


def test_hardship_answers_saved_one_at_a_time_are_all_kept(use_cases, verified_jane, pool):
    """Error E2 (simulación 5): guardar de a una respuesta borraba las anteriores."""
    use_cases.record_hardship_assessment.execute(verified_jane, HardshipAnswers(
        situation_description="Lost her job last month", situation_started="last month"))
    use_cases.record_hardship_assessment.execute(verified_jane, HardshipAnswers(household_support=True))
    use_cases.record_hardship_assessment.execute(verified_jane, HardshipAnswers(
        offered_amount_cents=3000, notes="Husband works part-time"))
    use_cases.record_hardship_assessment.execute(verified_jane, HardshipAnswers(
        duration_type=HardshipDuration.LONG_TERM, situation_started="six weeks ago"))
    with pool.connection() as conn:
        saved = conn.execute(
            """SELECT situation_description, situation_started, duration_type, household_support,
                      offered_amount_cents, notes
               FROM hardship_assessments WHERE call_id = %s""",
            (verified_jane,),
        ).fetchone()
    # Lo nuevo reemplaza (situation_started); lo que no vino se conserva.
    assert saved == ("Lost her job last month", "six weeks ago", "long_term", True, 3000,
                     "Husband works part-time")
