"""Append-Only Audit Logger (PHASE 6 - STREAMING + VALIDATION + REDACTION)

Thread-safe with internal idempotency + memory-safe NDJSON streaming.
"""
import os
import json
import hashlib
import threading
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Iterator
from datetime import datetime


class AuditLogger:
    """Append-only audit with streaming, validation, and redaction."""
    
    def __init__(self, audit_path: str = "data/risk_audit.jsonl"):
        self.audit_path = Path(audit_path)
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()  # Reentrant lock
        
        if not self.audit_path.exists():
            self.audit_path.touch()
    
    def log_change(
        self,
        action: str,
        request_id: str,
        actor: str,
        reason: str,
        previous_state: Dict[str, Any],
        new_state: Dict[str, Any],
        success: bool,
        error_code: Optional[str] = None
    ) -> str:
        """Log governance change with internal idempotency check (F3 fix)."""
        with self._lock:
            # Internal idempotency check (F3 fix)
            existing = self._find_by_request_id_nolock(request_id)
            if existing:
                return existing["audit_id"]  # Return existing, no duplicate append
            
            # Create new record
            timestamp = datetime.utcnow().isoformat() + "Z"
            
            record = {
                "timestamp": timestamp,
                "actor": actor,
                "action": action,
                "request_id": request_id,
                "reason": reason,
                "previous_state": {
                    "mode": previous_state.get("mode"),
                    "is_halted": previous_state.get("is_halted"),
                    "version": previous_state.get("version")
                },
                "new_state": {
                    "mode": new_state.get("mode"),
                    "is_halted": new_state.get("is_halted"),
                    "version": new_state.get("version")
                },
                "success": success,
                "error_code": error_code
            }
            
            canonical_json = json.dumps(record, sort_keys=True, separators=(',', ':'))
            audit_id = hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
            record["audit_id"] = audit_id
            
            # Append with fsync
            with open(self.audit_path, 'a') as f:
                f.write(json.dumps(record) + '\n')
                f.flush()
                os.fsync(f.fileno())
            
            return audit_id
    
    def stream_records(
        self,
        limit: int = 100,
        actor: Optional[str] = None,
        action: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> Iterator[str]:
        """Stream audit records as NDJSON with validation and redaction.
        
        Args:
            limit: Max valid records to yield (errors don't count). Hard cap 1000.
            actor: Optional filter by actor
            action: Optional filter by action
            request_id: Optional filter by exact request_id
        
        Yields:
            NDJSON lines (JSON object + '\n')
            
        Rules:
            - Generator law: never load entire file into memory
            - Validate each record (JSON parse + checksum)
            - On corruption: yield error record, continue streaming
            - Redact sensitive fields before yielding
            - Errors do NOT count toward limit
        """
        if limit > 1000:
            raise ValueError("LIMIT_EXCEEDED")
        
        if not self.audit_path.exists():
            return
        
        valid_count = 0
        
        with self._lock:
            with open(self.audit_path, 'r') as f:
                for line_num, raw_line in enumerate(f, start=1):
                    # Skip empty lines
                    if not raw_line.strip():
                        continue
                    
                    # Parse JSON
                    try:
                        record = json.loads(raw_line)
                    except json.JSONDecodeError as e:
                        # Yield error record, continue
                        yield json.dumps({
                            "type": "error",
                            "error": "INVALID_JSON",
                            "line_number": line_num,
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "raw": raw_line[:512],  # Truncate to avoid log amplification
                            "audit_id_present": False
                        }) + "\n"
                        continue
                    
                    # Validate checksum
                    stored_audit_id = record.get("audit_id")
                    checksum_record = {k: v for k, v in record.items() if k != "audit_id"}
                    canonical_json = json.dumps(checksum_record, sort_keys=True, separators=(',', ':'))
                    computed_audit_id = hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
                    
                    if stored_audit_id != computed_audit_id:
                        # Yield checksum mismatch error, continue
                        yield json.dumps({
                            "type": "error",
                            "error": "CHECKSUM_MISMATCH",
                            "line_number": line_num,
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "raw": raw_line[:512],
                            "audit_id_present": bool(stored_audit_id),
                            "stored_id": stored_audit_id,
                            "computed_id": computed_audit_id
                        }) + "\n"
                        continue
                    
                    # Apply filters
                    if actor and record.get("actor") != actor:
                        continue
                    if action and record.get("action") != action:
                        continue
                    if request_id and record.get("request_id") != request_id:
                        continue
                    
                    # Redact sensitive data
                    redacted = self._redact_record(record)
                    
                    # Yield valid record
                    yield json.dumps(redacted) + "\n"
                    
                    valid_count += 1
                    if valid_count >= limit:
                        break
    
    def _redact_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive fields to prevent secret leakage."""
        redacted = {}
        
        for key, value in record.items():
            if self._is_sensitive_key(key):
                redacted[key] = "***REDACTED***"
            elif isinstance(value, str):
                redacted[key] = self._redact_sensitive_strings(value)
            elif isinstance(value, dict):
                redacted[key] = self._redact_record(value)  # Recursive
            elif isinstance(value, list):
                redacted[key] = [
                    self._redact_record(item) if isinstance(item, dict) else
                    self._redact_sensitive_strings(item) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                redacted[key] = value
        
        return redacted
    
    def _is_sensitive_key(self, key: str) -> bool:
        """Check if key name is sensitive."""
        sensitive_patterns = [
            "token", "secret", "api_key", "authorization", 
            "password", "key", "credential"
        ]
        key_lower = key.lower()
        return any(pattern in key_lower for pattern in sensitive_patterns)
    
    def _redact_sensitive_strings(self, text: str) -> str:
        """Redact token-like substrings in free text."""
        # Redact long alphanumeric strings (potential tokens)
        text = re.sub(r'\b[a-zA-Z0-9_\-]{32,}\b', '***REDACTED***', text)
        
        # Redact Bearer tokens
        text = re.sub(r'Bearer\s+[a-zA-Z0-9_\-\.]+', 'Bearer ***REDACTED***', text)
        
        return text
    
    def find_by_request_id(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Find audit record by request_id."""
        with self._lock:
            return self._find_by_request_id_nolock(request_id)
    
    def _find_by_request_id_nolock(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Find by request_id (assumes caller holds lock)."""
        if not self.audit_path.exists():
            return None
        
        with open(self.audit_path, 'r') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    if record.get("request_id") == request_id:
                        return record
                except json.JSONDecodeError:
                    continue
        
        return None
    
    def verify_integrity_structured(self) -> Dict[str, Any]:
        """Verify audit log integrity (structured return, no prints)."""
        result = {
            "valid": True,
            "total_records": 0,
            "invalid_records": [],
            "errors": []
        }
        
        if not self.audit_path.exists():
            return result
        
        with self._lock:
            with open(self.audit_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    if not line.strip():
                        continue
                    
                    result["total_records"] += 1
                    
                    try:
                        record = json.loads(line)
                        stored_audit_id = record.get("audit_id")
                        
                        checksum_record = {k: v for k, v in record.items() if k != "audit_id"}
                        canonical_json = json.dumps(checksum_record, sort_keys=True, separators=(',', ':'))
                        computed_audit_id = hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
                        
                        if stored_audit_id != computed_audit_id:
                            result["valid"] = False
                            result["invalid_records"].append({
                                "line": line_num,
                                "stored": stored_audit_id,
                                "computed": computed_audit_id
                            })
                            result["errors"].append(f"Line {line_num}: checksum mismatch")
                            
                    except json.JSONDecodeError as e:
                        result["valid"] = False
                        result["invalid_records"].append({"line": line_num})
                        result["errors"].append(f"Line {line_num}: invalid JSON - {e}")
        
        return result
    
    def get_all_records(self) -> List[Dict[str, Any]]:
        """Get all audit records."""
        records = []
        if not self.audit_path.exists():
            return records
        
        with self._lock:
            with open(self.audit_path, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        
        return records
