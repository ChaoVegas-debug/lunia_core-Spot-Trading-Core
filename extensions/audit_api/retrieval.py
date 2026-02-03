"""
PHASE 11E — AUDIT RETRIEVAL API (READ-ONLY)

Production-safe, deterministic audit retrieval for UI visibility.

CRITICAL RULES:
- Read-only: no writes, deletes, or mutations
- Deterministic: same inputs → identical outputs
- No wall-clock: zero time/datetime imports
- Stateless: no global caches
- Fail-closed: structured errors, never crash
- Security: directory traversal protection
"""

import json
import base64
from pathlib import Path
from typing import Dict, Any, List, Optional, Union


# ────────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ────────────────────────────────────────────────────────────────────────────────

DEFAULT_LIMIT = 50
MIN_LIMIT = 1
MAX_LIMIT = 1000
DEFAULT_MAX_BYTES = 64_000


# ────────────────────────────────────────────────────────────────────────────────
# CURSOR ENCODING (Deterministic, Opaque)
# ────────────────────────────────────────────────────────────────────────────────

def encode_cursor(partition: Optional[str], line_index: int, order: str) -> str:
    """
    Encode cursor as opaque Base64 JSON.
    
    Args:
        partition: Partition path (POSIX relative) or None
        line_index: 0-indexed line number
        order: "asc" or "desc"
    
    Returns:
        Base64-encoded cursor string
    """
    payload = {
        "p": partition,
        "i": line_index,
        "o": order,
    }
    # Canonical JSON: sorted keys, compact separators
    json_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return base64.b64encode(json_str.encode('utf-8')).decode('ascii')


def decode_cursor(cursor: str) -> Optional[Dict[str, Any]]:
    """
    Decode cursor from Base64 JSON.
    
    Args:
        cursor: Base64-encoded cursor
    
    Returns:
        Dict with "p" (partition), "i" (line_index), "o" (order), or None if invalid
    """
    try:
        json_bytes = base64.b64decode(cursor.encode('ascii'))
        payload = json.loads(json_bytes.decode('utf-8'))
        
        # Validate structure
        if not isinstance(payload, dict):
            return None
        if "i" not in payload or not isinstance(payload["i"], int):
            return None
        if "o" not in payload or payload["o"] not in ["asc", "desc"]:
            return None
        # "p" can be None or string
        
        return payload
    except Exception:
        return None


# ────────────────────────────────────────────────────────────────────────────────
# SECURITY: DIRECTORY TRAVERSAL PROTECTION
# ────────────────────────────────────────────────────────────────────────────────

def validate_partition_path(root_dir: Path, partition: str) -> Optional[Path]:
    """
    Validate partition path for traversal protection.
    
    Args:
        root_dir: Root directory (absolute)
        partition: Relative partition path (POSIX)
    
    Returns:
        Resolved partition path if valid, None otherwise
    """
    # Reject absolute paths
    if partition.startswith('/'):
        return None
    
    # Reject ".." segments
    if ".." in partition.split('/'):
        return None
    
    # Resolve and check containment
    try:
        partition_path = (root_dir / partition).resolve()
        root_resolved = root_dir.resolve()
        
        # Must be within root_dir
        if not str(partition_path).startswith(str(root_resolved)):
            return None
        
        return partition_path
    except Exception:
        return None


# ────────────────────────────────────────────────────────────────────────────────
# LIST AUDIT PARTITIONS
# ────────────────────────────────────────────────────────────────────────────────

def list_audit_partitions(root_dir: Union[str, Path]) -> List[str]:
    """
    List all audit partition files deterministically.
    
    Args:
        root_dir: Root audit directory
    
    Returns:
        Sorted list of POSIX relative paths (e.g., "2025/01/2025-01-22.jsonl")
    """
    root_path = Path(root_dir)
    
    if not root_path.exists():
        return []
    
    partitions = []
    
    try:
        # Walk directory tree
        for file_path in root_path.rglob("*.jsonl"):
            # Get relative path in POSIX format
            try:
                rel_path = file_path.relative_to(root_path).as_posix()
                partitions.append(rel_path)
            except ValueError:
                # Skip files outside root (shouldn't happen with rglob)
                continue
    except Exception:
        # Fail-closed: return empty list
        return []
    
    # Deterministic sorting
    return sorted(partitions)


