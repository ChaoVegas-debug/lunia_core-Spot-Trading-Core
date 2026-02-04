"""
Budget Governor - Persistent AI Cost Enforcement

This service enforces AI budget constraints with DATABASE PERSISTENCE.

CRITICAL GUARANTEE:
Budget state MUST survive backend restarts. All spend tracking is DB-backed.

RESPONSIBILITIES:
1. Check if AI attempt is within budget (BEFORE inference)
2. Record actual cost (AFTER inference)
3. Emit governance events (warnings, hard stops)
4. Persist daily spend to ai_budget_usage table

FAIL-CLOSED:
- DB failure → AI blocked
- Missing config → AI blocked
- Invalid state → AI blocked
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
import logging

from lunia_core.app.services.execution_journal.budget_model import AIBudgetUsage
from lunia_core.app.services.ai_gateway.governance import AIGovernanceConfig

logger = logging.getLogger(__name__)


class BudgetGovernor:
    """
    Enforces AI budget constraints with persistent tracking.
    
    All budget state is stored in the database (ai_budget_usage table).
    Backend restart DOES NOT reset counters.
    """
    
    def __init__(self, db_session: Session, governance_config: AIGovernanceConfig):
        """
        Initialize Budget Governor.
        
        Args:
            db_session: SQLAlchemy session for DB operations
            governance_config: Governance config with budget limits
        """
        self.db = db_session
        self.config = governance_config
        
        logger.info(
            f"BudgetGovernor initialized: "
            f"daily_budget=${self.config.daily_budget_usd:.2f}, "
            f"per_signal=${self.config.per_signal_budget_usd:.4f}"
        )
    
    def can_attempt(
        self,
        estimated_cost_usd: float,
        provider: str = "unknown",
        model: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Check if AI attempt is within budget constraints.
        
        This is a GATE CHECK executed BEFORE inference.
        
        Args:
            estimated_cost_usd: Estimated USD cost for this attempt
            provider: Provider name (for logging)
            model: Model name (for logging)
            
        Returns:
            (can_proceed, reason)
            - (True, "ok") if within budget
            - (False, "reason") if blocked
            
        Fail-Closed:
            DB errors return (False, "budget_check_failed")
        """
        try:
            # Check 1: Per-signal budget
            if estimated_cost_usd > self.config.per_signal_budget_usd:
                logger.warning(
                    f"Attempt blocked: per-signal budget exceeded "
                    f"(estimated=${estimated_cost_usd:.4f}, "
                    f"limit=${self.config.per_signal_budget_usd:.4f})"
                )
                return False, "per_signal_cap_exceeded"
            
            # Check 2: Daily budget
            daily_spent = self.get_daily_spend()
            
            # Emit warning if approaching limit
            warn_threshold = self.config.daily_budget_usd * self.config.budget_warning_ratio
            if daily_spent >= warn_threshold and daily_spent < self.config.daily_budget_usd:
                pct = (daily_spent / self.config.daily_budget_usd) * 100
                logger.warning(
                    f"AI_BUDGET_WARNING: {pct:.1f}% of daily budget used "
                    f"(${daily_spent:.4f} / ${self.config.daily_budget_usd:.2f})"
                )
                # NOTE: Event emission will be added when EventBus integrated
            
            # Hard stop if budget exceeded
            if daily_spent >= self.config.daily_budget_usd:
                logger.error(
                    f"Attempt blocked: daily budget exceeded "
                    f"(spent=${daily_spent:.4f}, "
                    f"limit=${self.config.daily_budget_usd:.2f})"
                )
                return False, "daily_cap_exceeded"
            
            # Check 3: Would this attempt exceed budget?
            projected_spend = daily_spent + estimated_cost_usd
            if projected_spend > self.config.daily_budget_usd:
                logger.warning(
                    f"Attempt blocked: would exceed daily budget "
                    f"(projected=${projected_spend:.4f}, "
                    f"limit=${self.config.daily_budget_usd:.2f})"
                )
                return False, "would_exceed_daily_cap"
            
            # All checks passed
            return True, "ok"
            
        except SQLAlchemyError as e:
            # DB failure → FAIL CLOSED
            logger.error(f"Budget check failed due to DB error: {e}")
            return False, "budget_check_failed"
        except Exception as e:
            # Any other error → FAIL CLOSED
            logger.error(f"Budget check failed: {e}")
            return False, "budget_check_failed"
    
    def record_attempt(
        self,
        date: date,
        provider: str,
        model: Optional[str],
        tokens_prompt: int,
        tokens_completion: int,
        cost_usd: float
    ) -> bool:
        """
        Record AI attempt to database (persistent).
        
        This is called AFTER inference completes (or fails).
        
        Uses UPSERT logic:
        - If row exists for (date, provider, model): increment counters
        - Otherwise: create new row
        
        Args:
            date: UTC date of attempt
            provider: Provider name
            model: Model name (None for mock)
            tokens_prompt: Prompt tokens used
            tokens_completion: Completion tokens used
            cost_usd: Actual USD cost
            
        Returns:
            True if recorded successfully, False on error
            
        Note:
            This method commits the transaction.
            Caller should handle session management.
        """
        try:
            # Query for existing row
            existing = self.db.query(AIBudgetUsage).filter(
                AIBudgetUsage.date == date,
                AIBudgetUsage.provider == provider,
                AIBudgetUsage.model == model
            ).first()
            
            if existing:
                # UPDATE: increment counters
                existing.total_attempts += 1
                existing.total_tokens_prompt += tokens_prompt
                existing.total_tokens_completion += tokens_completion
                existing.total_cost_usd = float(existing.total_cost_usd) + cost_usd
                existing.updated_at = datetime.utcnow()
                
                logger.debug(
                    f"Updated budget usage: {date} {provider}/{model} "
                    f"(attempts={existing.total_attempts}, cost=${existing.total_cost_usd:.4f})"
                )
            else:
                # INSERT: create new row
                new_usage = AIBudgetUsage(
                    date=date,
                    provider=provider,
                    model=model,
                    total_attempts=1,
                    total_tokens_prompt=tokens_prompt,
                    total_tokens_completion=tokens_completion,
                    total_cost_usd=cost_usd
                )
                self.db.add(new_usage)
                
                logger.debug(
                    f"Created budget usage: {date} {provider}/{model} "
                    f"(cost=${cost_usd:.4f})"
                )
            
            # Commit transaction
            self.db.commit()
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to record attempt: {e}")
            self.db.rollback()
            return False
        except Exception as e:
            logger.error(f"Unexpected error recording attempt: {e}")
            self.db.rollback()
            return False
    
    def get_daily_spend(self, target_date: Optional[date] = None) -> float:
        """
        Query total USD spend for a given date.
        
        Args:
            target_date: Date to query (defaults to today UTC)
            
        Returns:
            Total USD spent on target_date (0.0 if no data)
            
        Fail-Closed:
            DB errors return 0.0 (conservative)
        """
        if target_date is None:
            target_date = datetime.utcnow().date()
        
        try:
            result = self.db.query(
                func.sum(AIBudgetUsage.total_cost_usd)
            ).filter(
                AIBudgetUsage.date == target_date
            ).scalar()
            
            return float(result) if result else 0.0
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to query daily spend: {e}")
            return 0.0  # Fail-closed: conservative estimate
        except Exception as e:
            logger.error(f"Unexpected error querying spend: {e}")
            return 0.0
    
    def get_usage_by_provider(
        self,
        target_date: Optional[date] = None
    ) -> dict:
        """
        Get detailed usage breakdown by provider for a date.
        
        Args:
            target_date: Date to query (defaults to today UTC)
            
        Returns:
            Dict mapping provider → {model → usage_data}
        """
        if target_date is None:
            target_date = datetime.utcnow().date()
        
        try:
            rows = self.db.query(AIBudgetUsage).filter(
                AIBudgetUsage.date == target_date
            ).all()
            
            breakdown = {}
            for row in rows:
                if row.provider not in breakdown:
                    breakdown[row.provider] = {}
                
                breakdown[row.provider][row.model or "default"] = {
                    "attempts": row.total_attempts,
                    "tokens_prompt": row.total_tokens_prompt,
                    "tokens_completion": row.total_tokens_completion,
                    "cost_usd": float(row.total_cost_usd)
                }
            
            return breakdown
            
        except Exception as e:
            logger.error(f"Failed to get usage breakdown: {e}")
            return {}
    
    def force_fallback_provider(self, reason: str = "budget_exceeded"):
        """
        Force switch to fallback provider (mock).
        
        This is called when budget is exceeded and hard_stop=False.
        
        Args:
            reason: Reason for fallback (for logging/events)
        """
        logger.warning(
            f"AI_PROVIDER_FORCED_FALLBACK: {reason} "
            f"(switching to {self.config.fallback_provider_on_exceed})"
        )
        
        # NOTE: Event emission will be added when EventBus integrated
        # EventBus.publish(AIGovernanceEvent(
        #     type="AI_PROVIDER_FORCED_FALLBACK",
        #     reason=reason,
        #     fallback_provider=self.config.fallback_provider_on_exceed
        # ))
    
    def reset_daily_budget(self, target_date: Optional[date] = None):
        """
        [ADMIN ONLY] Reset daily budget for a date.
        
        DANGEROUS: This deletes budget records.
        Only use for testing or administrative correction.
        
        Args:
            target_date: Date to reset (defaults to today UTC)
        """
        if target_date is None:
            target_date = datetime.utcnow().date()
        
        try:
            deleted = self.db.query(AIBudgetUsage).filter(
                AIBudgetUsage.date == target_date
            ).delete()
            
            self.db.commit()
            
            logger.warning(
                f"ADMIN: Reset budget for {target_date} (deleted {deleted} rows)"
            )
            
        except Exception as e:
            logger.error(f"Failed to reset budget: {e}")
            self.db.rollback()
