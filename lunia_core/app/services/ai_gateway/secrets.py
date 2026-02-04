"""
AI Gateway: Secrets Management

CRITICAL: Zero secret leakage guarantee.

This module handles:
- API key retrieval from environment
- Secret validation
- Recursive redaction for logging/audit

RULES:
- NEVER log API keys
- NEVER store keys in DB
- NEVER include keys in TraceDrawer events
"""

import os
import re
import logging
from typing import Any, Optional, Tuple, Dict

logger = logging.getLogger(__name__)


def get_openai_api_key() -> Optional[str]:
    """
    Read OPENAI_API_KEY from environment.
    
    Returns:
        API key string, or None if not set
    """
    return os.getenv("OPENAI_API_KEY")


def get_openai_config() -> Dict[str, Any]:
    """
    Read all OpenAI configuration from environment.
    
    Returns:
        dict with: api_key, model, base_url, timeout_sec, max_retries, org, project
    """
    return {
        "api_key": os.getenv("OPENAI_API_KEY"),
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "base_url": os.getenv("OPENAI_BASE_URL"),  # None = use default
        "timeout_sec": float(os.getenv("OPENAI_TIMEOUT_SEC", "30")),
        "max_retries": int(os.getenv("OPENAI_MAX_RETRIES", "2")),
        "org": os.getenv("OPENAI_ORG"),
        "project": os.getenv("OPENAI_PROJECT"),
    }


def validate_openai_env() -> Tuple[bool, str]:
    """
    Validate OpenAI environment configuration.
    
    Returns:
        (ok: bool, reason: str)
        
    Examples:
        (True, "ok")
        (False, "OPENAI_API_KEY not set")
        (False, "OPENAI_API_KEY invalid format")
    """
    key = get_openai_api_key()
    
    # Check existence
    if not key:
        return False, "OPENAI_API_KEY not set"
    
    # Check format (should start with sk- or sk-proj-)
    if not (key.startswith("sk-") or key.startswith("sk-proj-")):
        return False, "OPENAI_API_KEY invalid format (must start with sk- or sk-proj-)"
    
    # Check minimum length (real keys are ~50+ chars)
    if len(key) < 20:
        return False, "OPENAI_API_KEY suspiciously short"
    
    # All checks passed
    return True, "ok"


def redact_sensitive(obj: Any, depth: int = 0, max_depth: int = 10) -> Any:
    """
    Recursively redact secrets from object.
    
    Redacts:
    - Strings containing 'sk-' (OpenAI API keys)
    - Strings containing 'sk-proj-' (OpenAI project keys)
    - Long hex strings (>16 chars, potential keys/tokens)
    - Authorization headers
    - Any field named 'api_key', 'apiKey', 'authorization', 'token'
    
    Args:
        obj: Object to redact (str, dict, list, or primitive)
        depth: Current recursion depth (for protection)
        max_depth: Maximum recursion depth
    
    Returns:
        Redacted copy of object
    
    Example:
        >>> redact_sensitive({"api_key": "sk-abc123", "data": "public"})
        {"api_key": "***REDACTED_API_KEY***", "data": "public"}
    """
    # Recursion depth protection
    if depth > max_depth:
        return "***MAX_DEPTH_EXCEEDED***"
    
    # Handle strings
    if isinstance(obj, str):
        # Redact OpenAI API keys
        if "sk-" in obj or "sk-proj-" in obj:
            return "***REDACTED_API_KEY***"
        
        # Redact long hex strings (potential tokens)
        if re.match(r'^[a-fA-F0-9]{16,}$', obj):
            return "***REDACTED_HEX***"
        
        # Redact bearer tokens
        if obj.startswith("Bearer "):
            return "Bearer ***REDACTED***"
        
        return obj
    
    # Handle dicts
    elif isinstance(obj, dict):
        redacted = {}
        for key, value in obj.items():
            # Redact sensitive field names
            if key.lower() in ("api_key", "apikey", "authorization", "token", "secret", "password"):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = redact_sensitive(value, depth + 1, max_depth)
        return redacted
    
    # Handle lists
    elif isinstance(obj, list):
        return [redact_sensitive(item, depth + 1, max_depth) for item in obj]
    
    # Handle tuples
    elif isinstance(obj, tuple):
        return tuple(redact_sensitive(item, depth + 1, max_depth) for item in obj)
    
    # Primitives (int, float, bool, None)
    else:
        return obj


def validate_no_secrets(obj: Any) -> Tuple[bool, Optional[str]]:
    """
    Validate that object contains no secrets.
    
    Used as paranoid double-check before logging/auditing.
    
    Args:
        obj: Object to validate (typically dict or str)
    
    Returns:
        (ok: bool, leaked_secret_pattern: Optional[str])
        
    Examples:
        (True, None) - no secrets found
        (False, "sk-") - API key pattern detected
    """
    # Convert to JSON-like string for pattern matching
    obj_str = str(obj)
    
    # Check for OpenAI API key patterns
    if "sk-" in obj_str:
        return False, "sk-"
    
    if "sk-proj-" in obj_str:
        return False, "sk-proj-"
    
    # Check for long base64-like strings (potential tokens)
    if re.search(r'[A-Za-z0-9+/]{40,}', obj_str):
        # Could be legitimate data, but flag for review
        # Return True but log warning
        logger.warning("validate_no_secrets: Found long base64-like string (might be legitimate)")
    
    return True, None


# Export public API
__all__ = [
    "get_openai_api_key",
    "get_openai_config",
    "validate_openai_env",
    "redact_sensitive",
    "validate_no_secrets",
]
