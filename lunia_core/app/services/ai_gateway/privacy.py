"""
AI Gateway: Privacy Scrubber

Remove sensitive data from context before sending to LLM.

CRITICAL: Never send to external LLM:
- API keys
- Secrets
- Credentials
- Internal URLs
- Database connection strings
"""
import re
from typing import Any, Dict


# Patterns for sensitive data
SENSITIVE_PATTERNS = [
    (r'api[_-]?key', 'API_KEY'),
    (r'secret', 'SECRET'),
    (r'password', 'PASSWORD'),
    (r'token', 'TOKEN'),
    (r'credential', 'CREDENTIAL'),
    (r'bearer', 'BEARER'),
    (r'[a-zA-Z0-9]{32,}', 'HASH_OR_KEY'),  # Long alphanumeric strings
]


def scrub_dict(data: Dict[str, Any], depth: int = 0, max_depth: int = 10) -> Dict[str, Any]:
    """
    Recursively scrub sensitive data from dictionary.
    
    Args:
        data: Dictionary to scrub
        depth: Current recursion depth
        max_depth: Maximum recursion depth (prevent infinite loops)
    
    Returns:
        Scrubbed dictionary
    """
    if depth > max_depth:
        return {"error": "max_depth_exceeded"}
    
    scrubbed = {}
    for key, value in data.items():
        # Check if key itself is sensitive
        key_lower = key.lower()
        is_sensitive_key = any(
            re.search(pattern, key_lower)
            for pattern, _ in SENSITIVE_PATTERNS
        )
        
        if is_sensitive_key:
            scrubbed[key] = "[REDACTED]"
        elif isinstance(value, dict):
            scrubbed[key] = scrub_dict(value, depth + 1, max_depth)
        elif isinstance(value, list):
            scrubbed[key] = [
                scrub_dict(item, depth + 1, max_depth) if isinstance(item, dict) else item
                for item in value
            ]
        elif isinstance(value, str):
            # Check if value looks like sensitive data
            if len(value) > 20 and any(
                re.search(pattern, value.lower())
                for pattern, _ in SENSITIVE_PATTERNS
            ):
                scrubbed[key] = "[REDACTED]"
            else:
                scrubbed[key] = value
        else:
            scrubbed[key] = value
    
    return scrubbed


def privacy_scrub(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main privacy scrubbing function.
    
    Args:
        context: Raw context dictionary
    
    Returns:
        Scrubbed context safe for external LLM
    """
    return scrub_dict(context)


def validate_scrubbed(context: Dict[str, Any]) -> bool:
    """
    Validate that context has been properly scrubbed.
    
    Returns:
        True if safe, False if sensitive data detected
    """
    # Convert to string and check for patterns
    context_str = str(context).lower()
    
    for pattern, _ in SENSITIVE_PATTERNS:
        if re.search(pattern, context_str):
            # Found potential sensitive data
            return False
    
    return True
