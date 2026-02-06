"""
Epoch 9.1: Deterministic Conflict Detection

Pure function for classifying conflicts between core strategy decisions and AI interpretations.

Architecture:
- classify_conflict(): Main entry point (pure, deterministic)
- Severity escalation based on market conditions
- Reason code classification based on AI reasoning text

Invariants:
- No side effects (pure function)
- Deterministic output for given inputs
- No database or network calls
"""
from typing import Dict, Any, Tuple, Optional

from .governance import ConflictReasonCode, ConflictSeverity


def classify_conflict(
    core_decision: bool,
    ai_decision: bool,
    market_state: Optional[Dict[str, Any]],
    core_reasoning: str,
    ai_reasoning: str
) -> Tuple[ConflictReasonCode, ConflictSeverity, str]:
    """
    Pure, deterministic conflict classification between core and AI.
    
    Logic:
    1. If decisions agree → NO_CONFLICT
    2. If disagree → classify reason based on AI reasoning keywords
    3. Escalate severity based on market conditions:
       - DANGEROUS market → HIGH severity
       - RISKY market or HIGH volatility → MEDIUM severity
       - Otherwise → LOW severity
    
    Args:
        core_decision: Core strategy decision (True = execute, False = no signal)
        ai_decision: AI recommendation (True = recommend execute, False = recommend skip)
        market_state: Current market enrichment state (may be None)
        core_reasoning: Strategy's deterministic explanation
        ai_reasoning: AI's explanation/interpretation
    
    Returns:
        Tuple of (reason_code, severity, explanation)
    
    Examples:
        >>> classify_conflict(
        ...     core_decision=True,
        ...     ai_decision=True,
        ...     market_state={"market_risk_flag": "SAFE"},
        ...     core_reasoning="Buy signal: momentum > threshold",
        ...     ai_reasoning="Agree with buy signal"
        ... )
        (ConflictReasonCode.NO_CONFLICT, ConflictSeverity.NONE, "Core and AI agree")
        
        >>> classify_conflict(
        ...     core_decision=True,
        ...     ai_decision=False,
        ...     market_state={"market_risk_flag": "DANGEROUS", "volatility": {"vol_regime": "HIGH"}},
        ...     core_reasoning="Buy signal",
        ...     ai_reasoning="Market regime suggests high risk"
        ... )
        (ConflictReasonCode.RISK_MISMATCH, ConflictSeverity.HIGH, "...")
    """
    # No conflict if decisions agree
    if core_decision == ai_decision:
        return (
            ConflictReasonCode.NO_CONFLICT,
            ConflictSeverity.NONE,
            "Core and AI agree"
        )
    
    # Disagreement exists — classify
    
    # Extract market conditions (safe defaults)
    market_risk = "UNKNOWN"
    volatility_regime = "UNKNOWN"
    regime = "UNKNOWN"
    
    if market_state:
        market_risk = market_state.get("market_risk_flag", "UNKNOWN")
        volatility_dict = market_state.get("volatility", {})
        if isinstance(volatility_dict, dict):
            volatility_regime = volatility_dict.get("vol_regime", "UNKNOWN")
        regime_dict = market_state.get("regime", {})
        if isinstance(regime_dict, dict):
            regime = regime_dict.get("regime", "UNKNOWN")
    
    # Severity escalation rules
    severity = ConflictSeverity.LOW  # Default
    
    if market_risk == "DANGEROUS":
        severity = ConflictSeverity.HIGH
    elif market_risk == "RISKY" or volatility_regime == "HIGH":
        severity = ConflictSeverity.MEDIUM
    
    # Reason code classification (keyword-based heuristic)
    ai_reasoning_lower = ai_reasoning.lower()
    
    if any(keyword in ai_reasoning_lower for keyword in ["regime", "trend", "ranging", "breakout"]):
        reason = ConflictReasonCode.REGIME_MISMATCH
    elif any(keyword in ai_reasoning_lower for keyword in ["risk", "dangerous", "risky"]):
        reason = ConflictReasonCode.RISK_MISMATCH
    elif any(keyword in ai_reasoning_lower for keyword in ["liquidity", "spread", "depth", "slippage"]):
        reason = ConflictReasonCode.LIQUIDITY_WARNING
    elif any(keyword in ai_reasoning_lower for keyword in ["volatility", "atr", "volatile"]):
        reason = ConflictReasonCode.VOLATILITY_CONCERN
    else:
        reason = ConflictReasonCode.OTHER
    
    # Build explanation (truncate for DB storage)
    core_snippet = core_reasoning[:100] if core_reasoning else "N/A"
    ai_snippet = ai_reasoning[:100] if ai_reasoning else "N/A"
    
    explanation = (
        f"CONFLICT: Core={'execute' if core_decision else 'skip'}, "
        f"AI={'execute' if ai_decision else 'skip'} | "
        f"Market: {market_risk}/{volatility_regime}/{regime} | "
        f"Core: {core_snippet}... | AI: {ai_snippet}..."
    )
    
    return (reason, severity, explanation)


def extract_conflict_keywords(text: str) -> set:
    """
    Extract conflict-related keywords from reasoning text.
    
    Helper function for debugging and analysis.
    
    Args:
        text: Reasoning text (core or AI)
    
    Returns:
        Set of detected keywords
    """
    keywords = {
        "regime", "trend", "ranging", "breakout",
        "risk", "dangerous", "risky", "safe",
        "liquidity", "spread", "depth", "slippage",
        "volatility", "atr", "volatile"
    }
    
    text_lower = text.lower()
    return {kw for kw in keywords if kw in text_lower}
