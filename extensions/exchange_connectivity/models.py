"""
PHASE 12A — EXCHANGE CONNECTIVITY: Models

Deterministic error objects and response schemas.
"""

from typing import Any, Dict, Optional
from dataclasses import dataclass, field


# Error code constants
class ErrorCode:
    """Error code enum (deterministic strings)."""
    ENV_MISSING = "ENV_MISSING"
    HTTP_ERROR = "HTTP_ERROR"
    TIMEOUT = "TIMEOUT"
    JSON_PARSE_ERROR = "JSON_PARSE_ERROR"
    AUTH_FAILED = "AUTH_FAILED"
    SIGNATURE_ERROR = "SIGNATURE_ERROR"
    RATE_LIMIT = "RATE_LIMIT"
    INVALID_SYMBOL = "INVALID_SYMBOL"
    FORBIDDEN_ENDPOINT = "FORBIDDEN_ENDPOINT"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


@dataclass
class ErrorObject:
    """Deterministic error object."""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict (JSON-serializable)."""
        result = {
            "code": self.code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        return result


@dataclass
class Response:
    """Standard response wrapper."""
    ok: bool
    exchange: str
    endpoint: str
    data: Optional[Any] = None
    error: Optional[ErrorObject] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict (JSON-serializable)."""
        result = {
            "ok": self.ok,
            "exchange": self.exchange,
            "endpoint": self.endpoint,
            "data": self.data,
        }
        
        if self.error:
            result["error"] = self.error.to_dict()
        else:
            result["error"] = None
        
        return result
