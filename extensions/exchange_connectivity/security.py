"""
PHASE 12A — EXCHANGE CONNECTIVITY: Security & Secrets

Production-safe secret handling with automatic redaction.

CRITICAL RULES:
- Secrets NEVER logged, returned, or in exceptions
- API keys shown as first4...last4
- API secrets always "***"
- HMAC signatures never logged
"""

from typing import Optional


class SafeSecret:
    """Wrapper for sensitive strings with automatic redaction."""
    
    def __init__(self, value: Optional[str]):
        self._value = value
    
    def get(self) -> Optional[str]:
        """Get raw secret value (use sparingly)."""
        return self._value
    
    def is_set(self) -> bool:
        """Check if secret is configured."""
        return self._value is not None and len(self._value) > 0
    
    def __str__(self) -> str:
        """Redacted representation."""
        return "***" if self._value else "None"
    
    def __repr__(self) -> str:
        return f"SafeSecret({'set' if self.is_set() else 'unset'})"


def redact_api_key(api_key: Optional[str]) -> str:
    """
    Redact API key to first4...last4 format.
    
    Args:
        api_key: Raw API key
    
    Returns:
        Redacted string
    """
    if not api_key or len(api_key) < 8:
        return "***"
    
    return f"{api_key[:4]}...{api_key[-4:]}"


def sanitize_error_message(message: str, api_key: Optional[str] = None, api_secret: Optional[str] = None) -> str:
    """
    Remove secrets from error messages.
    
    Args:
        message: Original error message
        api_key: API key to redact (optional)
        api_secret: API secret to redact (optional)
    
    Returns:
        Sanitized message
    """
    sanitized = message
    
    if api_key:
        sanitized = sanitized.replace(api_key, redact_api_key(api_key))
    
    if api_secret:
        sanitized = sanitized.replace(api_secret, "***SECRET***")
    
    return sanitized
