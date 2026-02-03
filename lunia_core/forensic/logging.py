"""Forensic Logging Helpers

Structured, machine-parseable logging for accounting autopsy.
PHASE 0 ONLY - No decisions, pure observation.
"""
import json
from decimal import Decimal
from datetime import datetime
from typing import Any, Dict

class ForensicLogger:
    """Structured forensic logging for money physics verification"""
    
    def __init__(self):
        self.logs = []
    
    def _serialize(self, obj: Any) -> Any:
        """Convert Decimal and other types to JSON-serializable"""
        if isinstance(obj, Decimal):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._serialize(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._serialize(x) for x in obj]
        return obj
    
    def log_sizing(self, **kwargs):
        """[SIZING_FORENSIC] log entry"""
        entry = {
            "category": "SIZING_FORENSIC",
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs
        }
        self.logs.append(self._serialize(entry))
        print(f"[SIZING_FORENSIC] {json.dumps(self._serialize(kwargs), indent=None)}")
    
    def log_order_build(self, **kwargs):
        """[ORDER_BUILD_FORENSIC] log entry"""
        entry = {
            "category": "ORDER_BUILD_FORENSIC",
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs
        }
        self.logs.append(self._serialize(entry))
        print(f"[ORDER_BUILD_FORENSIC] {json.dumps(self._serialize(kwargs), indent=None)}")
    
    def log_fill_apply(self, **kwargs):
        """[FILL_APPLY_FORENSIC] log entry"""
        entry = {
            "category": "FILL_APPLY_FORENSIC",
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs
        }
        self.logs.append(self._serialize(entry))
        print(f"[FILL_APPLY_FORENSIC] {json.dumps(self._serialize(kwargs), indent=None)}")
    
    def log_accounting_assert(self, **kwargs):
        """[ACCOUNTING_ASSERT_FORENSIC] log entry"""
        entry = {
            "category": "ACCOUNTING_ASSERT_FORENSIC",
            "timestamp": datetime.utcnow().isoformat(),
            **kwargs
        }
        self.logs.append(self._serialize(entry))
        print(f"[ACCOUNTING_ASSERT_FORENSIC] {json.dumps(self._serialize(kwargs), indent=None)}")
    
    def get_logs(self) -> list:
        """Get all logs as list of dicts"""
        return self.logs
    
    def clear(self):
        """Clear all logs"""
        self.logs = []
