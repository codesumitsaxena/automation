"""Unit tests for the Reveal Budget Planner in CreditGuard."""

from app.services.credit_guard import CreditGuard


def test_planner_50_credits_all_reveals_enabled():
    """Verify that with 50 credits, 1 company, and 5 contacts with both reveals enabled:

    - Base cost = 7 (1 company + 1 search + 5 contacts)
    - 5 emails cost 25
    - 1 phone costs 15
    - Total cost = 47 of 50
    - Safety reserve of 3 credits is preserved intact
    - Plan summary matches: '5 emails (25) + 1 phone (15) + base (7) = 47 of 50'
    """
    plan = CreditGuard.plan_reveal_budget(
        remaining_balance=50,
        target_contacts=5,
        enrich_company=True,
        enable_email_reveal=True,
        enable_phone_reveal=True,
        safety_reserve=3,
    )

    assert plan.can_proceed is True
    assert plan.base_cost == 7
    assert plan.emails_allowed == 5
    assert plan.email_cost == 25
    assert plan.phones_allowed == 1
    assert plan.phone_cost == 15
    assert plan.total_estimated_cost == 47
    assert plan.balance_after_run == 3
    assert plan.safety_reserve == 3
    assert plan.plan_summary == "5 emails (25) + 1 phone (15) + base (7) = 47 of 50"


def test_planner_phone_reveal_only_for_contacts_with_email():
    """Verify phone reveals are strictly prohibited if email reveals are disabled,

    enforcing the constraint: phone reveal only for contacts who already have email.
    """
    plan = CreditGuard.plan_reveal_budget(
        remaining_balance=50,
        target_contacts=5,
        enrich_company=True,
        enable_email_reveal=False,
        enable_phone_reveal=True,
        safety_reserve=3,
    )

    assert plan.can_proceed is True
    assert plan.emails_allowed == 0
    assert plan.phones_allowed == 0
    assert plan.total_estimated_cost == 7
    assert plan.balance_after_run == 43
    assert any("phone reveals are only permitted for contacts who have email" in note for note in plan.notes)


def test_planner_respects_safety_reserve_tight_budget():
    """Verify that with a tight balance (20 credits) and safety reserve (3 credits):

    - Available for reveals = 20 - 7 - 3 = 10
    - 2 emails cost 10
    - 0 phones allowed (since phone costs 15 and would violate the 3-credit reserve)
    - Total cost = 17
    - Balance after = 3
    """
    plan = CreditGuard.plan_reveal_budget(
        remaining_balance=20,
        target_contacts=5,
        enrich_company=True,
        enable_email_reveal=True,
        enable_phone_reveal=True,
        safety_reserve=3,
    )

    assert plan.can_proceed is True
    assert plan.emails_allowed == 2
    assert plan.email_cost == 10
    assert plan.phones_allowed == 0
    assert plan.total_estimated_cost == 17
    assert plan.balance_after_run == 3
    assert plan.plan_summary == "2 emails (10) + 0 phones (0) + base (7) = 17 of 20"


def test_planner_insufficient_balance_cannot_proceed():
    """Verify that when balance cannot even cover the base cost, can_proceed is False."""
    plan = CreditGuard.plan_reveal_budget(
        remaining_balance=5,
        target_contacts=5,
        enrich_company=True,
        enable_email_reveal=True,
        enable_phone_reveal=True,
        safety_reserve=3,
    )

    assert plan.can_proceed is False
    assert plan.base_cost == 7
    assert plan.emails_allowed == 0
    assert plan.phones_allowed == 0
    assert plan.balance_after_run == -2
    assert any("Insufficient balance" in note for note in plan.notes)


def test_planner_reveals_disabled():
    """Verify that when reveals are disabled, cost is purely base cost (7 credits)."""
    plan = CreditGuard.plan_reveal_budget(
        remaining_balance=50,
        target_contacts=5,
        enrich_company=True,
        enable_email_reveal=False,
        enable_phone_reveal=False,
        safety_reserve=3,
    )

    assert plan.can_proceed is True
    assert plan.emails_allowed == 0
    assert plan.phones_allowed == 0
    assert plan.total_estimated_cost == 7
    assert plan.plan_summary == "0 emails (0) + 0 phones (0) + base (7) = 7 of 50"


def test_smoke_test_single_person_variants():
    """Verify smoke test credit estimations matching the README:

    - Single person WITH email and phone = 23 credits
    - Single person with email only = 8 credits
    - Single person without reveals = 3 credits
    """
    # Variant A: Base profile only
    plan_base = CreditGuard.plan_reveal_budget(
        remaining_balance=50,
        target_contacts=1,
        enrich_company=True,
        enable_email_reveal=False,
        enable_phone_reveal=False,
        safety_reserve=0,
    )
    assert plan_base.total_estimated_cost == 3

    # Variant B: With email only (1 company + 1 search + 1 detail + 1 email = 8)
    plan_email = CreditGuard.plan_reveal_budget(
        remaining_balance=50,
        target_contacts=1,
        enrich_company=True,
        enable_email_reveal=True,
        enable_phone_reveal=False,
        safety_reserve=0,
    )
    assert plan_email.total_estimated_cost == 8

    # Variant C: With email + phone (1 company + 1 search + 1 detail + 1 email + 1 phone = 23)
    plan_full = CreditGuard.plan_reveal_budget(
        remaining_balance=50,
        target_contacts=1,
        enrich_company=True,
        enable_email_reveal=True,
        enable_phone_reveal=True,
        safety_reserve=0,
    )
    assert plan_full.total_estimated_cost == 23
