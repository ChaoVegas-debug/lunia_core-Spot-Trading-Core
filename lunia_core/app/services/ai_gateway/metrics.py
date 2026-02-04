"""
AI Gateway: Observability Hooks

Provides visibility into AI budget usage without requiring full Grafana stack.

Phase 8.1A: Minimal metrics surface for budget monitoring.
Phase 8.3: Full Prometheus/Grafana integration (future).

CRITICAL: These functions query ai_budget_usage table directly.
Performance overhead is acceptable for Phase 8.1A (low query frequency).
"""

import logging
from typing import Dict, Optional, List
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..execution_journal.budget_model import AIBudgetUsage

logger = logging.getLogger(__name__)


def get_ai_budget_usage_today(db_session: Session) -> Dict[str, any]:
    """
    Get today's AI budget usage breakdown.
    
    Returns:
        dict with keys:
        - total_spend_usd: float
        - total_attempts: int
        - by_provider: dict[provider -> {attempts, tokens, cost}]
        - by_model: dict[model -> {attempts, tokens, cost}]
    
    Example:
        >>> usage = get_ai_budget_usage_today(session)
        >>> print(usage["total_spend_usd"])
        0.0123
        >>> print(usage["by_provider"]["openai"]["attempts"])
        45
    """
    try:
        today = date.today()
        
        # Query all usage records for today
        records = db_session.query(AIBudgetUsage).filter(
            AIBudgetUsage.date == today
        ).all()
        
        if not records:
            return {
                "total_spend_usd": 0.0,
                "total_attempts": 0,
                "by_provider": {},
                "by_model": {},
            }
        
        # Aggregate by provider
        by_provider = {}
        by_model = {}
        total_spend = 0.0
        total_attempts = 0
        
        for record in records:
            # By provider
            if record.provider not in by_provider:
                by_provider[record.provider] = {
                    "attempts": 0,
                    "tokens_prompt": 0,
                    "tokens_completion": 0,
                    "cost_usd": 0.0,
                }
            
            by_provider[record.provider]["attempts"] += record.total_attempts
            by_provider[record.provider]["tokens_prompt"] += record.total_tokens_prompt
            by_provider[record.provider]["tokens_completion"] += record.total_tokens_completion
            by_provider[record.provider]["cost_usd"] += record.total_cost_usd
            
            # By model
            model_key = f"{record.provider}:{record.model}" if record.model else record.provider
            if model_key not in by_model:
                by_model[model_key] = {
                    "attempts": 0,
                    "tokens_prompt": 0,
                    "tokens_completion": 0,
                    "cost_usd": 0.0,
                }
            
            by_model[model_key]["attempts"] += record.total_attempts
            by_model[model_key]["tokens_prompt"] += record.total_tokens_prompt
            by_model[model_key]["tokens_completion"] += record.total_tokens_completion
            by_model[model_key]["cost_usd"] += record.total_cost_usd
            
            # Totals
            total_spend += record.total_cost_usd
            total_attempts += record.total_attempts
        
        return {
            "total_spend_usd": round(total_spend, 6),
            "total_attempts": total_attempts,
            "by_provider": by_provider,
            "by_model": by_model,
        }
    
    except Exception as e:
        logger.error(f"Failed to get AI budget usage: {e}")
        return {
            "total_spend_usd": 0.0,
            "total_attempts": 0,
            "by_provider": {},
            "by_model": {},
            "error": str(e),
        }


def get_ai_budget_spend_today_usd(db_session: Session) -> float:
    """
    Get today's total AI spend in USD.
    
    Simpler version of get_ai_budget_usage_today for quick checks.
    
    Returns:
        Total spend in USD (0.0 on error, fail-closed)
    """
    try:
        today = date.today()
        
        result = db_session.query(
            func.sum(AIBudgetUsage.total_cost_usd)
        ).filter(
            AIBudgetUsage.date == today
        ).scalar()
        
        return round(result or 0.0, 6)
    
    except Exception as e:
        logger.error(f"Failed to get AI budget spend: {e}")
        return 0.0  # Fail-closed


