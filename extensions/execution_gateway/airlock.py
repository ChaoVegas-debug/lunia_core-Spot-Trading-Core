"""
PHASE 14A — EXECUTION GATEWAY: Airlock

The single chokepoint from StrategyIntent → ExecutableOrderRequest.

CRITICAL RULES:
- Default DENY (starts DISARMED)
- Kill Switch SUPREMACY (absolute veto)
- Fail-fast hierarchy (strict check order)
- Never throws (exceptions → BLOCKED + ERR_000)
- No wall-clock, no I/O, no mutation
- Deterministic output (stable JSON)
"""

import hashlib
from typing import Dict, Any, Tuple, Optional
from .models import (
    RiskLimits,
    ExecutionContextSnapshot,
    ExecutionRequest,
    ExecutionDecision,
    KillSwitchState,
    AuditPayload,
    stable_json,
    canonical_ts,
    normalize_symbol,
)
from .risk_policy import PreTradeRiskEngine


# ────────────────────────────────────────────────────────────────────────────────
# CHECK RESULT
# ────────────────────────────────────────────────────────────────────────────────

class CheckResult:
    """Simple check result container."""
    def __init__(self, passed: bool, code: str, message: str, details: Optional[Dict[str, Any]] = None):
        self.passed = passed
        self.code = code
        self.message = message
        self.details = details or {}


# ────────────────────────────────────────────────────────────────────────────────
# EXECUTION GATEWAY
# ────────────────────────────────────────────────────────────────────────────────

