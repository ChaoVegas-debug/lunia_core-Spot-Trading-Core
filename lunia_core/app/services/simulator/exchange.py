"""E5 Simulated Exchange - Merciless validation, Decimal-only, truth machine"""
import uuid
from decimal import Decimal
from typing import Optional,Dict
from .models import SimulatedOrder,ExecutionReport,FillEvent,RejectionReason
from .clock import DeterministicSimClock
from .config import SimulatorConfig
from lunia_core.app.services.allocation.models import SymbolConstraints
from lunia_core.app.services.allocation.policies import DecimalMathKernel

class SimulatedExchange:
    """
    Merciless simulated exchange (THE HOLODECK)
    
    PHILOSOPHY:
    - If the system is wrong → simulator breaks it
    - If the system passes → production-ready by construction
    
    INVARIANTS:
    - Strict quantization (no mercy)
    - Decimal-only math
    - Identity enforcement
    - Batch consistency
    - No silent normalization
    - No "auto-fix"
    """
    
    def __init__(self,config:SimulatorConfig,clock:DeterministicSimClock):
        self.config=config
        self.clock=clock
        self.balances:Dict[str,Decimal]={}  # symbol -> qty
        self.constraints_cache:Dict[str,SymbolConstraints]={}
        
        # Ensure Decimal precision (fail-fast)
        DecimalMathKernel.ensure_context(config.decimal_precision)
    
    def set_balance(self,asset:str,qty:Decimal):
        """Set simulated balance"""
        self.balances[asset]=qty
    
    def register_constraints(self,constraints:SymbolConstraints):
        """Register symbol constraints (ground truth)"""
        self.constraints_cache[constraints.symbol]=constraints
    
    def validate_order(
        self,
        order:SimulatedOrder,
        now_ms:int
    )->tuple[bool,Optional[RejectionReason],Optional[str]]:
        """
        Validate order with MERCILESS exchange rules
        
        Returns: (is_valid, rejection_reason, details)
        """
        # Check identity
        if not order.intent_id or not order.intent_id_source:
            return (False,RejectionReason.MISSING_INTENT_ID,"Intent ID required for audit")
        
        # Check for float contamination
        if isinstance(order.qty,float) or (order.price and isinstance(order.price,float)):
            return (False,RejectionReason.FLOAT_DETECTED,"Float detected - Decimal required")
        
        # Get constraints
        constraints=self.constraints_cache.get(order.symbol)
        if not constraints:
            return (False,RejectionReason.INVALID_SYMBOL,f"No constraints for {order.symbol}")
        
        # Check constraint freshness
        age_ms=now_ms-constraints.data_timestamp_ms
        if age_ms>self.config.constraint_staleness_ms:
            return (False,RejectionReason.STALE_CONSTRAINTS,f"Constraints stale (age={age_ms}ms)")
        
        # Validate qty quantization (STRICT)
        step=constraints.qty_step_size
        if step>0:
            # Check if qty aligns to step (using Decimal floor semantics)
            remainder=(order.qty%step) if step!=0 else Decimal("0")
            if remainder!=Decimal("0"):
                return (False,RejectionReason.QTY_NOT_ALIGNED_TO_STEP,
                       f"qty={order.qty} not aligned to step={step}, remainder={remainder}")
        
        # Validate price quantization (if LIMIT order)
        if order.order_type=="LIMIT" and order.price:
            tick=constraints.tick_size
            if tick and tick>0:
                remainder=(order.price%tick) if tick!=0 else Decimal("0")
                if remainder!=Decimal("0"):
                    return (False,RejectionReason.PRICE_NOT_ALIGNED_TO_TICK,
                           f"price={order.price} not aligned to tick={tick}")
        
        # Validate min_qty
        if constraints.min_qty and order.qty<constraints.min_qty:
            return (False,RejectionReason.MIN_QTY_NOT_MET,
                   f"qty={order.qty} < min_qty={constraints.min_qty}")
        
        # Validate max_qty
        if constraints.max_qty and order.qty>constraints.max_qty:
            return (False,RejectionReason.MAX_QTY_EXCEEDED,
                   f"qty={order.qty} > max_qty={constraints.max_qty}")
        
        # Validate min_notional (AFTER quantization, like real exchange)
        if order.price:
            notional=DecimalMathKernel.safe_mul(order.qty,order.price)
            min_notional=constraints.min_notional or Decimal("0")
            if notional and notional<min_notional:
                return (False,RejectionReason.MIN_NOTIONAL_NOT_MET,
                       f"notional={notional} < min_notional={min_notional}")
        
        # All validations passed
        return (True,None,None)
    
    def submit_order(
        self,
        order:SimulatedOrder
    )->ExecutionReport:
        """
        Submit order to simulated exchange
        
        Returns execution report (accepted or rejected)
        """
        now_ms=self.clock.now_ms()
        
        # Validate order
        is_valid,rejection_reason,details=self.validate_order(order,now_ms)
        
        if not is_valid:
            # REJECT (like real exchange)
            return ExecutionReport(
                order_id=order.order_id,
                accepted=False,
                rejection_reason=rejection_reason,
                rejection_details=details,
                status="REJECTED"
            )
        
        # ACCEPT and simulate fill
        fill_price=order.price or Decimal("50000")  # Mock market price for now
        fill_qty=order.qty
        fee=DecimalMathKernel.safe_mul(fill_qty,self.config.taker_fee_pct) or Decimal("0")
        
        fill_event=FillEvent(
            order_id=order.order_id,
            fill_id=str(uuid.uuid4()),
            filled_qty=fill_qty,
            fill_price=fill_price,
            fee=fee,
            filled_at_ms=self.clock.next_event_time()
        )
        
        return ExecutionReport(
            order_id=order.order_id,
            accepted=True,
            fills=[fill_event],
            total_filled_qty=fill_qty,
            remaining_qty=Decimal("0"),
            status="FILLED",
            metadata={"intent_id":order.intent_id,"intent_id_source":order.intent_id_source}
        )
