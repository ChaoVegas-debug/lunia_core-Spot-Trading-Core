"""
PHASE 11B — GENOME DSL: Complexity Tax Calculation

Implements Constitution Section 3.5:
- Formula: Σ(weight × 1.1^depth)
- Hard cap: 30.0
- Governance mapping: AUTO/COMMITTEE/EXEC

Exponential penalty discourages deep nesting.
"""

from typing import Any, Dict
from extensions.genome_dsl import types


# ────────────────────────────────────────────────────────────────────────────────
# NODE WEIGHTS (from Constitution Section 3.3)
# ────────────────────────────────────────────────────────────────────────────────

NODE_WEIGHTS: Dict[str, float] = {
    # Literals
    "ConstFloat": 0.5,
    "ConstInt": 0.5,
    "ConstBool": 0.5,
    "ConstString": 0.5,
    
    # Market Data (Sensors)
    "PriceMid": 1.0,
    "PriceBid": 1.0,
    "PriceAsk": 1.0,
    "SpreadPct": 1.0,
    "Volume": 1.0,
    "VolatilityState": 1.0,
    
    # Indicators
    "SMA": 2.0,
    "EMA": 2.0,
    "RSI": 3.0,
    "ATR": 3.0,
    "Highest": 2.0,
    "Lowest": 2.0,
    "ROC": 2.5,
    
    # Comparators
    "GreaterThan": 1.0,
    "LessThan": 1.0,
    "Equal": 1.0,
    "CrossAbove": 2.0,
    "CrossBelow": 2.0,
    
    # Boolean Logic
    "And": 1.0,
    "Or": 1.0,
    "Not": 0.5,
    "IfThenElse": 2.0,
    
    # Gates & Filters
    "RegimeFilter": 3.0,
    "CostGate": 5.0,  # Mandatory, high weight
    "TimeWindow": 2.0,
    
    # Actions
    "SignalEntry": 2.0,
    "SignalExit": 2.0,
    "SizingFixed": 1.5,
    "SizingATRBased": 3.0,
    
    # Root (not counted in complexity)
    "StrategyGenome": 0.0,
    "ExitPlanNode": 0.0,
}


# Constants
COMPLEXITY_CAP = 30.0
DEPTH_MULTIPLIER = 1.1


# ────────────────────────────────────────────────────────────────────────────────
# COMPLEXITY CALCULATION
# ────────────────────────────────────────────────────────────────────────────────

def calculate_complexity(genome: types.StrategyGenome) -> float:
    """
    Calculate complexity score per Constitution formula.
    
    Formula: Σ(weight × 1.1^depth)
    
    Args:
        genome: Strategy genome
    
    Returns:
        Complexity score (0.0 to infinity, cap enforced separately)
    """
    total_score = 0.0
    
    def traverse(node: Any, depth: int):
        nonlocal total_score
        
        if node is None:
            return
        
        node_type = type(node).__name__
        weight = NODE_WEIGHTS.get(node_type, 1.0)  # Default 1.0 if unknown
        
        # Add weighted score with exponential depth penalty
        node_score = weight * (DEPTH_MULTIPLIER ** depth)
        total_score += node_score
        
        # Recursively traverse children
        if hasattr(node, '__dict__'):
            for field_name, field_value in node.__dict__.items():
                if field_name in ['metadata', 'exit_plan', 'return_type']:
                    continue  # Skip metadata fields
                
                if isinstance(field_value, list):
                    for item in field_value:
                        traverse(item, depth + 1)
                elif hasattr(field_value, '__dict__'):
                    traverse(field_value, depth + 1)
    
    # Calculate for all three trees
    traverse(genome.entry_condition, 0)
    traverse(genome.exit_condition, 0)
    traverse(genome.sizing_logic, 0)
    
    return round(total_score, 2)


def enforce_complexity_cap(score: float) -> bool:
    """
    Check if complexity score is within cap.
    
    Args:
        score: Calculated complexity score
    
    Returns:
        True if within cap (≤30.0), False if exceeds
    """
    return score <= COMPLEXITY_CAP


def get_governance_level(score: float) -> str:
    """
    Map complexity score to governance level per Constitution Section 3.5.
    
    Args:
        score: Complexity score
    
    Returns:
        "AUTO" | "COMMITTEE" | "EXEC" | "REJECTED"
    """
    if score > COMPLEXITY_CAP:
        return "REJECTED"
    elif score >= 20.0:
        return "EXEC"  # Senior approval required
    elif score >= 10.0:
        return "COMMITTEE"  # Multi-reviewer
    else:
        return "AUTO"  # No human review
