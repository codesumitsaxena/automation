from dataclasses import dataclass, field
import uuid
from typing import Any

from sqlalchemy import func

from app.config import get_settings
from app.db.database import SessionLocal
from app.db.models import CreditUsage
from app.logging_config import setup_logging

settings = get_settings()
logger = setup_logging(settings.log_level)


class CreditLimitExceededError(Exception):
    """Raised when an operation would exceed the configured credit safety budget."""


@dataclass
class RevealPlan:
    """Projected execution plan and reveal budget allocation."""
    remaining_balance: int
    target_contacts: int
    enrich_company: bool
    base_cost: int
    emails_allowed: int
    email_cost: int
    phones_allowed: int
    phone_cost: int
    total_estimated_cost: int
    balance_after_run: int
    safety_reserve: int
    plan_summary: str
    can_proceed: bool
    notes: list[str] = field(default_factory=list)


class CreditGuard:
    """Enforces credit budgets, estimates costs, and records credit transactions."""

    def __init__(self, max_credits_per_run: int | None = None, dry_run: bool | None = None):
        s = get_settings()
        self.max_credits_per_run = max_credits_per_run or s.max_credits_per_run
        self.dry_run = s.forager_dry_run if dry_run is None else dry_run

    @staticmethod
    def estimate_run_cost(
        enrich_company: bool = True,
        num_contacts: int = 5,
        enable_email_reveal: bool = False,
        enable_phone_reveal: bool = False,
    ) -> dict[str, Any]:
        """Calculate projected credit requirements before running an enrichment job."""
        breakdown = {}
        total = 0

        if enrich_company:
            breakdown["company_search"] = 1
            total += 1

        if num_contacts > 0:
            # 1 credit for person role search
            breakdown["people_role_search"] = 1
            total += 1
            # 1 credit per contact detail lookup
            detail_cost = num_contacts * 1
            breakdown["contact_details"] = detail_cost
            total += detail_cost

            if enable_email_reveal:
                email_cost = num_contacts * 5
                breakdown["work_email_reveals"] = email_cost
                total += email_cost

            if enable_phone_reveal:
                phone_cost = num_contacts * 15
                breakdown["phone_number_reveals"] = phone_cost
                total += phone_cost

        return {
            "estimated_total_credits": total,
            "cost_breakdown": breakdown,
            "dry_run": settings.forager_dry_run,
            "real_cost_if_dry_run": 0 if settings.forager_dry_run else total,
        }

    @staticmethod
    def plan_reveal_budget(
        remaining_balance: int,
        target_contacts: int = 5,
        enrich_company: bool = True,
        enable_email_reveal: bool = False,
        enable_phone_reveal: bool = False,
        safety_reserve: int = 3,
    ) -> RevealPlan:
        """Plan contact email and phone reveals based on remaining Forager credit balance.

        Cost table:
          - Company firmographics lookup: 1 credit
          - People role search: 1 credit
          - Person detail lookup: 1 credit per contact
          - Work email reveal: 5 credits per contact
          - Phone number reveal: 15 credits per contact

        Rules:
          - Base operations (company, role search, contact details) are reserved first.
          - Safety reserve (default: 3 credits) must remain intact after all operations.
          - Phone reveals are ONLY awarded to contacts who already receive an email reveal.
          - Phone reveals are ONLY awarded if balance after the reveal stays >= safety_reserve.
        """
        notes: list[str] = []

        company_cost = 1 if enrich_company else 0
        search_cost = 1 if target_contacts > 0 else 0
        detail_cost = target_contacts * 1
        base_cost = company_cost + search_cost + detail_cost

        # If remaining balance cannot even cover base cost
        if remaining_balance < base_cost:
            notes.append(
                f"Insufficient balance ({remaining_balance}) to cover base enrichment cost ({base_cost})."
            )
            summary = f"0 emails (0) + 0 phones (0) + base ({base_cost}) = {base_cost} of {remaining_balance}"
            return RevealPlan(
                remaining_balance=remaining_balance,
                target_contacts=target_contacts,
                enrich_company=enrich_company,
                base_cost=base_cost,
                emails_allowed=0,
                email_cost=0,
                phones_allowed=0,
                phone_cost=0,
                total_estimated_cost=base_cost,
                balance_after_run=remaining_balance - base_cost,
                safety_reserve=safety_reserve,
                plan_summary=summary,
                can_proceed=False,
                notes=notes,
            )

        # Available pool for reveals while keeping safety reserve
        available_for_reveals = max(0, remaining_balance - base_cost - safety_reserve)

        emails_allowed = 0
        email_cost = 0
        phones_allowed = 0
        phone_cost = 0

        # 1. Email allocation
        if enable_email_reveal:
            max_emails_by_budget = available_for_reveals // 5
            emails_allowed = min(target_contacts, max_emails_by_budget)
            email_cost = emails_allowed * 5
            available_for_reveals -= email_cost
            if emails_allowed < target_contacts:
                notes.append(
                    f"Only {emails_allowed} of {target_contacts} contacts can receive email reveals within safe budget."
                )
        else:
            notes.append("Email reveals disabled by configuration (ENABLE_EMAIL_REVEAL=False).")

        # 2. Phone allocation (Phone reveal ONLY for contacts who already have email, and keeping safety reserve)
        if enable_phone_reveal:
            if not enable_email_reveal or emails_allowed == 0:
                notes.append("Phone reveals skipped: phone reveals are only permitted for contacts who have email.")
            else:
                max_phones_by_budget = available_for_reveals // 15
                phones_allowed = min(emails_allowed, max_phones_by_budget)
                phone_cost = phones_allowed * 15
                available_for_reveals -= phone_cost
                if phones_allowed < emails_allowed:
                    notes.append(
                        f"Only {phones_allowed} of {emails_allowed} email-revealed contacts can receive phone reveals within safe reserve."
                    )
        else:
            notes.append("Phone reveals disabled by configuration (ENABLE_PHONE_REVEAL=False).")

        total_estimated_cost = base_cost + email_cost + phone_cost
        balance_after_run = remaining_balance - total_estimated_cost
        can_proceed = balance_after_run >= safety_reserve

        phone_word = "phone" if phones_allowed == 1 else "phones"
        email_word = "email" if emails_allowed == 1 else "emails"

        plan_summary = (
            f"{emails_allowed} {email_word} ({email_cost}) + "
            f"{phones_allowed} {phone_word} ({phone_cost}) + "
            f"base ({base_cost}) = {total_estimated_cost} of {remaining_balance}"
        )

        return RevealPlan(
            remaining_balance=remaining_balance,
            target_contacts=target_contacts,
            enrich_company=enrich_company,
            base_cost=base_cost,
            emails_allowed=emails_allowed,
            email_cost=email_cost,
            phones_allowed=phones_allowed,
            phone_cost=phone_cost,
            total_estimated_cost=total_estimated_cost,
            balance_after_run=balance_after_run,
            safety_reserve=safety_reserve,
            plan_summary=plan_summary,
            can_proceed=can_proceed,
            notes=notes,
        )

    def check_and_deduct(
        self,
        operation: str,
        target: str,
        credits_needed: int,
        run_id: str | None = None,
        is_cache_hit: bool = False,
    ) -> int:
        """Validate credit capacity and record credit transaction in the database.
        
        If is_cache_hit is True, credits_needed is set to 0 and 0 credits are spent,
        ensuring cached operations never deduct credits even in LIVE mode.
        """
        if is_cache_hit:
            credits_needed = 0

        actual_spend = 0 if self.dry_run else credits_needed

        with SessionLocal() as db:
            if not self.dry_run and not is_cache_hit and actual_spend > 0:
                total_real_spent = (
                    db.query(func.coalesce(func.sum(CreditUsage.credits_spent), 0))
                    .filter(CreditUsage.is_mock == False)
                    .scalar()
                )
                hard_cap = 50
                if (total_real_spent + actual_spend) > hard_cap:
                    msg = (
                        f"Hard credit cap (50 credits) would be exceeded! "
                        f"Total spent so far: {total_real_spent}, required: {actual_spend}, cap: {hard_cap}"
                    )
                    logger.error(msg)
                    raise CreditLimitExceededError(msg)

            if run_id and not is_cache_hit:
                # Check credits spent in current run
                run_spent = (
                    db.query(func.coalesce(func.sum(CreditUsage.credits_spent), 0))
                    .filter(CreditUsage.run_id == run_id, CreditUsage.is_mock == False)
                    .scalar()
                )
                if (run_spent + actual_spend) > self.max_credits_per_run:
                    msg = (
                        f"Credit limit exceeded for run {run_id}! "
                        f"Current spent: {run_spent}, Required: {actual_spend}, Max: {self.max_credits_per_run}"
                    )
                    logger.error(msg)
                    raise CreditLimitExceededError(msg)

            # Record entry in ledger
            op_label = f"{operation} (cache_hit)" if is_cache_hit else operation
            record = CreditUsage(
                operation=op_label,
                target=target,
                credits_spent=actual_spend,
                is_mock=self.dry_run,
                run_id=run_id or str(uuid.uuid4()),
            )
            db.add(record)
            db.commit()

        logger.info(
            "CreditGuard [%s]: operation='%s', target='%s', credits=%d (mock=%s, cache_hit=%s)",
            run_id[:8] if run_id else "global",
            operation,
            target,
            actual_spend,
            self.dry_run,
            is_cache_hit,
        )
        return actual_spend

    @staticmethod
    def get_ledger_summary() -> dict[str, Any]:
        """Aggregate all credit expenditures recorded in SQLite."""
        with SessionLocal() as db:
            total_real = (
                db.query(func.coalesce(func.sum(CreditUsage.credits_spent), 0))
                .filter(CreditUsage.is_mock == False)
                .scalar()
            )
            total_mock_events = (
                db.query(func.count(CreditUsage.id))
                .filter(CreditUsage.is_mock == True)
                .scalar()
            )
            recent_entries = (
                db.query(CreditUsage)
                .order_by(CreditUsage.created_at.desc())
                .limit(10)
                .all()
            )

        # Default trial allocation from Forager is 50 credits
        trial_budget = 50
        remaining = max(0, trial_budget - total_real)

        return {
            "trial_budget": trial_budget,
            "total_real_credits_used": total_real,
            "credits_remaining": remaining,
            "mock_operations_count": total_mock_events,
            "recent_usage": [
                {
                    "operation": r.operation,
                    "target": r.target,
                    "credits": r.credits_spent,
                    "is_mock": r.is_mock,
                    "timestamp": r.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                }
                for r in recent_entries
            ],
        }
