"""Shadow Risk Gate (PHASE 2 - SHADOW + ENFORCE)

Preserves Phase 1 SHADOW behavior (backward compatible).
Adds Phase 2 ENFORCE capability (simulation-only).

Constitution:
- SHADOW mode: always allowed=True (Phase 1 behavior)
- ENFORCE mode: may return allowed=False
- Fail-closed: errors => blocked in ENFORCE
- Decimal math only
"""
import json
from decimal import Decimal
from typing import Dict, Any, Optional

from forensic.risk.ledger import RiskLedger
from forensic.risk.decision import RiskDecision, compute_decision_id
from forensic.risk.simulator import ShadowSimulator
from forensic.risk.config import RiskConfig, RiskMode
from forensic.risk.policy import RiskOverride, validate_override, ArchitecturalViolationError


class ShadowRiskGate:
    """Shadow + Enforce risk gate (E3.1).
    
    PHASE 1 (SHADOW): Observe only, never block
    PHASE 2 (ENFORCE): Block when limits breached
    
    Backward compatible: default config is SHADOW.
    """
    
    def __init__(self, ledger: RiskLedger,  config: Optional[RiskConfig] = None):
        """Initialize risk gate.
        
        Args:
            ledger: RiskLedger instance (post-fill observer)
            config: RiskConfig (default: SHADOW mode)
        """
        self.ledger = ledger
        self.simulator = ShadowSimulator()
        self.config = config or RiskConfig()  # Default SHADOW
    
    def assess(
        self,
        trade_intent: Dict[str, Any],
        portfolio_snapshot: Dict[str, Decimal],
        price: Decimal,
        override: Optional[RiskOverride] = None
    ) -> RiskDecision:
        """Assess risk for pending trade.
        
        Args:
            trade_intent: {id: str, side: str, qty: Decimal}
            portfolio_snapshot: {cash: Decimal, position_qty: Decimal}
            price: Current price (Decimal)
            override: Optional override for ENFORCE mode
            
        Returns:
            RiskDecision
        """
        # Wrap in fail-closed handler
        try:
            return self._assess_internal(trade_intent, portfolio_snapshot, price, override)
        
        except ArchitecturalViolationError:
            # Policy violations must crash (invalid override token)
            raise
        
        except Exception as e:
            # Fail-closed in ENFORCE mode
            if self.config.mode == RiskMode.ENFORCE and self.config.fail_closed:
                # Create fail-closed decision
                state = self.ledger.get_state()
                
                decision_id = compute_decision_id(
                    run_id=state.run_id,
                    intent_id=trade_intent.get('id', 'unknown'),
                    mode="ENFORCE",
                    max_drawdown=self.config.max_drawdown,
                    equity_hwm=state.equity_high_water_mark,
                    equity_current=state.current_equity,
                    equity_projected=state.current_equity,  # Unknown due to error
                    current_dd=state.current_drawdown_pct,
                    projected_dd=state.current_drawdown_pct,
                    would_block=True,  # Fail-closed
                    block_reason="FAIL_CLOSED_ERROR",
                    override_present=override is not None,
                    override_valid=False
                )
                
                decision = RiskDecision(
                    run_id=state.run_id,
                    intent_id=trade_intent.get('id', 'unknown'),
                    decision_id=decision_id,
                    mode="ENFORCE",
                    enforce_active=True,
                    allowed=False,  # BLOCKED
                    would_block=True,
                    blocked=True,
                    block_reason="FAIL_CLOSED_ERROR",
                    current_dd=state.current_drawdown_pct,
                    projected_dd=state.current_drawdown_pct,
                    equity_hwm=state.equity_high_water_mark,
                    equity_current=state.current_equity,
                    equity_projected=state.current_equity,
                    override_present=override is not None,
                    override_valid=False,
                    override_used=False,
                    override_actor=None,
                    override_reason=None
                )
                
                self._log_enforce(decision, exception=str(e))
                return decision
            
            else:
                # SHADOW mode must crash loudly (observation failure)
                raise
    
    def _assess_internal(
        self,
        trade_intent: Dict[str, Any],
        portfolio_snapshot: Dict[str, Decimal],
        price: Decimal,
        override: Optional[RiskOverride]
    ) -> RiskDecision:
        """Internal assessment logic."""
        
        # ╔════════════════════════════════════════════════════════════════╗
        # ║ PHASE 3: EMERGENCY PRE-CHECK (MUST BE FIRST)                  ║
        # ║ Safety Valve: Bypass enforcement for emergency SELL only      ║
        # ╚════════════════════════════════════════════════════════════════╝
        
        if trade_intent.get('is_emergency', False):
            state = self.ledger.get_state()
            intent_id = trade_intent.get('id', 'unknown')
            emergency_reason = trade_intent.get('emergency_reason', 'UNSPECIFIED')
            
            # Emergency BUY is FORBIDDEN (architectural violation)
            if trade_intent.get('side') == "BUY":
                print(f"[RISK_VIOLATION] EMERGENCY_BUY_ATTEMPTED run_id={state.run_id} "
                      f"intent_id={intent_id} violation=SAFETY_VALVE_BUY_ATTEMPT "
                      f"emergency_reason={emergency_reason}")
                
                # Return blocked decision with violation reason
                return RiskDecision(
                    run_id=state.run_id,
                    intent_id=intent_id,
                    decision_id="emergency-buy-blocked",
                    mode=self.config.mode.value,
                    enforce_active=True,
                    allowed=False,
                    would_block=True,
                    blocked=True,
                    block_reason="EMERGENCY_BUY_FORBIDDEN",
                    current_dd=state.current_drawdown_pct,
                    projected_dd=state.current_drawdown_pct,
                    equity_hwm=state.equity_high_water_mark,
                    equity_current=state.current_equity,
                    equity_projected=state.current_equity,
                    override_present=False,
                    override_valid=False,
                    override_used=False
                )
            
            # Emergency SELL → SAFETY VALVE BYPASS
            print(f"[RISK_EMERGENCY_BYPASS] SAFETY_VALVE_ACTIVATED run_id={state.run_id} "
                  f"intent_id={intent_id} side=SELL emergency_reason={emergency_reason} "
                  f"decision=ALLOWED_BYPASS")
            
            return RiskDecision(
                run_id=state.run_id,
                intent_id=intent_id,
                decision_id="emergency-bypass",
                mode=self.config.mode.value,
                enforce_active=False,  # Bypass enforcement
                allowed=True,  # ALLOWED
                would_block=False,  # Not blocked
                blocked=False,
                block_reason=None,
                current_dd=state.current_drawdown_pct,
                projected_dd=Decimal("0"),  # Irrelevant for emergency
                equity_hwm=state.equity_high_water_mark,
                equity_current=state.current_equity,
                equity_projected=state.current_equity,  # Not projected
                override_present=False,
                override_valid=False,
                override_used=False,
                is_emergency_bypass=True,
                emergency_reason=emergency_reason
            )
        
        # ╔════════════════════════════════════════════════════════════════╗
        # ║ STANDARD RISK ASSESSMENT (PHASE 1/2 LOGIC)                    ║
        # ╚════════════════════════════════════════════════════════════════╝
        
        # Read ledger state (Phase 1 truth)
        state = self.ledger.get_state()
        
        # Current drawdown (from ledger)
        current_dd = state.current_drawdown_pct
        
        # Project impact (Phase 1 simulator)
        projection = self.simulator.project_impact(
            portfolio_snapshot=portfolio_snapshot,
            trade_intent=trade_intent,
            price=price
        )
        
        # Compute projected drawdown
        projected_equity = projection['equity']
        projection_hwm = max(state.equity_high_water_mark, projected_equity)
        
        if projection_hwm > Decimal("0"):
            projected_dd = (projection_hwm - projected_equity) / projection_hwm
        else:
            projected_dd = Decimal("0")
        
        # Compute would_block signal
        max_dd = self.config.max_drawdown
        would_block = (current_dd >= max_dd) or (projected_dd >= max_dd)
        
        # Determine block reason
        if current_dd >= max_dd:
            block_reason = "CURRENT_DRAWDOWN_25PCT"
        elif projected_dd >= max_dd:
            block_reason = "PROJECTED_DRAWDOWN_25PCT"
        else:
            block_reason = None
        
        # Mode-specific behavior
        if self.config.mode == RiskMode.SHADOW:
            # PHASE 1: Always allow (backward compatible)
            enforce_active = False
            allowed = True
            blocked = False
            override_valid = False
            override_used = False
            
        else:  # ENFORCE
            enforce_active = True
            
            if not would_block:
                # No risk violation
                allowed = True
                blocked = False
                override_valid = False
                override_used = False
            
            else:
                # Risk violation - check override
                override_valid = validate_override(override) if self.config.override_enabled else False
                
                if override_valid:
                    # Override allows pass-through
                    allowed = True
                    blocked = False
                    override_used = True
                else:
                    # BLOCKED
                    allowed = False
                    blocked = True
                    override_used = False
        
        # Compute deterministic decision_id
        decision_id = compute_decision_id(
            run_id=state.run_id,
            intent_id=trade_intent.get('id', 'unknown'),
            mode=self.config.mode.value,
            max_drawdown=self.config.max_drawdown,
            equity_hwm=state.equity_high_water_mark,
            equity_current=state.current_equity,
            equity_projected=projected_equity,
            current_dd=current_dd,
            projected_dd=projected_dd,
            would_block=would_block,
            block_reason=block_reason,
            override_present=override is not None,
            override_valid=override_valid
        )
        
        # Create decision
        decision = RiskDecision(
            run_id=state.run_id,
            intent_id=trade_intent.get('id', 'unknown'),
            decision_id=decision_id,
            mode=self.config.mode.value,
            enforce_active=enforce_active,
            allowed=allowed,
            would_block=would_block,
            blocked=blocked,
            block_reason=block_reason,
            current_dd=current_dd,
            projected_dd=projected_dd,
            equity_hwm=state.equity_high_water_mark,
            equity_current=state.current_equity,
            equity_projected=projected_equity,
            override_present=override is not None,
            override_valid=override_valid,
            override_used=override_used,
            override_actor=override.actor if (override and override_valid) else None,
            override_reason=override.reason if (override and override_valid) else None
        )
        
        # Emit logs
        self._log_shadow(decision)  # Phase 1 log (preserve)
        self._log_enforce(decision)  # Phase 2 log (new)
        
        return decision
    
    def _log_shadow(self, decision: RiskDecision):
        """Emit Phase 1 log (preserve backward compatibility)."""
        log_data = {
            "run_id": decision.run_id,
            "intent_id": decision.intent_id,
            "check": "MAX_DRAWDOWN",
            "layer": "E3.1",
            "equity_hwm": str(decision.equity_hwm),
            "equity_current": str(decision.equity_current),
            "equity_projected": str(decision.equity_projected),
            "current_dd_pct": f"{decision.current_dd * Decimal('100'):.2f}",
            "projected_dd_pct": f"{decision.projected_dd * Decimal('100'):.2f}",
            "limit_pct": "25.00",
            "WOULD_BLOCK": decision.would_block,
            "would_block_reason": decision.block_reason,
            "decision": "ALLOWED_SHADOW_MODE" if decision.mode == "SHADOW" else "ENFORCEMENT_ACTIVE",
            "reason": "PHASE_1_OBSERVER_NO_ENFORCE" if decision.mode == "SHADOW" else "PHASE_2_ENFORCE"
        }
        
        print(f"[RISK_SHADOW_ASSESSMENT] {json.dumps(log_data)}")
    
    def _log_enforce(self, decision: RiskDecision, exception: Optional[str] = None):
        """Emit Phase 2 enforcement log."""
        log_data = {
            "run_id": decision.run_id,
            "intent_id": decision.intent_id,
            "decision_id": decision.decision_id,
            "layer": "E3.1",
            "mode": decision.mode,
            "enforce_active": decision.enforce_active,
            "check": "MAX_DRAWDOWN",
            "equity_hwm": str(decision.equity_hwm),
            "equity_current": str(decision.equity_current),
            "equity_projected": str(decision.equity_projected),
            "current_dd": str(decision.current_dd),
            "projected_dd": str(decision.projected_dd),
            "limit": str(self.config.max_drawdown),
            "WOULD_BLOCK": decision.would_block,
            "BLOCKED": decision.blocked,
            "block_reason": decision.block_reason,
            "override_present": decision.override_present,
            "override_valid": decision.override_valid,
            "override_used": decision.override_used,
            "override_actor": decision.override_actor,
            "decision": "ALLOWED" if decision.allowed else "BLOCKED",
            "reason": f"PHASE_2_{decision.mode}" if not exception else "FAIL_CLOSED",
        }
        
        if exception:
            log_data["exception"] = exception
        
        print(f"[RISK_ENFORCE] {json.dumps(log_data)}")
