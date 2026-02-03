"""
PHASE 13A — SHADOW RUNNER: Loop

Single-strategy shadow execution loop.

CRITICAL RULES:
- Stale guard: NEVER call execute_genome on stale snapshot
- Fail-closed: any error → ERROR status with audit
- Mode A (loop-owned): tick() calls pump.tick()
- Mode B (external): tick(snapshot_override=...) uses provided snapshot
- Canonical time: snapshot event_ts_ms → server_ts_ms → None
"""

from typing import Dict, Any, Optional
from extensions.genome_dsl.execution_surface import execute_genome
from .models import ShadowStepResult, ShadowErrorCode
from .adapter import ShadowAdapter


class ShadowLoop:
    """
    Single-strategy shadow execution loop.
    
    Orchestrates: Pump → Snapshot → Freshness Guard → execute_genome → Adapter → Audit
    """
    
    def __init__(
        self,
        pump: Any,  # LiveDataPump
        genome_json: Dict[str, Any],
        context_template: Dict[str, Any],
        audit_store: Any,  # AuditStore
        adapter: Optional[ShadowAdapter] = None,
        symbol: Optional[str] = None,
    ):
        """
        Initialize shadow loop.
        
        Args:
            pump: LiveDataPump instance
            genome_json: Genome JSON dict
            context_template: Base execution context (will be cloned per tick)
            audit_store: AuditStore instance
            adapter: ShadowAdapter (default: new instance)
            symbol: Trading symbol override (default: from genome metadata)
        """
        self.pump = pump
        self.genome_json = genome_json
        self.context_template = context_template
        self.audit_store = audit_store
        self.adapter = adapter or ShadowAdapter()
        
        # Extract symbol
        if symbol:
            self.symbol = symbol
        else:
            self.symbol = genome_json.get("metadata", {}).get("symbol", "UNKNOWN")
        
        # Statistics
        self.tick_count = 0
        self.executed_count = 0
        self.skipped_stale_count = 0
        self.skipped_noop_count = 0
        self.error_count = 0
        self.last_audit_ref: Optional[str] = None
        self.last_error: Optional[Dict[str, Any]] = None
    
    def _get_canonical_timestamp(self, snapshot: Dict[str, Any]) -> Optional[int]:
        """
        Extract canonical timestamp from snapshot.
        
        Priority: event_ts_ms → server_ts_ms → None
        
        Args:
            snapshot: Market snapshot
        
        Returns:
            Timestamp in ms or None
        """
        event_ts = snapshot.get("event_ts_ms")
        if event_ts is not None:
            return event_ts
        
        server_ts = snapshot.get("server_ts_ms")
        if server_ts is not None:
            return server_ts
        
        return None
    
    def _create_shadow_audit_record(
        self,
        result: ShadowStepResult,
        snapshot: Dict[str, Any],
        decision_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create shadow-layer audit record.
        
        Args:
            result: ShadowStepResult
            snapshot: Market snapshot (bounded)
            decision_id: Decision ID from execute_genome (if any)
        
        Returns:
            Audit record dict
        """
        record = {
            "schema_version": "1.0.0",
            "phase": "13A",
            "symbol": self.symbol,
            "timestamp_ms": result.timestamp_ms,
            "snapshot_health": result.snapshot_health,
            "decision_id": decision_id,
            "status": result.status,
        }
        
        if result.intent:
            record["intent"] = result.intent.to_dict()
        
        if result.virtual_order:
            record["virtual_order"] = result.virtual_order.to_dict()
        
        if result.error:
            record["error"] = result.error
        
        return record
    
    def tick(self, snapshot_override: Optional[Dict[str, Any]] = None) -> ShadowStepResult:
        """
        Execute one shadow loop tick.
        
        Args:
            snapshot_override: Optional snapshot (Mode B: external drive)
        
        Returns:
            ShadowStepResult (never crashes)
        """
        self.tick_count += 1
        
        try:
            # Mode A: call pump.tick() if no override
            if snapshot_override is None:
                self.pump.tick()
            
            # Get snapshot
            snapshot = snapshot_override or self.pump.get_latest_snapshot()
            
            # Canonical timestamp
            timestamp_ms = self._get_canonical_timestamp(snapshot) if snapshot else None
            
            # Guard: missing snapshot
            if not snapshot:
                result = ShadowStepResult(
                    timestamp_ms=timestamp_ms,
                    symbol=self.symbol,
                    status="ERROR",
                    snapshot_health={},
                    error={
                        "code": ShadowErrorCode.SNAPSHOT_MISSING,
                        "message": "No snapshot available",
                    },
                    audit_ref="",
                )
                
                # Persist audit
                try:
                    audit_record = self._create_shadow_audit_record(result, {})
                    result.audit_ref = self.audit_store.append(audit_record)
                    self.last_audit_ref = result.audit_ref
                except Exception:
                    result.audit_ref = "AUDIT_WRITE_FAILED"
                
                self.error_count += 1
                self.last_error = result.error
                return result
            
            # Extract snapshot health
            snapshot_health = snapshot.get("health", {})
            is_fresh = snapshot_health.get("is_fresh", False)
            
            # STALE GUARD (CRITICAL: Never call execute_genome on stale)
            if not is_fresh:
                result = ShadowStepResult(
                    timestamp_ms=timestamp_ms,
                    symbol=self.symbol,
                    status="SKIPPED_STALE",
                    snapshot_health=snapshot_health,
                    audit_ref="",
                )
                
                # Persist audit
                try:
                    audit_record = self._create_shadow_audit_record(result, snapshot)
                    result.audit_ref = self.audit_store.append(audit_record)
                    self.last_audit_ref = result.audit_ref
                except Exception:
                    result.audit_ref = "AUDIT_WRITE_FAILED"
                
                self.skipped_stale_count += 1
                return result
            
            # Build context (clone template + add timestamp)
            context = self.context_template.copy()
            context["now_ms"] = timestamp_ms or 0
            
            # Execute genome
            exec_result = execute_genome(
                self.genome_json,
                snapshot,
                context,
                persist_audit=True,
                audit_store=self.audit_store
            )
            
            # Extract decision_id and intent
            decision_id = exec_result.get("strategy_intent", {}).get("intent_id")
            strategy_intent_dict = exec_result.get("strategy_intent", {})
            
            # Normalize intent
            normalized_intent, intent_error = self.adapter.normalize_intent(strategy_intent_dict)
            
            if intent_error:
                # Intent normalization failed
                result = ShadowStepResult(
                    timestamp_ms=timestamp_ms,
                    symbol=self.symbol,
                    status="ERROR",
                    snapshot_health=snapshot_health,
                    decision_id=decision_id,
                    error=intent_error,
                    audit_ref="",
                )
                
                # Persist audit
                try:
                    audit_record = self._create_shadow_audit_record(result, snapshot, decision_id)
                    result.audit_ref = self.audit_store.append(audit_record)
                    self.last_audit_ref = result.audit_ref
                except Exception:
                    result.audit_ref = "AUDIT_WRITE_FAILED"
                
                self.error_count += 1
                self.last_error = intent_error
                return result
            
            # Check for NOOP
            if normalized_intent.signal == "NOOP":
                result = ShadowStepResult(
                    timestamp_ms=timestamp_ms,
                    symbol=self.symbol,
                    status="SKIPPED_NOOP",
                    snapshot_health=snapshot_health,
                    decision_id=decision_id,
                    intent=normalized_intent,
                    audit_ref="",
                )
                
                # Persist audit
                try:
                    audit_record = self._create_shadow_audit_record(result, snapshot, decision_id)
                    result.audit_ref = self.audit_store.append(audit_record)
                    self.last_audit_ref = result.audit_ref
                except Exception:
                    result.audit_ref = "AUDIT_WRITE_FAILED"
                
                self.skipped_noop_count += 1
                return result
            
            # Create virtual order
            virtual_order, order_error = self.adapter.create_virtual_order(
                normalized_intent,
                snapshot,
                self.symbol
            )
            
            if order_error:
                # Order creation failed (e.g., missing prices)
                result = ShadowStepResult(
                    timestamp_ms=timestamp_ms,
                    symbol=self.symbol,
                    status="SKIPPED_NOOP",  # Fail-closed to NOOP
                    snapshot_health=snapshot_health,
                    decision_id=decision_id,
                    intent=normalized_intent,
                    error=order_error,
                    audit_ref="",
                )
                
                # Persist audit
                try:
                    audit_record = self._create_shadow_audit_record(result, snapshot, decision_id)
                    result.audit_ref = self.audit_store.append(audit_record)
                    self.last_audit_ref = result.audit_ref
                except Exception:
                    result.audit_ref = "AUDIT_WRITE_FAILED"
                
                self.skipped_noop_count += 1
                self.last_error = order_error
                return result
            
            # SUCCESS: Virtual order created
            result = ShadowStepResult(
                timestamp_ms=timestamp_ms,
                symbol=self.symbol,
                status="EXECUTED",
                snapshot_health=snapshot_health,
                decision_id=decision_id,
                intent=normalized_intent,
                virtual_order=virtual_order,
                audit_ref="",
            )
            
            # Persist audit
            try:
                audit_record = self._create_shadow_audit_record(result, snapshot, decision_id)
                result.audit_ref = self.audit_store.append(audit_record)
                self.last_audit_ref = result.audit_ref
            except Exception:
                result.audit_ref = "AUDIT_WRITE_FAILED"
            
            self.executed_count += 1
            return result
        
        except Exception as e:
            # Catch-all error handler (fail-closed)
            result = ShadowStepResult(
                timestamp_ms=None,
                symbol=self.symbol,
                status="ERROR",
                snapshot_health={},
                error={
                    "code": ShadowErrorCode.EXECUTION_ERROR,
                    "message": f"Loop crashed: {str(e)[:200]}",
                },
                audit_ref="",
            )
            
            # Persist audit
            try:
                audit_record = self._create_shadow_audit_record(result, {})
                result.audit_ref = self.audit_store.append(audit_record)
                self.last_audit_ref = result.audit_ref
            except Exception:
                result.audit_ref = "AUDIT_WRITE_FAILED"
            
            self.error_count += 1
            self.last_error = result.error
            return result
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get loop statistics."""
        return {
            "symbol": self.symbol,
            "tick_count": self.tick_count,
            "executed_count": self.executed_count,
            "skipped_stale_count": self.skipped_stale_count,
            "skipped_noop_count": self.skipped_noop_count,
            "error_count": self.error_count,
            "last_audit_ref": self.last_audit_ref,
            "last_error": self.last_error,
        }
