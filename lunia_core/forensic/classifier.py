"""Forensic Failure Classifier

Assigns forensic tags to accounting failures for root cause analysis.
PHASE 0 ONLY - No enforcement, observation only.
"""

class ForensicTag:
    """Primary forensic failure tags"""
    # Unit/Notional Bugs
    QTY_NOTIONAL_MISMATCH = "QTY_NOTIONAL_MISMATCH"
    PRICE_SCALE_MISMATCH = "PRICE_SCALE_MISMATCH"
    
    # Accounting Sign Errors
    FEE_SIGN_ERROR = "FEE_SIGN_ERROR"
    CASH_SIGN_ERROR = "CASH_SIGN_ERROR"
    
    # Constraint Violations
    OVERSEND_CASH = "OVERSEND_CASH"
    OVERSELL_POSITION = "OVERSELL_POSITION"
    
    # Semantic Mismatches
    SYMBOL_DECIMAL_MISMATCH = "SYMBOL_DECIMAL_MISMATCH"
    EXCHANGE_SEMANTICS_MISMATCH = "EXCHANGE_SEMANTICS_MISMATCH"
    
    # Secondary (optional)
    DOUBLE_COUNT = "DOUBLE_COUNT"
    MISSING_FILL = "MISSING_FILL"
    STATE_DESYNC = "STATE_DESYNC"
    PRICE_SOURCE_CORRUPTION = "PRICE_SOURCE_CORRUPTION"
    
    # Unexplained
    UNEXPLAINED_DELTA = "UNEXPLAINED_DELTA"

def classify_failure(failure_type: str, context: dict) -> dict:
    """
    Classify an accounting failure and return forensic metadata.
    
    Args:
        failure_type: High-level failure category
        context: Dict with failure details
        
    Returns:
        Dict with primary_tag, secondary_tags, severity, explanation
    """
    result = {
        "primary_tag": ForensicTag.UNEXPLAINED_DELTA,
        "secondary_tags": [],
        "severity": "CRITICAL",
        "explanation": "",
        "context": context
    }
    
    # Classify based on failure type
    if failure_type == "equity_collapse":
        delta_pct = context.get("delta_pct", 0)
        if delta_pct < -0.5:  # >50% loss
            if context.get("flash_crash", False):
                result["primary_tag"] = "MARKET_EVENT"
                result["severity"] = "INFO"
            else:
                result["primary_tag"] = ForensicTag.QTY_NOTIONAL_MISMATCH
                result["explanation"] = "Massive equity loss without market event suggests unit/notional bug"
    
    elif failure_type == "conservation_violation":
        expected = context.get("expected_delta", 0)
        actual = context.get("actual_delta", 0)
        diff = abs(actual - expected)
        
        if diff > abs(expected) * 10:  # 10x worse than expected
            result["primary_tag"] = ForensicTag.QTY_NOTIONAL_MISMATCH
        elif context.get("fee_amount", 0) < 0:
            result["primary_tag"] = ForensicTag.FEE_SIGN_ERROR
        else:
            result["primary_tag"] = ForensicTag.UNEXPLAINED_DELTA
    
    elif failure_type == "overspend":
        result["primary_tag"] = ForensicTag.OVERSEND_CASH
        result["explanation"] = f"Attempted to spend {context.get('attempted')} with only {context.get('available')} available"
    
    elif failure_type == "oversell":
        result["primary_tag"] = ForensicTag.OVERSELL_POSITION
        result["explanation"] = f"Attempted to sell {context.get('attempted')} with only {context.get('available')} held"
    
    return result
