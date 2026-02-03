"""E4 AllocationEngine (HARDENED) - Decimal math, constraint freshness, batch consistency, identity contract"""
import time,uuid
from decimal import Decimal
from typing import List,Optional
from .models import AllocationConfig,AllocationContext,SizedIntent,AllocationPlan,SymbolConstraints,CapMode,resolve_intent_id
from .policies import *
from app.services.strategy.models import IntentProposal

class AllocationEngine:
    """
    Deterministic capital allocation with Decimal math
    
    LOCKED INVARIANTS:
    - Usable equity only
    - Decimal-only math (no float drift)
    - Constraint freshness enforced
    - Batch consistency (one snapshot)
    - Strict mode: any fail blocks all
    - ZERO execution authority
    """
    
    def __init__(self,config:AllocationConfig):
        self.config=config
    
    def build_plan(
        self,
        intents:List[IntentProposal],
        context:AllocationContext,
        now_ms:int
    )->AllocationPlan:
        """Build allocation plan with strict fail-closed semantics"""
        # Ensure Decimal precision (fail-fast)
        DecimalMathKernel.ensure_context(self.config.decimal_precision)
        
        plan_id=str(uuid.uuid4())
        sized_intents=[]
        blocking_reasons=[]
        
        # Validate context
        if context.usable_equity<=0:
            return AllocationPlan(
                plan_id=plan_id,
                blocked=True,
                blocking_reasons=["ALLOC_EQ_USABLE_NONPOSITIVE"],
                computed_at_ms=now_ms,
                snapshot_version=context.snapshot_version
            )
        
        # Apply reserve policy
        reserve=ReservePolicy(self.config.reserve_buffer_pct)
        reserve_result=reserve.apply(context.usable_equity)
        usable_adj=reserve_result.value
        
        # Process each intent
        for intent in intents:
            # Get price
            price=context.mark_prices.get(intent.symbol)
            if not price or price<=0:
                if self.config.strict_mode:
                    return AllocationPlan(plan_id=plan_id,blocked=True,blocking_reasons=[f"ALLOC_MARK_PRICE_MISSING:{intent.symbol}"],computed_at_ms=now_ms,snapshot_version=context.snapshot_version)
                else:
                    blocking_reasons.append(f"ALLOC_MARK_PRICE_MISSING:{intent.symbol}")
                    continue
            
            # Get constraints (REQUIRED)
            constraints=context.constraints.get(intent.symbol)
            if not constraints:
                if self.config.strict_mode:
                    return AllocationPlan(plan_id=plan_id,blocked=True,blocking_reasons=[f"ALLOC_CONSTRAINTS_MISSING:{intent.symbol}"],computed_at_ms=now_ms,snapshot_version=context.snapshot_version)
                else:
                    blocking_reasons.append(f"ALLOC_CONSTRAINTS_MISSING:{intent.symbol}")
                    continue
            
            # Check constraint freshness (use config, not env var)
            age_ms=now_ms-constraints.data_timestamp_ms
            if age_ms>self.config.constraint_staleness_ms:
                if self.config.strict_mode:
                    return AllocationPlan(plan_id=plan_id,blocked=True,blocking_reasons=[f"ALLOC_CONSTRAINTS_STALE:{intent.symbol}(age={age_ms}ms)"],computed_at_ms=now_ms,snapshot_version=context.snapshot_version)
                else:
                    blocking_reasons.append(f"ALLOC_CONSTRAINTS_STALE:{intent.symbol}")
                    continue
            
            # Policy pipeline
            # 1. FixedFraction
            frac=FixedFractionPolicy(self.config.max_alloc_per_symbol_pct,self.config.decimal_precision)
            r1=frac.apply(usable_adj,price)
            if not r1.ok:
                if self.config.strict_mode:
                    return AllocationPlan(plan_id=plan_id,blocked=True,blocking_reasons=[r1.reason],computed_at_ms=now_ms,snapshot_version=context.snapshot_version)
                else:
                    blocking_reasons.append(r1.reason)
                    continue
            
            # 2. ExposureCap
            cap=ExposureCapPolicy(self.config.max_alloc_per_symbol_pct,usable_adj,price,self.config.cap_mode.value)
            r2=cap.apply(r1.value)
            if not r2.ok:
                if self.config.strict_mode:
                    return AllocationPlan(plan_id=plan_id,blocked=True,blocking_reasons=[r2.reason],computed_at_ms=now_ms,snapshot_version=context.snapshot_version)
                else:
                    blocking_reasons.append(r2.reason)
                    continue
            
            # 3. Quantization
            quant=QuantizationPolicy(constraints.qty_step_size)
            r3=quant.apply(r2.value)
            if not r3.ok:
                if self.config.strict_mode:
                    return AllocationPlan(plan_id=plan_id,blocked=True,blocking_reasons=[r3.reason],computed_at_ms=now_ms,snapshot_version=context.snapshot_version)
                else:
                    blocking_reasons.append(r3.reason)
                    continue
            
            # 4. MinMaxQty
            minmax=MinMaxQtyPolicy(constraints.min_qty,constraints.max_qty)
            r4=minmax.apply(r3.value)
            if not r4.ok:
                if self.config.strict_mode:
                    return AllocationPlan(plan_id=plan_id,blocked=True,blocking_reasons=[r4.reason],computed_at_ms=now_ms,snapshot_version=context.snapshot_version)
                else:
                    blocking_reasons.append(r4.reason)
                    continue
            
            # 5. MinNotional
            min_not=MinTradeNotionalPolicy(self.config.min_trade_notional_global,constraints.min_notional,price)
            r5=min_not.apply(r4.value)
            if not r5.ok:
                if self.config.strict_mode:
                    return AllocationPlan(plan_id=plan_id,blocked=True,blocking_reasons=[r5.reason],computed_at_ms=now_ms,snapshot_version=context.snapshot_version)
                else:
                    blocking_reasons.append(r5.reason)
                    continue
            
            # Build SizedIntent
            final_qty=r5.value
            notional=DecimalMathKernel.safe_mul(final_qty,price)
            qty_str=DecimalMathKernel.canonical_decimal_str(final_qty,constraints.qty_step_size)
            
            # Resolve canonical intent_id with explicit policy
            canonical_id,id_source,id_metadata=resolve_intent_id(intent,now_ms,context.snapshot_version)
            
            sized=SizedIntent(
                intent_id=canonical_id,
                strategy_id=intent.strategy_id,
                symbol=intent.symbol,
                side=intent.side,
                qty_decimal=final_qty,
                qty_decimal_str=qty_str,
                notional=notional,
                price_value_used=price,
                price_ref=self.config.price_reference.value,
                sizing_policy_id="fixed_fraction_decimal_v1",
                usable_equity_used=usable_adj,
                metadata={
                    "policies":["reserve","fixed_fraction","exposure_cap","quantization","minmax_qty","min_notional"],
                    "requested_qty":str(r1.value),
                    "capped_qty":str(r2.value),
                    "final_qty":str(final_qty),
                    "constraint_age_ms":age_ms,
                    "now_ms":now_ms,
                    "snapshot_version":context.snapshot_version,
                    "intent_id_source":id_source,
                    "intent_id_generated_components":id_metadata if id_source=="generated" else None
                }
            )
            sized_intents.append(sized)
        
        # Summary
        total_notional=sum(Decimal(s.notional) for s in sized_intents)
        summary={
            "total_notional":str(total_notional),
            "planned_exposure_pct":str(total_notional/context.total_equity) if context.total_equity>0 else "0",
            "intent_count":len(sized_intents)
        }
        
        return AllocationPlan(
            plan_id=plan_id,
            sized_intents=sized_intents,
            blocked=len(blocking_reasons)>0,
            blocking_reasons=blocking_reasons,
            summary_metrics=summary,
            computed_at_ms=now_ms,
            snapshot_version=context.snapshot_version
        )
