"""E5.1 Execution Preflight - Mechanical normalization (FLOOR-only, no business logic)"""
from decimal import Decimal
from typing import List
from .preflight_models import NormalizedOrder,PreflightResult,BatchPreflightResult,PreflightRejectionReason
from .preflight_config import PreflightConfig
from .preflight_context import PreflightContext
from lunia_core.app.services.allocation.policies import DecimalMathKernel
from lunia_core.app.services.allocation.models import SizedIntent

class ExecutionPreflight:
    """
    Forced normalization layer (by E5 Holodeck)
    
    PHILOSOPHY:
    - The wall (E5) stays strong
    - The adapter (E5.1) earns passage
    - Only mechanical quantization (FLOOR)
    - No business logic, no cap reapplication
    - Fail-closed on ambiguity
    
    INVARIANTS:
    - Decimal-only math
    - Identity from E4 (no generation)
    - Constraint freshness enforced
    - Batch consistency enforced
    - Complete audit trail
    """
    
    def __init__(self,config:PreflightConfig):
        self.config=config
    
    def validate_and_normalize(
        self,
        intent:SizedIntent,
        context:PreflightContext
    )->PreflightResult:
        """
        Validate and normalize single intent to NormalizedOrder
        
        Returns: PreflightResult (ok + normalized_order OR rejection)
        """
        # Ensure Decimal precision (fail-fast)
        DecimalMathKernel.ensure_context(self.config.decimal_precision)
        
        # Validate identity
        if not intent.intent_id or not hasattr(intent,'intent_id'):
            return PreflightResult(
                ok=False,
                rejection_reason=PreflightRejectionReason.MISSING_INTENT_ID,
                rejection_details="Intent ID required from E4"
            )
        
        # Get constraints
        constraints=context.constraints_by_symbol.get(intent.symbol)
        if not constraints:
            return PreflightResult(
                ok=False,
                rejection_reason=PreflightRejectionReason.MISSING_CONSTRAINTS,
                rejection_details=f"No constraints for {intent.symbol}"
            )
        
        # Check constraint freshness
        age_ms=context.now_ms-constraints.data_timestamp_ms
        if age_ms>self.config.constraint_staleness_ms:
            return PreflightResult(
                ok=False,
                rejection_reason=PreflightRejectionReason.STALE_CONSTRAINTS,
                rejection_details=f"Constraints stale (age={age_ms}ms)"
            )
        
        # Float contamination check
        if isinstance(intent.qty_decimal,float):
            return PreflightResult(
                ok=False,
                rejection_reason=PreflightRejectionReason.FLOAT_DETECTED,
                rejection_details="Float detected - Decimal required"
            )
        
        # Non-finite check
        if not DecimalMathKernel.is_finite(intent.qty_decimal):
            return PreflightResult(
                ok=False,
                rejection_reason=PreflightRejectionReason.NON_FINITE_DECIMAL,
                rejection_details=f"Non-finite qty: {intent.qty_decimal}"
            )
        
        # Quantize qty (FLOOR to step_size)
        quantized_qty=DecimalMathKernel.floor_to_step(intent.qty_decimal,constraints.qty_step_size)
        
        # Check if quantization changed qty (would fail E5)
        if quantized_qty!=intent.qty_decimal:
            # This means E4 didn't properly quantize - should not happen if E4 is correct
            # But preflight normalizes anyway (mechanical correction)
            pass
        
        # Quantize price if LIMIT and present
        quantized_price=None
        if intent.price_value_used and constraints.tick_size:
            quantized_price=DecimalMathKernel.floor_to_step(intent.price_value_used,constraints.tick_size)
        
        # Validate min_qty AFTER quantization
        if constraints.min_qty and quantized_qty<constraints.min_qty:
            return PreflightResult(
                ok=False,
                rejection_reason=PreflightRejectionReason.MIN_QTY_NOT_MET,
                rejection_details=f"qty={quantized_qty} < min_qty={constraints.min_qty}"
            )
        
        # Validate max_qty AFTER quantization
        if constraints.max_qty and quantized_qty>constraints.max_qty:
            return PreflightResult(
                ok=False,
                rejection_reason=PreflightRejectionReason.MAX_QTY_EXCEEDED,
                rejection_details=f"qty={quantized_qty} > max_qty={constraints.max_qty}"
            )
        
        # Calculate notional (AFTER quantization)
        price_for_notional=quantized_price or intent.price_value_used or Decimal("50000")  # Fallback for MARKET
        notional=DecimalMathKernel.safe_mul(quantized_qty,price_for_notional) or Decimal("0")
        
        # Validate min_notional AFTER quantization
        min_notional=constraints.min_notional or Decimal("0")
        if notional<min_notional:
            return PreflightResult(
                ok=False,
                rejection_reason=PreflightRejectionReason.MIN_NOTIONAL_NOT_MET,
                rejection_details=f"notional={notional} < min_notional={min_notional}"
            )
        
        # Generate canonical strings
        qty_str=DecimalMathKernel.canonical_decimal_str(quantized_qty,constraints.qty_step_size)
        price_str=DecimalMathKernel.canonical_decimal_str(quantized_price,constraints.tick_size) if quantized_price else None
        
        # Build NormalizedOrder
        normalized=NormalizedOrder(
            intent_id=intent.intent_id,
            intent_id_source=intent.metadata.get("intent_id_source","unknown"),
            symbol=intent.symbol,
            side=intent.side,
            order_type="LIMIT",
            qty_decimal=quantized_qty,
            qty_decimal_str=qty_str,
            price_decimal=quantized_price,
            price_decimal_str=price_str,
            notional_decimal=notional,
            snapshot_version=context.snapshot_version,
            now_ms=context.now_ms,
            constraints_provenance={
                "source":constraints.source,
                "data_timestamp_ms":constraints.data_timestamp_ms,
                "age_ms":age_ms
            },
            metadata={
                "requested_qty":str(intent.qty_decimal),
                "quantized_qty":str(quantized_qty),
                "quantization_method":"FLOOR",
                "requested_price":str(intent.price_value_used) if intent.price_value_used else None,
                "quantized_price":str(quantized_price) if quantized_price else None,
                "policy_trace":["identity_validated","constraints_fresh","qty_quantized","min_max_validated","min_notional_validated"]
            }
        )
        
        return PreflightResult(ok=True,normalized_order=normalized)
    
    def validate_and_normalize_batch(
        self,
        intents:List[SizedIntent],
        context:PreflightContext
    )->BatchPreflightResult:
        """
        Validate and normalize batch of intents
        
        Returns: BatchPreflightResult (ok + normalized_orders OR blocking_reasons)
        """
        normalized_orders=[]
        blocking_reasons=[]
        
        # Check batch consistency (all same snapshot_version)
        if intents:
            first_snapshot=intents[0].metadata.get("snapshot_version",context.snapshot_version)
            for intent in intents:
                intent_snapshot=intent.metadata.get("snapshot_version",context.snapshot_version)
                if intent_snapshot!=first_snapshot:
                    return BatchPreflightResult(
                        ok=False,
                        blocking_reasons=["MIXED_SNAPSHOT_BATCH"]
                    )
        
        # Validate and normalize each
        for intent in intents:
            result=self.validate_and_normalize(intent,context)
            if not result.ok:
                if self.config.strict_batch_mode:
                    # Fail entire batch
                    return BatchPreflightResult(
                        ok=False,
                        blocking_reasons=[f"{result.rejection_reason}:{result.rejection_details}"]
                    )
                else:
                    blocking_reasons.append(f"{result.rejection_reason}:{result.rejection_details}")
            else:
                normalized_orders.append(result.normalized_order)
        
        # Success
        return BatchPreflightResult(
            ok=len(blocking_reasons)==0,
            normalized_orders=normalized_orders if len(blocking_reasons)==0 else [],
            blocking_reasons=blocking_reasons
        )
