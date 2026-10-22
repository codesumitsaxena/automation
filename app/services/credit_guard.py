"""Credit guardrail management, budget limits, and credit expenditure tracking."""

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


class CreditGuard:
    """Enforces credit budgets, estimates costs, and records credit transactions."""

    def __init__(self, max_credits_per_run: int | None = None):
        self.max_credits_per_run = max_credits_per_run or settings.max_credits_per_run
        self.dry_run = settings.dry_run

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
            "dry_run": settings.dry_run,
            "real_cost_if_dry_run": 0 if settings.dry_run else total,
        }

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