# ────────────────────────────────────────────────────────────────────────────────
# LIST AUDIT RECORDS (Paginated)
# ────────────────────────────────────────────────────────────────────────────────

def list_audit_records(
    root_dir: Union[str, Path],
    *,
    partition: Optional[str] = None,
    cursor: Optional[str] = None,
    limit: int = DEFAULT_LIMIT,
    order: str = "asc",
    filters: Optional[Dict[str, Any]] = None,
    memory_store: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    List audit records with pagination.
    
    Args:
        root_dir: Root audit directory
        partition: Optional partition filter (POSIX relative path)
        cursor: Optional pagination cursor (opaque Base64)
        limit: Max records to return (1..1000)
        order: "asc" or "desc" by (timestamp_ms, line_index)
        filters: Optional exact-match filters
        memory_store: Optional MemoryAuditStore for testing
    
    Returns:
        Dict with items, next_cursor,partition, order, limit, stats
    """
    root_path = Path(root_dir)
    
    # Validate and bound limit
    limit = max(MIN_LIMIT, min(MAX_LIMIT, limit))
    
    # Validate order
    if order not in ["asc", "desc"]:
        return _error_result("Invalid order", {"allowed": ["asc", "desc"]})
    
    # Decode cursor if present
    cursor_data = None
    if cursor:
        cursor_data = decode_cursor(cursor)
        if cursor_data is None:
            return _error_result("Invalid cursor", {})
        
        # Order must match cursor order
        if cursor_data["o"] != order:
            return _error_result("Cursor order mismatch", {"cursor_order": cursor_data["o"], "requested_order": order})
    
    # Get partitions to scan
    if partition:
        # Single partition
        partitions_to_scan = [partition]
    else:
        # All partitions
        partitions_to_scan = list_audit_partitions(root_path)
    
    # Scan partitions
    items = []
    stats = {
        "scanned_partitions": 0,
        "scanned_records": 0,
        "returned_records": 0,
    }
    
    # Cursor starting point
    cursor_partition = cursor_data["p"] if cursor_data else None
    cursor_line = cursor_data["i"] if cursor_data else 0
    
    # Track if we've passed the cursor partition
    passed_cursor = cursor_partition is None
    
    for part in partitions_to_scan:
        # Skip partitions before cursor partition
        if not passed_cursor:
            if part == cursor_partition:
                passed_cursor = True
            elif part < cursor_partition:
                continue
            else:
                # We're past cursor partition, start from beginning
                passed_cursor = True
        
        # Validate partition path
        part_path = validate_partition_path(root_path, part)
        if part_path is None or not part_path.exists():
            continue
        
        stats["scanned_partitions"] += 1
        
        # Stream read partition
        try:
            with open(part_path, 'r') as f:
                for line_idx, line in enumerate(f):
                    stats["scanned_records"] += 1
                    
                    # Skip if before cursor line (only in cursor partition)
                    if cursor_partition == part and line_idx < cursor_line:
                        continue
                    
                    # Parse record
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    
                    # Apply filters
                    if filters and not _matches_filters(record, filters):
                        continue
                    
                    # Create summary
                    summary = _create_summary(record, part, line_idx)
                    items.append(summary)
                    stats["returned_records"] += 1
                    
                    # Stop if limit reached
                    if len(items) >= limit:
                        break
        
        except Exception:
            # Fail-closed: skip partition
            continue
        
        # Stop if limit reached
        if len(items) >= limit:
            break
    
    # Sort items deterministically
    items = _sort_items(items, order)
    
    # Generate next cursor
    next_cursor = None
    if len(items) >= limit and items:
        last_item = items[-1]
        # Parse audit_ref to get partition and line
        ref_parts = last_item["audit_ref"].split(':')
        if len(ref_parts) >= 3 and ref_parts[0] == "file":
            next_partition = ref_parts[1]
            next_line = int(ref_parts[2]) + 1
            next_cursor = encode_cursor(next_partition, next_line, order)
    
    return {
        "items": items,
        "next_cursor": next_cursor,
        "partition": partition,
        "order": order,
        "limit": limit,
        "stats": stats,
    }


def _matches_filters(record: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    """Check if record matches exact filters."""
    if "decision_id" in filters:
        if record.get("decision_id") != filters["decision_id"]:
            return False
    
    if "signal" in filters:
        evidence = record.get("decision_evidence", {})
        if evidence.get("signal") != filters["signal"]:
            return False
    
    if "min_ts" in filters:
        if record.get("timestamp_ms", 0) < filters["min_ts"]:
            return False
    
    if "max_ts" in filters:
        if record.get("timestamp_ms", 0) > filters["max_ts"]:
            return False
    
    if "genome_hash" in filters:
        hashes = record.get("hashes", {})
        if hashes.get("genome_hash") != filters["genome_hash"]:
            return False
    
    if "proposal_hash" in filters:
        hashes = record.get("hashes", {})
        if hashes.get("proposal_hash") != filters["proposal_hash"]:
            return False
    
    return True


def _create_summary(record: Dict[str, Any], partition: str, line_idx: int) -> Dict[str, Any]:
    """Create AuditRecordSummary from full record."""
    hashes = record.get("hashes", {})
    evidence = record.get("decision_evidence", {})
    intent = record.get("strategy_intent", {})
    
    return {
        "audit_ref": f"file:{partition}:{line_idx}",
        "timestamp_ms": record.get("timestamp_ms", 0),
        "decision_id": record.get("decision_id"),
        "schema_version": record.get("schema_version"),
        "genome_hash": hashes.get("genome_hash"),
        "snapshot_hash": hashes.get("snapshot_hash"),
        "context_hash": hashes.get("context_hash"),
        "evidence_hash": hashes.get("evidence_hash"),
        "intent_hash": hashes.get("intent_hash"),
        "proposal_hash": hashes.get("proposal_hash"),
        "signal": evidence.get("signal"),
        "confidence": intent.get("confidence"),
        "truncation_note": record.get("truncation_note"),
    }


def _sort_items(items: List[Dict[str, Any]], order: str) -> List[Dict[str, Any]]:
    """Sort items by (timestamp_ms, line_index)."""
    def sort_key(item):
        ts = item["timestamp_ms"]
        # Extract line_index from audit_ref
        ref_parts = item["audit_ref"].split(':')
        line_idx = int(ref_parts[-1]) if len(ref_parts) >= 3 else 0
        return (ts, line_idx)
    
    reverse = (order == "desc")
    return sorted(items, key=sort_key, reverse=reverse)


def _error_result(message: str, details: Dict[str, Any]) -> Dict[str, Any]:
    """Create error result (fail-closed)."""
    return {
        "items": [],
        "next_cursor": None,
        "partition": None,
        "order": "asc",
        "limit": DEFAULT_LIMIT,
        "stats": {
            "scanned_partitions": 0,
            "scanned_records": 0,
            "returned_records": 0,
        },
        "error": {
            "message": message,
            "details": details,
        },
    }


# ────────────────────────────────────────────────────────────────────────────────
# GET AUDIT RECORD
# ────────────────────────────────────────────────────────────────────────────────

def get_audit_record(
    root_dir: Union[str, Path],
    audit_ref: str,
    *,
    memory_store: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Get single audit record by reference.
    
    Args:
        root_dir: Root audit directory
        audit_ref: "file:<partition>:<line>" or "memory:<index>"
        memory_store: Optional MemoryAuditStore
    
    Returns:
        Record dict with audit_ref and source, or error dict
    """
    # Parse audit_ref
    parts = audit_ref.split(':', 2)
    
    if len(parts) < 2:
        return {"error": {"code": "INVALID_REF", "message": "Invalid audit_ref format"}, "audit_ref": audit_ref}
    
    ref_type = parts[0]
    
    if ref_type == "memory":
        # Memory store retrieval
        if memory_store is None:
            return {"error": {"code": "NO_MEMORY_STORE", "message": "Memory store not provided"}, "audit_ref": audit_ref}
        
        try:
            index = int(parts[1])
            if 0 <= index < len(memory_store.records):
                record = memory_store.records[index].copy()
                record["audit_ref"] = audit_ref
                record["source"] = {"type": "memory", "index": index}
                return record
            else:
                return {"error": {"code": "NOT_FOUND", "message": "Record not found"}, "audit_ref": audit_ref}
        except (ValueError, AttributeError):
            return {"error": {"code": "INVALID_INDEX", "message": "Invalid memory index"}, "audit_ref": audit_ref}
    
    elif ref_type == "file":
        if len(parts) < 3:
            return {"error": {"code": "INVALID_REF", "message": "File ref requires partition and line"}, "audit_ref": audit_ref}
        
        partition = parts[1]
        try:
            line_index = int(parts[2])
        except ValueError:
            return {"error": {"code": "INVALID_LINE", "message": "Invalid line index"}, "audit_ref": audit_ref}
        
        # Validate partition path
        root_path = Path(root_dir)
        part_path = validate_partition_path(root_path, partition)
        
        if part_path is None:
            return {"error": {"code": "INVALID_PATH", "message": "Invalid partition path"}, "audit_ref": audit_ref}
        
        if not part_path.exists():
            return {"error": {"code": "NOT_FOUND", "message": "Partition file not found"}, "audit_ref": audit_ref}
        
        # Read exact line
        try:
            with open(part_path, 'r') as f:
                for idx, line in enumerate(f):
                    if idx == line_index:
                        record = json.loads(line)
                        record["audit_ref"] = audit_ref
                        record["source"] = {
                            "type": "file",
                            "partition": partition,
                            "line_index": line_index,
                        }
                        return record
            
            # Line index out of range
            return {"error": {"code": "NOT_FOUND", "message": "Line index out of range"}, "audit_ref": audit_ref}
        
        except json.JSONDecodeError:
            return {"error": {"code": "PARSE_ERROR", "message": "Invalid JSON"}, "audit_ref": audit_ref}
        except Exception as e:
            return {"error": {"code": "READ_ERROR", "message": str(e)[:100]}, "audit_ref": audit_ref}
    
    else:
        return {"error": {"code": "UNKNOWN_TYPE", "message": f"Unknown ref type: {ref_type}"}, "audit_ref": audit_ref}


# ────────────────────────────────────────────────────────────────────────────────
# VERIFY AUDIT RECORD
# ────────────────────────────────────────────────────────────────────────────────

def verify_audit_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verify audit record structure (no re-execution).
    
    Args:
        record: Audit record dict
    
    Returns:
        Verification result with ok, checks, notes
    """
    checks = {
        "has_required_keys": False,
        "hash_fields_present": False,
        "timestamp_valid": False,
        "schema_version_present": False,
    }
    
    notes = []
    
    # Check required keys
    has_timestamp = "timestamp_ms" in record
    has_schema = "schema_version" in record
    
    if has_timestamp and has_schema:
        checks["has_required_keys"] = True
    else:
        if not has_timestamp:
            notes.append("Missing timestamp_ms")
        if not has_schema:
            notes.append("Missing schema_version")
    
    # Check schema version
    if has_schema:
        checks["schema_version_present"] = True
    
    # Check timestamp validity
    if has_timestamp:
        ts = record["timestamp_ms"]
        if isinstance(ts, int) and ts >= 0:
            checks["timestamp_valid"] = True
        else:
            notes.append(f"Invalid timestamp: {ts}")
    
    # Check hash fields
    hashes = record.get("hashes", {})
    expected_hashes = ["genome_hash", "snapshot_hash", "context_hash", "evidence_hash", "intent_hash", "proposal_hash"]
    
    missing_hashes = [h for h in expected_hashes if h not in hashes]
    if not missing_hashes:
        checks["hash_fields_present"] = True
    else:
        notes.append(f"Missing hashes: {', '.join(missing_hashes)}")
    
    # Overall ok
    ok = all(checks.values())
    
    return {
        "ok": ok,
        "checks": checks,
        "notes": notes,
    }


# ────────────────────────────────────────────────────────────────────────────────
# COMPACT AUDIT RECORD
# ────────────────────────────────────────────────────────────────────────────────

def compact_audit_record(record: Dict[str, Any], *, max_bytes: int = DEFAULT_MAX_BYTES) -> Dict[str, Any]:
    """
    Compact record for UI (deterministic size-bounded).
    
    Args:
        record: Full audit record
        max_bytes: Max JSON bytes (default 64KB)
    
    Returns:
        Compacted record with compaction_note if truncated
    """
    # Tier 0: Essential scalars + hashes
    compact = {
        "schema_version": record.get("schema_version"),
        "decision_id": record.get("decision_id"),
        "timestamp_ms": record.get("timestamp_ms"),
        "hashes": record.get("hashes", {}),
        "truncation_note": record.get("truncation_note"),
    }
    
    # Add signal and confidence if available
    evidence = record.get("decision_evidence", {})
    intent = record.get("strategy_intent", {})
    
    if evidence.get("signal"):
        compact["signal"] = evidence["signal"]
    
    if intent.get("confidence") is not None:
        compact["confidence"] = intent["confidence"]
    
    # Check size (Tier 0 baseline)
    size = len(json.dumps(compact, separators=(',', ':')))
    if size <= max_bytes:
        # No truncation needed, but if input had salient/trace, note we compacted
        if record.get("salient_nodes") or record.get("decision_evidence", {}).get("logic_trace"):
            compact["compaction_note"] = "TIER0_NO_TRUNCATION"
        return compact
    
    # Tier 1: Add bounded excerpt
    salient = record.get("salient_nodes", [])
    if salient:
        compact["salient_nodes_excerpt"] = [
            {
                "node_type": node.get("node_type"),
                "severity": node.get("severity"),
                "rationale": (node.get("rationale", "")[:120]),
            }
            for node in salient[:3]
        ]
        compact["compaction_note"] = "TIER1_SALIENT"
    else:
        logic_trace = evidence.get("logic_trace", [])
        if logic_trace:
            compact["logic_trace_excerpt"] = [
                {
                    "node_type": node.get("node_type"),
                    "rationale": (node.get("rationale", "")[:120]),
                }
                for node in logic_trace[:10]
            ]
            compact["compaction_note"] = "TIER1_TRACE"
    
    size = len(json.dumps(compact, separators=(',', ':')))
    if size <= max_bytes:
        return compact
    
    # Tier 2: Drop excerpts
    compact.pop("salient_nodes_excerpt", None)
    compact.pop("logic_trace_excerpt", None)
    compact["compaction_note"] = "TIER2_NO_EXCERPT"
    
    size = len(json.dumps(compact, separators=(',', ':')))
    if size <= max_bytes:
        return compact
    
    # Tier 3: Truncate hashes
    hashes = compact.get("hashes", {})
    compact["hashes"] = {k: (v[:16] + "..." if len(v) > 16 else v) for k, v in hashes.items()}
    compact["compaction_note"] = "TIER3_HASH_TRUNCATE"
    
    size = len(json.dumps(compact, separators=(',', ':')))
    if size <= max_bytes:
        return compact
    
    # Tier 4: Minimal
    compact = {
        "schema_version": record.get("schema_version"),
        "decision_id": record.get("decision_id"),
        "timestamp_ms": record.get("timestamp_ms"),
        "compaction_note": "TIER4_MINIMAL",
    }
    
    return compact
