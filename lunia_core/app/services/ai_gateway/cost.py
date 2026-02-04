"""
AI Gateway: Cost Estimation

Pricing tables and cost estimation for LLM providers.

Pricing as of February 2026 (OpenAI).
Source: https://openai.com/pricing

CRITICAL: Cost estimation feeds BudgetGovernor pre-call checks.
Unknown models are treated as EXPENSIVE (fail-closed bias).
"""

import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


# Pricing tables (USD per 1 million tokens)
# Updated: February 2026
MODEL_PRICING = {
    # GPT-4o models (latest, recommended)
    "gpt-4o": {
        "input": 2.50,   # $2.50 per 1M input tokens
        "output": 10.00,  # $10.00 per 1M output tokens
    },
    "gpt-4o-mini": {
        "input": 0.15,   # $0.15 per 1M input tokens
        "output": 0.60,  # $0.60 per 1M output tokens
    },
    
    # GPT-4 Turbo
    "gpt-4-turbo": {
        "input": 10.00,
        "output": 30.00,
    },
    "gpt-4-turbo-2024-04-09": {
        "input": 10.00,
        "output": 30.00,
    },
    
    # GPT-4 (legacy, expensive)
    "gpt-4": {
        "input": 30.00,
        "output": 60.00,
    },
    "gpt-4-0613": {
        "input": 30.00,
        "output": 60.00,
    },
    
    # GPT-3.5 Turbo (cheap but older)
    "gpt-3.5-turbo": {
        "input": 0.50,
        "output": 1.50,
    },
    "gpt-3.5-turbo-0125": {
        "input": 0.50,
        "output": 1.50,
    },
}

# Default pricing for unknown models (EXPENSIVE, fail-closed bias)
DEFAULT_PRICING = {
    "input": 10.00,   # Assume GPT-4 Turbo pricing
    "output": 30.00,
}


def get_model_pricing(model: str) -> Tuple[float, float]:
    """
    Get (input_price_per_1m, output_price_per_1m) for model.
    
    If model is unknown, returns DEFAULT_PRICING (expensive, fail-closed).
    
    Args:
        model: Model name (e.g., "gpt-4o-mini", "gpt-4-turbo")
    
    Returns:
        (input_usd_per_1m_tokens, output_usd_per_1m_tokens)
    
    Examples:
        >>> get_model_pricing("gpt-4o-mini")
        (0.15, 0.60)
        
        >>> get_model_pricing("unknown-model")
        (10.00, 30.00)  # Default (expensive)
    """
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
    
    if model not in MODEL_PRICING:
        logger.warning(
            f"Unknown model '{model}', using default pricing "
            f"(${DEFAULT_PRICING['input']:.2f}/${DEFAULT_PRICING['output']:.2f} per 1M). "
            "This may trigger per-signal budget cap."
        )
    
    return pricing["input"], pricing["output"]


def estimate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int
) -> float:
    """
    Estimate USD cost for inference.
    
    Args:
        model: Model name
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
    
    Returns:
        Estimated cost in USD
    
    Examples:
        >>> estimate_cost("gpt-4o-mini", 1000, 500)
        0.00045  # (1000/1e6 * 0.15) + (500/1e6 * 0.60)
        
        >>> estimate_cost("gpt-4-turbo", 1000, 500)
        0.025  # (1000/1e6 * 10.0) + (500/1e6 * 30.0)
    """
    input_price, output_price = get_model_pricing(model)
    
    # Calculate costs
    cost_input = (prompt_tokens / 1_000_000) * input_price
    cost_output = (completion_tokens / 1_000_000) * output_price
    
    total_cost = cost_input + cost_output
    
    return total_cost


def get_recommended_model(budget_usd: float, estimated_tokens: int) -> str:
    """
    Recommend cheapest model that fits budget.
    
    Args:
        budget_usd: Available budget in USD
        estimated_tokens: Estimated total tokens (prompt + completion)
    
    Returns:
        Recommended model name
    
    Example:
        >>> get_recommended_model(0.01, 2000)
        "gpt-4o-mini"  # Cheapest model
    """
    # Try cheapest first
    models_by_cost = [
        "gpt-4o-mini",     # Cheapest
        "gpt-3.5-turbo",
        "gpt-4o",
        "gpt-4-turbo",
        "gpt-4",           # Most expensive
    ]
    
    for model in models_by_cost:
        # Rough estimate: assume 50/50 split prompt/completion
        est_cost = estimate_cost(model, estimated_tokens // 2, estimated_tokens // 2)
        
        if est_cost <= budget_usd:
            return model
    
    # If nothing fits budget, return cheapest anyway
    logger.warning(
        f"No model fits budget ${budget_usd:.4f} for {estimated_tokens} tokens, "
        "recommending cheapest (gpt-4o-mini)"
    )
    return "gpt-4o-mini"


def format_cost(cost_usd: float) -> str:
    """
    Format cost for logging/display.
    
    Args:
        cost_usd: Cost in USD
    
    Returns:
        Formatted string (e.g., "$0.0012", "$0.00", "$1.23")
    
    Examples:
        >>> format_cost(0.001234)
        "$0.0012"
        
        >>> format_cost(0.0)
        "$0.00"
    """
    return f"${cost_usd:.4f}"


# Export public API
__all__ = [
    "get_model_pricing",
    "estimate_cost",
    "get_recommended_model",
    "format_cost",
    "MODEL_PRICING",
    "DEFAULT_PRICING",
]
