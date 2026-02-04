"""
AI Gateway: Token Estimation

Estimates token count for prompts and completions.

Uses tiktoken if available, otherwise falls back to heuristic estimation.

CRITICAL: Estimation MUST NOT crash - it feeds BudgetGovernor pre-call checks.
"""

import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Try to import tiktoken
TIKTOKEN_AVAILABLE = False
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
    logger.info("tiktoken available, using accurate token estimation")
except ImportError:
    logger.warning(
        "tiktoken not installed, using heuristic token estimation. "
        "Install with: pip install tiktoken"
    )


def estimate_tokens(text: str, model: str = "gpt-4o-mini") -> int:
    """
    Estimate token count for text.
    
    Uses tiktoken if available, otherwise heuristic (~4 chars/token).
    
    Args:
        text: Text to estimate tokens for
        model: Model name (for tiktoken encoding selection)
    
    Returns:
        Estimated token count (always >= 1)
    
    Examples:
        >>> estimate_tokens("Hello world")
        3  # with tiktoken
        
        >>> estimate_tokens("Hello world")  # without tiktoken
        3  # (11 chars / 4) + 1
    """
    if not text:
        return 1  # Minimum token count
    
    # Try tiktoken first
    if TIKTOKEN_AVAILABLE:
        try:
            # Get encoding for model
            encoding = tiktoken.encoding_for_model(model)
            tokens = len(encoding.encode(text))
            return max(1, tokens)
        except KeyError:
            # Model not found, fall back to cl100k_base (GPT-4 encoding)
            logger.debug(f"Model {model} not found in tiktoken, using cl100k_base")
            try:
                encoding = tiktoken.get_encoding("cl100k_base")
                tokens = len(encoding.encode(text))
                return max(1, tokens)
            except Exception as e:
                logger.warning(f"tiktoken encoding failed: {e}, using heuristic")
                # Fall through to heuristic
        except Exception as e:
            logger.warning(f"tiktoken failed: {e}, using heuristic")
            # Fall through to heuristic
    
    # Heuristic fallback: ~4 characters per token
    # This is conservative (slightly overestimates)
    tokens = len(text) // 4 + 1
    return max(1, tokens)


def estimate_prompt_and_completion(
    prompt: str,
    model: str = "gpt-4o-mini",
    max_completion_tokens: int = 400
) -> Tuple[int, int]:
    """
    Estimate (prompt_tokens, completion_tokens) for inference.
    
    Prompt tokens are estimated from actual prompt text.
    Completion tokens are set to max_completion_tokens (conservative).
    
    Args:
        prompt: Full prompt text (system + user)
        model: Model name
        max_completion_tokens: Maximum tokens for completion (default: 400)
    
    Returns:
        (estimated_prompt_tokens, estimated_completion_tokens)
    
    Example:
        >>> estimate_prompt_and_completion("Analyze this signal", max_completion_tokens=200)
        (4, 200)
    """
    prompt_tokens = estimate_tokens(prompt, model)
    completion_tokens = max_completion_tokens  # Conservative: assume max
    
    return prompt_tokens, completion_tokens


def get_estimation_mode() -> str:
    """
    Get current token estimation mode.
    
    Returns:
        "tiktoken" or "heuristic"
    """
    return "tiktoken" if TIKTOKEN_AVAILABLE else "heuristic"


# Export public API
__all__ = [
    "estimate_tokens",
    "estimate_prompt_and_completion",
    "get_estimation_mode",
    "TIKTOKEN_AVAILABLE",
]
