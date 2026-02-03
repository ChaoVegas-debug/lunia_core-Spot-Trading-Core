"""
PHASE 13B — VIRTUAL PORTFOLIO: Risk Monitor

Evaluates portfolio state and generates risk alerts.

CRITICAL RULES:
- Never throws exceptions (fail-closed to OK with internal error)
- Deterministic alert generation
- Compares drawdown_pct against thresholds
"""

from decimal import Decimal
from typing import List
from .models import PortfolioState, RiskAlert, RiskLevel


class RiskMonitor:
    """
    Risk monitor for portfolio state evaluation.
    
    Features:
    - Drawdown-based alerts (WARNING/CRITICAL)
    - Fail-closed (exceptions → OK with error details)
    - Deterministic thresholds
    """
    
    def __init__(
        self,
        warn_dd_pct: Decimal = Decimal("0.03"),
        crit_dd_pct: Decimal = Decimal("0.05"),
    ):
        """
        Initialize risk monitor.
        
        Args:
            warn_dd_pct: WARNING threshold (default 3%)
            crit_dd_pct: CRITICAL threshold (default 5%)
        """
        self.warn_dd_pct = warn_dd_pct
        self.crit_dd_pct = crit_dd_pct
    
    def evaluate(self, state: PortfolioState) -> List[RiskAlert]:
        """
        Evaluate portfolio state and generate risk alerts.
        
        Args:
            state: Current portfolio state
        
        Returns:
            List of RiskAlert (may be empty if OK)
        """
        try:
            alerts = []
            
            # Check drawdown
            dd_pct = state.drawdown_pct
            
            if dd_pct >= self.crit_dd_pct:
                alerts.append(RiskAlert(
                    ts_ms=state.ts_ms,
                    level="CRITICAL",
                    code="DRAWDOWN_CRITICAL",
                    message=f"Drawdown {dd_pct:.2%} >= {self.crit_dd_pct:.2%}",
                    details={
                        "drawdown_pct": str(dd_pct),
                        "threshold_pct": str(self.crit_dd_pct),
                        "drawdown_abs": str(state.drawdown_abs),
                    }
                ))
            elif dd_pct >= self.warn_dd_pct:
                alerts.append(RiskAlert(
                    ts_ms=state.ts_ms,
                    level="WARNING",
                    code="DRAWDOWN_WARNING",
                    message=f"Drawdown {dd_pct:.2%} >= {self.warn_dd_pct:.2%}",
                    details={
                        "drawdown_pct": str(dd_pct),
                        "threshold_pct": str(self.warn_dd_pct),
                        "drawdown_abs": str(state.drawdown_abs),
                    }
                ))
            else:
                # OK
                alerts.append(RiskAlert(
                    ts_ms=state.ts_ms,
                    level="OK",
                    code="PORTFOLIO_HEALTHY",
                    message="Portfolio within risk limits",
                    details={"drawdown_pct": str(dd_pct)}
                ))
            
            return alerts
        
        except Exception as e:
            # Fail-closed: return OK with internal error
            return [RiskAlert(
                ts_ms=state.ts_ms,
                level="OK",
                code="RISK_EVAL_ERROR",
                message=f"Risk evaluation failed: {str(e)[:100]}",
                details={"error": str(e)}
            )]
