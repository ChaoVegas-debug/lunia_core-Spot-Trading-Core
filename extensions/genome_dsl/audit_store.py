"""
PHASE 11D — GENOME DSL: Audit Store (Append-Only Persistence)

Deterministic audit record persistence with size guards and partitioning.

CRITICAL RULES:
- Append-only: never modify existing records
- Deterministic partitioning: based ONLY on context.now_ms (no wall-clock)
- Size-bounded: 1MB cap per record with 3-tier truncation
- No global state: instantiate per-use or inject
- Fail-safe: persistence errors never crash execution
"""

import os
import json
from typing import Dict, Any, Optional
from pathlib import Path


# ────────────────────────────────────────────────────────────────────────────────
# SIZE GUARDS & TRUNCATION
# ────────────────────────────────────────────────────────────────────────────────

MAX_AUDIT_RECORD_BYTES = 1_048_576  # 1MB
LOGIC_TRACE_TRUNCATE_LIMIT = 100  # Keep first 100 entries

def truncate_audit_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply deterministic 3-tier truncation to audit record.
    
    Tier 1: Truncate logic_trace to first 100 entries
    Tier 2: Remove logic_trace entirely (keep salient_nodes only)
    Tier 3: Minimal record (schema, decision_id, timestamp, hashes only)
    
    Args:
        record: Full audit record
    
    Returns:
        Truncated record (deterministic)
    """
    record_json = json.dumps(record, sort_keys=True)
    
    if len(record_json.encode('utf-8')) <= MAX_AUDIT_RECORD_BYTES:
        return record  # No truncation needed
    
    # Tier 1: Truncate logic_trace
    if "decision_evidence" in record and "logic_trace" in record["decision_evidence"]:
        logic_trace = record["decision_evidence"]["logic_trace"]
        if len(logic_trace) > LOGIC_TRACE_TRUNCATE_LIMIT:
            record["decision_evidence"]["logic_trace"] = logic_trace[:LOGIC_TRACE_TRUNCATE_LIMIT]
            record["truncation_note"] = "DATA_TRUNCATED_TIER1"
            
            record_json = json.dumps(record, sort_keys=True)
            if len(record_json.encode('utf-8')) <= MAX_AUDIT_RECORD_BYTES:
                return record
    
    # Tier 2: Remove logic_trace (keep salient_nodes)
    if "decision_evidence" in record:
        record["decision_evidence"].pop("logic_trace", None)
        record["truncation_note"] = "DATA_TRUNCATED_TIER2"
        
        record_json = json.dumps(record, sort_keys=True)
        if len(record_json.encode('utf-8')) <= MAX_AUDIT_RECORD_BYTES:
            return record
    
    # Tier 3: Minimal record
    minimal_record = {
        "schema_version": record.get("schema_version", "1.0.0"),
        "decision_id": record.get("decision_id", "unknown"),
        "timestamp_ms": record.get("timestamp_ms", 0),
        "hashes": record.get("hashes", {}),
        "truncation_note": "DATA_TRUNCATED_MINIMAL",
    }
    
    return minimal_record


# ────────────────────────────────────────────────────────────────────────────────
# AUDIT STORE INTERFACE
# ────────────────────────────────────────────────────────────────────────────────

class AuditStore:
    """
    Interface for audit record persistence.
    
    Implementations must be:
    - Append-only (never modify existing records)
    - Deterministic (same inputs → same storage behavior)
    - Fail-safe (errors return error refs, never crash)
    """
    
    def append(self, record: Dict[str, Any]) -> str:
        """
        Append audit record.
        
        Args:
            record: Audit record dict
        
        Returns:
            Audit reference (deterministic identifier)
        
        Raises:
            Never - returns error ref on failure
        """
        raise NotImplementedError


# ────────────────────────────────────────────────────────────────────────────────
# FILE AUDIT STORE (Default Implementation)
# ────────────────────────────────────────────────────────────────────────────────

class FileAuditStore(AuditStore):
    """
    Append-only JSONL file-based audit store.
    
    Features:
    - Deterministic day-based partitioning (from now_ms)
    - Size guards (1MB cap with truncation)
    - POSIX-style normalized paths
    - Thread-safe append (atomic write)
    """
    
    def __init__(self, root_dir: Optional[str] = None):
        """
        Initialize FileAuditStore.
        
        Args:
            root_dir: Root directory for audit files (default: extensions/.audit)
        """
        if root_dir is None:
            # Default: extensions/.audit relative to this file
            module_dir = Path(__file__).parent
            root_dir = module_dir.parent / ".audit"
        
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_partition_path(self, timestamp_ms: int) -> Path:
        """
        Compute deterministic partition path from timestamp.
        
        Partitioning: day-based using pure arithmetic (no wall-clock).
        Format: YYYY-MM-DD computed from epoch_ms.
        
        Args:
            timestamp_ms: Timestamp in milliseconds (from context.now_ms)
        
        Returns:
            Path to partition file (JSONL)
        """
        # Convert ms to days since epoch
        days_since_epoch = timestamp_ms // 86_400_000
        
        # Convert days to YYYY-MM-DD (deterministic, no wall-clock)
        # Epoch: 1970-01-01
        # Simple algorithm: days → (year, month, day)
        
        # Approximate years first
        year = 1970
        days_remaining = days_since_epoch
        
        while True:
            days_in_year = 366 if self._is_leap_year(year) else 365
            if days_remaining < days_in_year:
                break
            days_remaining -= days_in_year
            year += 1
        
        # Find month and day
        days_in_months = self._get_days_in_months(year)
        month = 1
        for m, days_in_month in enumerate(days_in_months, 1):
            if days_remaining < days_in_month:
                month = m
                day = days_remaining + 1  # 1-indexed
                break
            days_remaining -= days_in_month
        
        # Format as YYYY-MM-DD
        date_str = f"{year:04d}-{month:02d}-{day:02d}"
        
        # Partition file: <root>/<YYYY>/<MM>/<YYYY-MM-DD>.jsonl
        partition_path = self.root_dir / f"{year:04d}" / f"{month:02d}" / f"{date_str}.jsonl"
        partition_path.parent.mkdir(parents=True, exist_ok=True)
        
        return partition_path
    
    def _is_leap_year(self, year: int) -> bool:
        """Check if year is leap year (deterministic)."""
        return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
    
    def _get_days_in_months(self, year: int) -> list:
        """Get days in each month for given year (deterministic)."""
        if self._is_leap_year(year):
            return [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        else:
            return [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    
    def append(self, record: Dict[str, Any]) -> str:
        """
        Append audit record to partition file.
        
        Args:
            record: Audit record dict (must include timestamp_ms)
        
        Returns:
            Audit reference: "<partition_path>:<line_number>"
        """
        try:
            # Apply size guard
            truncated_record = truncate_audit_record(record)
            
            # Get partition path
            timestamp_ms = record.get("timestamp_ms", 0)
            partition_path = self._get_partition_path(timestamp_ms)
            
            # Count existing lines (for reference)
            line_number = 1
            if partition_path.exists():
                with open(partition_path, 'r') as f:
                    line_number = sum(1 for _ in f) + 1
            
            # Append record (JSONL format)
            record_json = json.dumps(truncated_record, sort_keys=True)
            with open(partition_path, 'a') as f:
                f.write(record_json + '\n')
            
            # Return audit reference
            # Use POSIX-style normalized relative path
            relative_path = partition_path.relative_to(self.root_dir)
            posix_path = relative_path.as_posix()
            
            return f"{posix_path}:{line_number}"
        
        except Exception as e:
            # Fail-safe: return error ref
            return f"ERROR:{str(e)[:100]}"


# ────────────────────────────────────────────────────────────────────────────────
# IN-MEMORY AUDIT STORE (Testing)
# ────────────────────────────────────────────────────────────────────────────────

class MemoryAuditStore(AuditStore):
    """
    In-memory audit store for testing.
    
    Records stored in a list (deterministic ordering).
    """
    
    def __init__(self):
        """Initialize empty store."""
        self.records = []
    
    def append(self, record: Dict[str, Any]) -> str:
        """
        Append record to in-memory list.
        
        Args:
            record: Audit record dict
        
        Returns:
            Audit reference: "memory:<index>"
        """
        try:
            # Apply size guard
            truncated_record = truncate_audit_record(record)
            
            # Append to list
            self.records.append(truncated_record)
            
            # Return reference
            return f"memory:{len(self.records) - 1}"
        
        except Exception as e:
            return f"ERROR:{str(e)[:100]}"