def get_ai_budget_warning_state(
    db_session: Session,
    daily_budget_usd: float,
    warning_ratio: float = 0.8
) -> Dict[str, any]:
    """
    Check if AI budget is approaching daily cap.
    
    Args:
        db_session: Database session
        daily_budget_usd: Daily budget cap from governance config
        warning_ratio: Warn when spend exceeds this ratio (default: 0.8)
    
    Returns:
        dict with keys:
        - spend_usd: float (today's spend)
        - budget_usd: float (daily cap)
        - ratio_used: float (0.0 to 1.0+)
        - warning_triggered: bool (True if >= warning_ratio)
        - hard_stop_triggered: bool (True if >= 1.0)
    
    Example:
        >>> state = get_ai_budget_warning_state(session, 1.0, 0.8)
        >>> if state["warning_triggered"]:
        >>>     print("WARNING: AI budget at 80%")
    """
    spend_usd = get_ai_budget_spend_today_usd(db_session)
    
    ratio_used = spend_usd / daily_budget_usd if daily_budget_usd > 0 else 0.0
    
    return {
        "spend_usd": spend_usd,
        "budget_usd": daily_budget_usd,
        "ratio_used": round(ratio_used, 4),
        "warning_triggered": ratio_used >= warning_ratio,
        "hard_stop_triggered": ratio_used >= 1.0,
    }


def get_ai_budget_history(
    db_session: Session,
    days: int = 7
) -> List[Dict[str, any]]:
    """
    Get AI budget usage history for last N days.
    
    Args:
        db_session: Database session
        days: Number of days to look back (default: 7)
    
    Returns:
        List of dicts, one per day:
        - date: date
        - spend_usd: float
        - attempts: int
    
    Example:
        >>> history = get_ai_budget_history(session, days=7)
        >>> for day in history:
        >>>     print(f"{day['date']}: ${day['spend_usd']:.4f}")
    """
    try:
        # Query aggregated by date
        results = db_session.query(
            AIBudgetUsage.date,
            func.sum(AIBudgetUsage.total_cost_usd).label("spend_usd"),
            func.sum(AIBudgetUsage.total_attempts).label("attempts")
        ).group_by(
            AIBudgetUsage.date
        ).order_by(
            AIBudgetUsage.date.desc()
        ).limit(days).all()
        
        history = []
        for record in results:
            history.append({
                "date": record.date,
                "spend_usd": round(record.spend_usd or 0.0, 6),
                "attempts": record.attempts or 0,
            })
        
        return history
    
    except Exception as e:
        logger.error(f"Failed to get AI budget history: {e}")
        return []


# Future: Prometheus metrics (Phase 8.3)
# Placeholder for Prometheus integration
class PrometheusMetrics:
    """
    Placeholder for Prometheus metrics.
    
    Phase 8.3 will implement:
    - ai_budget_spend_usd (Gauge)
    - ai_budget_attempts_total (Counter)
    - ai_budget_blocked_total (Counter)
    - ai_provider_fallback_total (Counter)
    - ai_inference_latency_ms (Histogram)
    """
    
    def __init__(self):
        logger.info("PrometheusMetrics placeholder (not yet implemented)")
    
    def record_spend(self, provider: str, model: str, cost_usd: float):
        """Placeholder for recording spend metric."""
        pass
    
    def record_attempt(self, provider: str, model: str):
        """Placeholder for recording attempt counter."""
        pass
    
    def record_blocked(self, reason: str):
        """Placeholder for recording blocked counter."""
        pass


# Export public API
__all__ = [
    "get_ai_budget_usage_today",
    "get_ai_budget_spend_today_usd",
    "get_ai_budget_warning_state",
    "get_ai_budget_history",
    "PrometheusMetrics",
]