class ExecutionGateway:
    """
    Execution Gateway (Airlock).
    
    Single chokepoint enforcing:
    - Kill Switch supremacy
    - Explicit arming
    - System health gate
    - Snapshot freshness gate
    - Symbol allowlist
    - Pre-trade risk limits
    
    Rules:
    - Default DENY (starts DISARMED)
    - Fail-fast check order: KS→ARM→HLT→SNP→SYM→RSK
    - Never throws (exceptions → BLOCKED + error)
    - Deterministic (same input → same output)
    - No mutation of external state
    """
    
    def __init__(self, limits: RiskLimits):
        """
        Initialize execution gateway.
        
        Args:
            limits: Risk limits configuration
        """
        self._armed = False
        self._armed_reason: Optional[str] = None
        self._kill_switch = KillSwitchState(enabled=False, reason=None, ts_ms=None)
        self._limits = limits
        self._risk_engine = PreTradeRiskEngine(limits)
    
    def arm(self, reason: str) -> None:
        """
        ARM the gateway (allow evaluation).
        
        Args:
            reason: Reason for arming
        """
        self._armed = True
        self._armed_reason = reason
    
    def disarm(self, reason: str) -> None:
        """
        DISARM the gateway (block all).
        
        Args:
            reason: Reason for disarming
        """
        self._armed = False
        self._armed_reason = reason
    
    def set_kill_switch(self, enabled: bool, reason: str, ts_ms: Optional[int] = None) -> None:
        """
        Set kill switch state (absolute veto).
        
        Args:
            enabled: If True, ALL requests blocked
            reason: Reason for kill switch state
            ts_ms: Timestamp of state change
        """
        self._kill_switch = KillSwitchState(enabled=enabled, reason=reason, ts_ms=ts_ms)
    
    def evaluate(
        self,
        request: ExecutionRequest,
        context: ExecutionContextSnapshot,
    ) -> Tuple[ExecutionDecision, AuditPayload]:
        """
        Evaluate execution request (THE AIRLOCK).
        
        Args:
            request: Execution request
            context: System state snapshot
        
        Returns:
            (decision, audit_payload)
        """
        # Initialize checks_passed dict (all checks, default False)
        checks_passed = {
            "KS_001": False,
            "ARM_002": False,
            "HLT_003": False,
            "SNP_004": False,
            "SYM_005": False,
            "RSK_006": False,
        }
        
        # Canonical timestamp computation
        snapshot_ts = None
        portfolio_ts = None
        health_ts = None
        
        if context.snapshot:
            snapshot_ts = context.snapshot.get("event_ts_ms") or context.snapshot.get("server_ts_ms")
        if context.portfolio_state:
            portfolio_ts = context.portfolio_state.get("ts_ms")
        if context.system_health:
            # Health may have nested ts_ms in components, use supervisor as reference
            supervisor = context.system_health.get("supervisor", {})
            health_ts = supervisor.get("ts_ms") if isinstance(supervisor, dict) else None
        
        ts_ms = canonical_ts(request.ts_ms, context.ts_ms, snapshot_ts, portfolio_ts, health_ts)
        
        # Symbol normalization (early, for audit)
        normalized_symbol = ""
        try:
            normalized_symbol = normalize_symbol(request.symbol)
        except Exception as e:
            # Symbol normalization failed → fail early
            decision = ExecutionDecision(
                status="BLOCKED",
                reason_code="SYM_005_NORMALIZATION_FAILED",
                reason_message=f"Symbol normalization failed: {str(e)}",
                checks_passed=checks_passed,
                ts_ms=ts_ms,
                normalized_symbol=request.symbol,  # Use raw symbol
                error={"code": "SYM_005", "message": str(e)},
            )
            audit = self._create_audit_payload(decision, request, context, {})
            return (decision, audit)
        
        # ─────────────────────────────────────────────────────────────────────────
        # FAILSAFE WRAPPER: Never throw
        # ─────────────────────────────────────────────────────────────────────────
        
        try:
            return self._evaluate_internal(request, context, normalized_symbol, ts_ms, checks_passed)
        except Exception as e:
            # Unexpected exception → BLOCKED with ERR_000
            decision = ExecutionDecision(
                status="BLOCKED",
                reason_code="ERR_000",
                reason_message=f"Unexpected error: {str(e)}",
                checks_passed=checks_passed,
                ts_ms=ts_ms,
                normalized_symbol=normalized_symbol,
                error={"code": "ERR_000", "message": str(e), "type": type(e).__name__},
            )
            audit = self._create_audit_payload(decision, request, context, {})
            return (decision, audit)
    
    def _evaluate_internal(
        self,
        request: ExecutionRequest,
        context: ExecutionContextSnapshot,
        normalized_symbol: str,
        ts_ms: Optional[int],
        checks_passed: Dict[str, bool],
    ) -> Tuple[ExecutionDecision, AuditPayload]:
        """
        Internal evaluation with fail-fast checks.
        
        Check order (strict):
        1. KS_001 — Kill Switch
        2. ARM_002 — Arming Status
        3. HLT_003 — System Health
        4. SNP_004 — Snapshot Freshness
        5. SYM_005 — Symbol Allowlist
        6. RSK_006 — Risk Policy
        """
        checks_detail: Dict[str, Any] = {}
        
        # ─────────────────────────────────────────────────────────────────────────
        # CHECK 1: KS_001 — Kill Switch
        # ─────────────────────────────────────────────────────────────────────────
        
        ks_check = self._check_kill_switch()
        checks_detail["KS_001"] = ks_check.details
        
        if not ks_check.passed:
            checks_passed["KS_001"] = False
            # Mark remaining checks as NOT_EVALUATED
            for check_id in ["ARM_002", "HLT_003", "SNP_004", "SYM_005", "RSK_006"]:
                checks_passed[check_id] = False
                checks_detail[check_id] = {"not_evaluated": "FAILFAST_STOPPED_AT_KS_001"}
            
            decision = ExecutionDecision(
                status="BLOCKED",
                reason_code=ks_check.code,
                reason_message=ks_check.message,
                checks_passed=checks_passed,
                ts_ms=ts_ms,
                normalized_symbol=normalized_symbol,
            )
            audit = self._create_audit_payload(decision, request, context, checks_detail)
            return (decision, audit)
        
        checks_passed["KS_001"] = True
        
        # ─────────────────────────────────────────────────────────────────────────
        # CHECK 2: ARM_002 — Arming Status
        # ─────────────────────────────────────────────────────────────────────────
        
        arm_check = self._check_arming()
        checks_detail["ARM_002"] = arm_check.details
        
        if not arm_check.passed:
            checks_passed["ARM_002"] = False
            for check_id in ["HLT_003", "SNP_004", "SYM_005", "RSK_006"]:
                checks_passed[check_id] = False
                checks_detail[check_id] = {"not_evaluated": "FAILFAST_STOPPED_AT_ARM_002"}
            
            decision = ExecutionDecision(
                status="BLOCKED",
                reason_code=arm_check.code,
                reason_message=arm_check.message,
                checks_passed=checks_passed,
                ts_ms=ts_ms,
                normalized_symbol=normalized_symbol,
            )
            audit = self._create_audit_payload(decision, request, context, checks_detail)
            return (decision, audit)
        
        checks_passed["ARM_002"] = True
        
        # ─────────────────────────────────────────────────────────────────────────
        # CHECK 3: HLT_003 — System Health
        # ─────────────────────────────────────────────────────────────────────────
        
        hlt_check = self._check_health(context)
        checks_detail["HLT_003"] = hlt_check.details
        
        if not hlt_check.passed:
            checks_passed["HLT_003"] = False
            for check_id in ["SNP_004", "SYM_005", "RSK_006"]:
                checks_passed[check_id] = False
                checks_detail[check_id] = {"not_evaluated": "FAILFAST_STOPPED_AT_HLT_003"}
            
            decision = ExecutionDecision(
                status="BLOCKED",
                reason_code=hlt_check.code,
                reason_message=hlt_check.message,
                checks_passed=checks_passed,
                ts_ms=ts_ms,
                normalized_symbol=normalized_symbol,
            )
            audit = self._create_audit_payload(decision, request, context, checks_detail)
            return (decision, audit)
        
        checks_passed["HLT_003"] = True
        
        # ─────────────────────────────────────────────────────────────────────────
        # CHECK 4: SNP_004 — Snapshot Freshness
        # ─────────────────────────────────────────────────────────────────────────
        
        snp_check = self._check_snapshot(context)
        checks_detail["SNP_004"] = snp_check.details
        
        if not snp_check.passed:
            checks_passed["SNP_004"] = False
            for check_id in ["SYM_005", "RSK_006"]:
                checks_passed[check_id] = False
                checks_detail[check_id] = {"not_evaluated": "FAILFAST_STOPPED_AT_SNP_004"}
            
            decision = ExecutionDecision(
                status="BLOCKED",
                reason_code=snp_check.code,
                reason_message=snp_check.message,
                checks_passed=checks_passed,
                ts_ms=ts_ms,
                normalized_symbol=normalized_symbol,
            )
            audit = self._create_audit_payload(decision, request, context, checks_detail)
            return (decision, audit)
        
        checks_passed["SNP_004"] = True
        
        # ─────────────────────────────────────────────────────────────────────────
        # CHECK 5: SYM_005 — Symbol Allowlist
        # ─────────────────────────────────────────────────────────────────────────
        
        sym_check = self._check_symbol(normalized_symbol)
        checks_detail["SYM_005"] = sym_check.details
        
        if not sym_check.passed:
            checks_passed["SYM_005"] = False
            checks_passed["RSK_006"] = False
            checks_detail["RSK_006"] = {"not_evaluated": "FAILFAST_STOPPED_AT_SYM_005"}
            
            decision = ExecutionDecision(
                status="BLOCKED",
                reason_code=sym_check.code,
                reason_message=sym_check.message,
                checks_passed=checks_passed,
                ts_ms=ts_ms,
                normalized_symbol=normalized_symbol,
            )
            audit = self._create_audit_payload(decision, request, context, checks_detail)
            return (decision, audit)
        
        checks_passed["SYM_005"] = True
        
        # ─────────────────────────────────────────────────────────────────────────
        # CHECK 6: RSK_006 — Risk Policy
        # ─────────────────────────────────────────────────────────────────────────
        
        rsk_check = self._check_risk(normalized_symbol, request.intent, context)
        checks_detail["RSK_006"] = rsk_check.details
        
        if not rsk_check.passed:
            checks_passed["RSK_006"] = False
            
            decision = ExecutionDecision(
                status="BLOCKED",
                reason_code=rsk_check.code,
                reason_message=rsk_check.message,
                checks_passed=checks_passed,
                ts_ms=ts_ms,
                normalized_symbol=normalized_symbol,
            )
            audit = self._create_audit_payload(decision, request, context, checks_detail)
            return (decision, audit)
        
        checks_passed["RSK_006"] = True
        
        # ─────────────────────────────────────────────────────────────────────────
        # ALL CHECKS PASSED → ALLOWED (but no real execution in Phase 14A)
        # ─────────────────────────────────────────────────────────────────────────
        
        decision = ExecutionDecision(
            status="ALLOWED",
            reason_code="OK",
            reason_message="All gateway checks passed",
            checks_passed=checks_passed,
            ts_ms=ts_ms,
            normalized_symbol=normalized_symbol,
        )
        audit = self._create_audit_payload(decision, request, context, checks_detail)
        return (decision, audit)
    
    # ─────────────────────────────────────────────────────────────────────────────
    # CHECK IMPLEMENTATIONS
    # ─────────────────────────────────────────────────────────────────────────────
    
    def _check_kill_switch(self) -> CheckResult:
        """Check KS_001: Kill Switch."""
        if self._kill_switch.enabled:
            return CheckResult(
                passed=False,
                code="KS_001",
                message=f"Kill switch enabled: {self._kill_switch.reason}",
                details={"enabled": True, "reason": self._kill_switch.reason},
            )
        return CheckResult(
            passed=True,
            code="KS_001",
            message="Kill switch disabled",
            details={"enabled": False},
        )
    
    def _check_arming(self) -> CheckResult:
        """Check ARM_002: Arming Status."""
        if not self._armed:
            return CheckResult(
                passed=False,
                code="ARM_002",
                message=f"Gateway disarmed: {self._armed_reason}",
                details={"armed": False, "reason": self._armed_reason},
            )
        return CheckResult(
            passed=True,
            code="ARM_002",
            message="Gateway armed",
            details={"armed": True, "reason": self._armed_reason},
        )
    
    def _check_health(self, context: ExecutionContextSnapshot) -> CheckResult:
        """Check HLT_003: System Health."""
        if not context.system_health:
            return CheckResult(
                passed=False,
                code="HLT_003",
                message="System health data missing",
                details={"missing": True},
            )
        
        health = context.system_health
        
        # Check critical components: supervisor, portfolio, pumps
        components_to_check = []
        
        supervisor = health.get("supervisor")
        if supervisor:
            components_to_check.append(("supervisor", supervisor))
        
        portfolio = health.get("portfolio")
        if portfolio:
            components_to_check.append(("portfolio", portfolio))
        
        pumps = health.get("pumps", {})
        for symbol, pump_health in pumps.items():
            components_to_check.append((f"pump_{symbol}", pump_health))
        
        degraded_components = []
        
        for component_name, component_health in components_to_check:
            if isinstance(component_health, dict):
                status = component_health.get("status")
                if status in ["DEGRADED", "DOWN"]:
                    degraded_components.append({
                        "component": component_name,
                        "status": status,
                        "error": component_health.get("error"),
                    })
        
        if degraded_components:
            return CheckResult(
                passed=False,
                code="HLT_003",
                message=f"System health degraded: {len(degraded_components)} components",
                details={"degraded_components": degraded_components},
            )
        
        return CheckResult(
            passed=True,
            code="HLT_003",
            message="System health OK",
            details={"components_checked": len(components_to_check)},
        )
    
    def _check_snapshot(self, context: ExecutionContextSnapshot) -> CheckResult:
        """Check SNP_004: Snapshot Freshness."""
        if not context.snapshot:
            return CheckResult(
                passed=False,
                code="SNP_004",
                message="Market snapshot missing",
                details={"missing": True},
            )
        
        snapshot = context.snapshot
        health = snapshot.get("health", {})
        
        is_fresh = health.get("is_fresh")
        is_synced = health.get("is_synced")
        
        if not is_fresh:
            return CheckResult(
                passed=False,
                code="SNP_004",
                message="Snapshot not fresh",
                details={
                    "is_fresh": is_fresh,
                    "is_synced": is_synced,
                    "stale_reason": health.get("stale_reason"),
                },
            )
        
        if not is_synced:
            return CheckResult(
                passed=False,
                code="SNP_004",
                message="Snapshot not synced",
                details={
                    "is_fresh": is_fresh,
                    "is_synced": is_synced,
                },
            )
        
        return CheckResult(
            passed=True,
            code="SNP_004",
            message="Snapshot fresh and synced",
            details={"is_fresh": True, "is_synced": True},
        )
    
    def _check_symbol(self, normalized_symbol: str) -> CheckResult:
        """Check SYM_005: Symbol Allowlist."""
        if normalized_symbol not in self._limits.allowed_symbols:
            return CheckResult(
                passed=False,
                code="SYM_005",
                message=f"Symbol not in allowlist: {normalized_symbol}",
                details={
                    "symbol": normalized_symbol,
                    "allowed_symbols": sorted(list(self._limits.allowed_symbols)),
                },
            )
        
        return CheckResult(
            passed=True,
            code="SYM_005",
            message=f"Symbol allowed: {normalized_symbol}",
            details={"symbol": normalized_symbol},
        )
    
    def _check_risk(
        self,
        normalized_symbol: str,
        intent: Dict[str, Any],
        context: ExecutionContextSnapshot,
    ) -> CheckResult:
        """Check RSK_006: Risk Policy."""
        ok, reason_code, details = self._risk_engine.check(normalized_symbol, intent, context)
        
        if not ok:
            return CheckResult(
                passed=False,
                code=reason_code,
                message=f"Risk check failed: {reason_code}",
                details=details,
            )
        
        return CheckResult(
            passed=True,
            code="RSK_006",
            message="Risk checks passed",
            details=details,
        )
    
    # ─────────────────────────────────────────────────────────────────────────────
    # AUDIT PAYLOAD CREATION
    # ─────────────────────────────────────────────────────────────────────────────
    
    def _create_audit_payload(
        self,
        decision: ExecutionDecision,
        request: ExecutionRequest,
        context: ExecutionContextSnapshot,
        checks_detail: Dict[str, Any],
    ) -> AuditPayload:
        """
        Create audit payload (deterministic).
        
        Args:
            decision: Execution decision
            request: Original request
            context: Context snapshot
            checks_detail: Detailed check results
        
        Returns:
            Audit payload
        """
        # Create deterministic context digest (hash of selected fields)
        context_summary = {
            "snapshot_present": context.snapshot is not None,
            "portfolio_present": context.portfolio_state is not None,
            "health_present": context.system_health is not None,
        }
        
        if context.snapshot:
            context_summary["snapshot_symbol"] = context.snapshot.get("symbol")
            health = context.snapshot.get("health", {})
            context_summary["snapshot_fresh"] = health.get("is_fresh")
            context_summary["snapshot_synced"] = health.get("is_synced")
        
        if context.portfolio_state:
            context_summary["portfolio_equity"] = context.portfolio_state.get("equity")
        
        if context.system_health:
            supervisor = context.system_health.get("supervisor", {})
            context_summary["supervisor_status"] = supervisor.get("status") if isinstance(supervisor, dict) else None
        
        context_digest = hashlib.sha256(
            stable_json(context_summary).encode("utf-8")
        ).hexdigest()[:16]
        
        return AuditPayload(
            schema_version="1.0.0",
            phase="14A",
            event="EXECUTION_GATEWAY_EVALUATED",
            timestamp_ms=decision.ts_ms,
            symbol=decision.normalized_symbol,
            data={
                "decision": decision.to_dict(),
                "context_digest": context_digest,
                "checks_detail": checks_detail,
                "request_intent_signal": request.intent.get("signal"),
            },
        )
