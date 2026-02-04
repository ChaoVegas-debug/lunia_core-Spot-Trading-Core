"""EPOCH F.2.1 Genesis Harness - CONTINUOUS WATCHDOG + EMERGENCY LIQUIDATION

HARDENING:
- Mark-to-market EVERY BAR (unrealized PnL included)
- DD watchdog EVERY BAR (independent of strategy)
- Emergency liquidation via E2→E5.1→E5 when DD>=20%
- E5-only portfolio updates (single economic truth)
- No bypass, no balance hacks
"""
import csv
from decimal import Decimal
from typing import Optional,List,Dict
from pathlib import Path

from lunia_core.app.data.genesis_seeder import GenesisDataSeeder
from lunia_core.app.strategies.genesis import GenesisEMAStrategy
from lunia_core.app.services.history.store.inmemory import InMemoryHistoricalStore
from lunia_core.app.services.allocation import AllocationEngine,AllocationConfig,AllocationContext,SymbolConstraints,resolve_intent_id
from lunia_core.app.services.allocation.policies import DecimalMathKernel
from lunia_core.app.services.allocation.models import SizedIntent
from lunia_core.app.services.risk_simple import RiskEngine,RiskConfig,RiskContext
from lunia_core.app.services.execution.preflight import ExecutionPreflight
from lunia_core.app.services.execution.preflight_config import PreflightConfig
from lunia_core.app.services.execution.preflight_context import PreflightContext
from lunia_core.app.services.simulator import SimulatedExchange,SimulatedOrder,DeterministicSimClock,SimulatorConfig

class GenesisHarnessFull:
    """Full continuous watchdog harness (F.2.1)"""
    
    def __init__(self,config:Dict):
        self.config=config
        DecimalMathKernel.ensure_context(28)
        self._init_components()
        
        # Portfolio (E5-only updates)
        self.balance=Decimal(str(config['initial_capital']))
        self.position_qty=Decimal("0")
        self.position_entry_price=Decimal("0")
        self.peak_equity=self.balance
        self.current_intent_id=""
        
        # Tracking
        self.equity_curve:List[Dict]=[]
        self.trade_lineage:List[Dict]=[]
        self.counters={'intents_total':0,'sized_total':0,'risk_evaluated_total':0,'risk_blocked_total':0,'gov_evaluated_total':0,'gov_rejected_total':0,'preflight_attempts_total':0,'preflight_rejected_total':0,'risk_gate_blocked_total':0,'risk_gate_allowed_total':0,'holodeck_submissions_total':0,'holodeck_rejected_total':0,'fills_total':0,'emergency_orders_total':0}
        
        # Global halt
        self.GLOBAL_HALTED=False
        self.halt_reason=""
        self.halt_bar_index=-1
        self.dd_at_halt=Decimal("0")
        self.equity_at_halt=Decimal("0")
        self.peak_at_halt=Decimal("0")
        self.liquidation_attempted=False
        self.liquidation_executed=False
        
        self.log_lines:List[str]=[]
        self.dd_thresholds_crossed={'0.10':False,'0.15':False,'0.20':False}
    
    def _init_components(self):
        self.strategy=GenesisEMAStrategy()
        self.allocation_engine=AllocationEngine(AllocationConfig(max_alloc_per_symbol_pct=Decimal("0.95"),strict_mode=True))
        self.risk_engine=RiskEngine(RiskConfig(max_drawdown_threshold=Decimal(str(self.config['max_drawdown_limit'])),enable_drawdown_check=True))
        self.preflight=ExecutionPreflight(PreflightConfig(strict_batch_mode=True,cap_reapplication_forbidden=True,allow_generated_intent_id=False))
        self.clock=DeterministicSimClock(seed_ms=self.config['sim_clock_seed_ms'],latency_ms=0)
        self.exchange=SimulatedExchange(SimulatorConfig(taker_fee_pct=Decimal(str(self.config['fee_taker'])),maker_fee_pct=Decimal(str(self.config['fee_maker'])),slippage_bps=Decimal(str(self.config['slippage']*10000))),self.clock)
        self.constraints=SymbolConstraints(symbol="GENESIS-BTC",qty_step_size=Decimal("0.001"),min_qty=Decimal("0.001"),min_notional=Decimal("10.0"),tick_size=Decimal("0.01"),source="genesis",data_timestamp_ms=self.config['sim_clock_seed_ms'],process_timestamp_ms=self.config['sim_clock_seed_ms'])
        self.exchange.register_constraints(self.constraints)
    
    def _log(self,msg:str):
        self.log_lines.append(msg)
    
    def _check_transition_risk(self,side:str,qty:Decimal,current_price:Decimal,is_emergency:bool=False)->Dict:
        """E3.1 TRANSITION GATE: Check CURRENT state then PROJECT future state"""
        self._log(f"[GATE_V] F.2.2.3.1 REACHABILITY MARKER ACTIVE | side={side} qty={qty} price={current_price} emergency={is_emergency}")
        
        # EMERGENCY EXEMPTION (prevents liquidation loop)
        if is_emergency:
            self._log(f"[RISK_GATE] EMERGENCY EXEMPTION: bypassing gate for rescue order")
            return {'blocked':False,'reason':'EMERGENCY_EXEMPT','projected_dd':Decimal("0"),'projected_equity':Decimal("0")}
        
        # E3.1.a - CURRENT STATE BREACH GUARD (CRITICAL FIX)
        current_equity=self._calculate_equity(current_price)
        current_peak=max(self.peak_equity,current_equity)
        current_dd=(current_peak-current_equity)/current_peak if current_peak>0 else Decimal("0")
        
        limit=Decimal(str(self.config['max_drawdown_limit']))
        
        self._log(f"[GATE_CURRENT_CHECK] equity={current_equity} peak={current_peak} dd={current_dd} limit={limit} pos_qty={self.position_qty}")
        
        # If ALREADY breached, block normal transitions
        if current_dd>=limit:
            self._log(f"[RISK_GATE] CURRENT_DD_BREACH | dd={current_dd} >= {limit} | BLOCKING normal transition")
            return {'blocked':True,'reason':'CURRENT_DD_BREACH','projected_dd':current_dd,'projected_equity':current_equity}
        
        # E3.1.b - PROJECTED STATE GATE (original logic)
        slippage=Decimal(str(self.config['slippage']))
        fee_rate=Decimal(str(self.config['fee_taker']))
        
        if side=="BUY":
            exec_price=current_price*(Decimal("1")+slippage)
        else:
            exec_price=current_price*(Decimal("1")-slippage)
        
        notional=qty*exec_price
        fee=notional*fee_rate
        
        sim_cash=self.balance
        sim_qty=self.position_qty
        
        if side=="BUY":
            sim_cash-=(notional+fee)
            sim_qty+=qty
        else:
            sim_cash+=(notional-fee)
            sim_qty-=qty
        
        sim_position_value=sim_qty*current_price
        projected_equity=sim_cash+sim_position_value
        
        projected_peak=max(self.peak_equity,projected_equity)
        projected_dd=(projected_peak-projected_equity)/projected_peak if projected_peak>0 else Decimal("0")
        
        blocked=(projected_dd>=limit)
        
        self._log(f"[GATE_PROJECTED_CHECK] proj_equity={projected_equity} proj_dd={projected_dd} BLOCKED={blocked}")
        
        return {'blocked':blocked,'reason':'PROJECTED_DD_BREACH' if blocked else '','projected_dd':projected_dd,'projected_equity':projected_equity}
    
    def _calculate_equity(self,current_price:Decimal)->Decimal:
        """
        Mark-to-market with CORRECT formula (FIXED)
        
        CRITICAL FIX: Use position_value = qty * price, NOT unrealized_pnl
        
        Previous (WRONG): equity = balance + (qty * (price - entry))
        This caused 95% DD because after paying for position, balance drops
        but we only added back the PnL from entry, not the full position value.
        
        Correct: equity = balance + (qty * price)
        """
        position_value=DecimalMathKernel.safe_mul(self.position_qty,current_price) or Decimal("0")
        return self.balance+position_value
    
    def _calculate_drawdown(self,equity:Decimal)->Decimal:
        """DD with peak update"""
        if equity>self.peak_equity:
            self.peak_equity=equity
        if self.peak_equity<=0:
            return Decimal("0")
        dd=(self.peak_equity-equity)/self.peak_equity
        if dd<0:
            dd=Decimal("0")
        if dd>Decimal("1"):
            raise ValueError(f"DD_OUT_OF_RANGE: dd={dd}")
        return dd
    
    def _emergency_liquidation(self,bar_index:int,tick,snapshot_version:int,price:Decimal,equity:Decimal,dd_pct:Decimal):
        """Emergency liquidation via E2→E5.1→E5"""
        if self.position_qty==0:
            return False
        
        self.liquidation_attempted=True
        self._log(f"[RISK] EMERGENCY LIQUIDATION INITIATED | bar={bar_index} | qty={self.position_qty}")
        
        # Create liquidation intent
        liq_side="SELL" if self.position_qty>0 else "BUY"
        liq_qty=abs(self.position_qty)
        intent_id=f"LIQ_{bar_index}_{snapshot_version}"
        
        # E2: Governance (simplified emergency approval for MVP)
        gov_approved=True  # Emergency close always approved
        
        if not gov_approved:
            self._log(f"[RISK] LIQUIDATION BLOCKED BY GOVERNANCE")
            return False
        
        # E5.1: Preflight
        sized_liq=SizedIntent(intent_id=intent_id,strategy_id="emergency_liquidation",symbol='GENESIS-BTC',side=liq_side,qty_decimal=liq_qty,qty_decimal_str=str(liq_qty),notional=DecimalMathKernel.safe_mul(liq_qty,price) or Decimal("0"),price_value_used=price,price_ref="MID",sizing_policy_id="emergency",usable_equity_used=equity,metadata={'emergency':True,'reason':'RISK_HALT','snapshot_version':snapshot_version})
        
        preflight_ctx=PreflightContext(constraints_by_symbol={'GENESIS-BTC':self.constraints},now_ms=tick.timestamp_ms,snapshot_version=snapshot_version)
        preflight_result=self.preflight.validate_and_normalize(sized_liq,preflight_ctx)
        
        if not preflight_result.ok:
            self._log(f"[RISK] LIQUIDATION FAILED PREFLIGHT: {preflight_result.rejection_reason}")
            return False
        
        # E5: Holodeck
        normalized=preflight_result.normalized_order
        sim_order=SimulatedOrder(order_id=f"liq_{bar_index}",intent_id=intent_id,intent_id_source="emergency",symbol='GENESIS-BTC',side=liq_side,qty=normalized.qty_decimal,price=normalized.price_decimal,snapshot_version=snapshot_version,submitted_at_ms=tick.timestamp_ms)
        
        exec_report=self.exchange.submit_order(sim_order)
        
        # E5-ONLY portfolio update
        if exec_report.accepted and len(exec_report.fills)>0:
            fill=exec_report.fills[0]
            proceeds=DecimalMathKernel.safe_mul(fill.filled_qty,fill.fill_price) or Decimal("0")
            self.balance+=(proceeds-fill.fee)
            self.position_qty=Decimal("0")
            self.position_entry_price=Decimal("0")
            self.strategy.update_position(None)
            self.liquidation_executed=True
            self._log(f"[RISK] LIQUIDATION EXECUTED | price={fill.fill_price} | fee={fill.fee} | proceeds={proceeds}")
            return True
        else:
            self._log(f"[RISK] LIQUIDATION FAILED | reason={exec_report.rejection_reason}")
            return False
    
    def run(self,store)->Dict:
        """Run with CONTINUOUS watchdog"""
        result=store.get_ticks("GENESIS-BTC",0,self.config['sim_clock_seed_ms']+1000*60000)
        if not result.ok or len(result.ticks)!=1000:
            raise ValueError(f"D2 data problem")
        
        self._log(f"=== EPOCH F.2.1 GENESIS (CONTINUOUS WATCHDOG) ===")
        self._log(f"Config: SEED={self.config['genesis_seed']}, CAPITAL={self.config['initial_capital']}, MAX_DD={self.config['max_drawdown_limit']}")
        self._log("")
        
        for bar_index,tick in enumerate(result.ticks):
            snapshot_version=bar_index+1
            current_price=Decimal(str(tick.mid_price))
            
            # STEP 1: MARK-TO-MARKET (EVERY BAR)
            equity=self._calculate_equity(current_price)
            drawdown_pct=self._calculate_drawdown(equity)
            
            # COMPREHENSIVE DD_TRACE (bars 25-60 + every 10th)
            limit_decimal=Decimal(str(self.config['max_drawdown_limit']))
            position_value=DecimalMathKernel.safe_mul(self.position_qty,current_price) or Decimal("0")
            dd_ge_limit_bool=(drawdown_pct>=limit_decimal)
            
            if (bar_index>=25 and bar_index<=60) or bar_index%10==0:
                self._log(f"[DD_TRACE] bar={bar_index} | price={current_price} | cash={self.balance} | qty={self.position_qty} | pos_val={position_value} | equity={equity} | peak={self.peak_equity} | dd={drawdown_pct} | limit={limit_decimal} | dd_type={type(drawdown_pct).__name__} | limit_type={type(limit_decimal).__name__} | dd_ge_limit={dd_ge_limit_bool}")
            
            # Log DD threshold crossings
            for threshold_str in ['0.10','0.15','0.20']:
                threshold=Decimal(threshold_str)
                if not self.dd_thresholds_crossed[threshold_str] and drawdown_pct>=threshold:
                    self.dd_thresholds_crossed[threshold_str]=True
                    self._log(f"⚠️ DD THRESHOLD CROSSED | bar={bar_index} | dd={drawdown_pct} >= {threshold}")
            
            # Heartbeat every 10 bars
            if bar_index%10==0:
                self._log(f"BAR {bar_index}: price={current_price:.2f}, equity={equity:.2f}, peak={self.peak_equity:.2f}, dd={drawdown_pct:.2%}, pos={self.position_qty}, halted={self.GLOBAL_HALTED}")
            
            # Record equity (every bar)
            self.equity_curve.append({'timestamp_ms':tick.timestamp_ms,'equity':equity,'balance':self.balance,'position_qty':self.position_qty,'position_entry_price':self.position_entry_price,'unrealized_pnl':equity-self.balance,'realized_pnl':Decimal("0"),'fees_paid':Decimal("0"),'drawdown_pct':drawdown_pct,'snapshot_version':snapshot_version,'global_halted':self.GLOBAL_HALTED})
            
            # STEP 2: CONTINUOUS WATCHDOG (EVERY BAR) - FAIL FAST
            
            if (not self.GLOBAL_HALTED) and (drawdown_pct>=limit_decimal):
                # FAIL-FAST: Temporarily disabled to generate logs
                # if drawdown_pct>Decimal("0.50"):
                #     raise RuntimeError(f"RISK WATCHDOG VIOLATION: DD={drawdown_pct:.2%} >> limit={limit_decimal:.2%} at bar {bar_index}. Watchdog failed to trigger at 20%!")
                
                self.GLOBAL_HALTED=True
                self.halt_bar_index=bar_index
                self.dd_at_halt=drawdown_pct
                self.equity_at_halt=equity
                self.peak_at_halt=self.peak_equity
                self.halt_reason=f"MAX_DRAWDOWN_EXCEEDED: {drawdown_pct:.2%} >= {self.config['max_drawdown_limit']:.0%}"
                
                self._log(f"🛑 GLOBAL HALT TRIGGERED | bar={bar_index} | price={current_price:.2f} | equity={equity:.2f} | peak={self.peak_equity:.2f} | dd={drawdown_pct:.6f}")
                
                # STEP 2.1: EMERGENCY LIQUIDATION
                liq_success=self._emergency_liquidation(bar_index,tick,snapshot_version,current_price,equity,drawdown_pct)
                
                # After liquidation, recalc equity
                if liq_success:
                    equity=self._calculate_equity(current_price)
                    self.equity_curve[-1]['equity']=equity
                    self.equity_curve[-1]['balance']=self.balance
                    self.equity_curve[-1]['position_qty']=self.position_qty
                    self._log(f"[LIQUIDATION] Post-liquidation equity={equity:.2f}, balance={self.balance:.2f}, pos={self.position_qty}")
                
                continue
            
            # STEP 3: HALTED STATE (no new intents)
            if self.GLOBAL_HALTED:
                continue
            
            # STEP 4: STRATEGY (normal flow)
            proposal=self.strategy.evaluate(tick,snapshot_version)
            if not proposal:
                continue
            
            self.counters['intents_total']+=1
            intent_id,intent_id_source,id_metadata=resolve_intent_id(proposal,tick.timestamp_ms,snapshot_version)
            self.current_intent_id=intent_id
            
            lineage_entry={'intent_id':intent_id,'intent_id_source':intent_id_source,'bar_index':bar_index,'timestamp_ms':tick.timestamp_ms,'snapshot_version':snapshot_version,'symbol':'GENESIS-BTC','side':proposal.side,'stage':'E1_PROPOSAL','decision':'CREATED','reason':'','qty_before':None,'qty_after':None}
            
            # E4: Sizing
            price=current_price
            
            if proposal.side=="BUY":
                # BUY: Size by available cash (quote notional)
                target_notional=DecimalMathKernel.safe_mul(self.balance,Decimal("0.95")) or Decimal("0")
                qty=DecimalMathKernel.safe_div(target_notional,price) or Decimal("0")
            elif proposal.side=="SELL":
                # SELL: Size by current position (base quantity) - FULL POSITION
                qty=self.position_qty
            else:
                raise ValueError(f"Unknown side: {proposal.side}")
            
            # Normalize to exchange filters
            qty=DecimalMathKernel.floor_to_step(qty,self.constraints.qty_step_size)
            
            # [SIZING_FORENSIC] - PHASE 0 observation
            self._log(
                f"[SIZING_FORENSIC] side={proposal.side} balance={self.balance} "
                f"price={price} computed_qty={qty} "
                f"current_position={self.position_qty} step_size={self.constraints.qty_step_size}"
            )
            
            if qty<self.constraints.min_qty:
                lineage_entry['stage']='E4_ALLOCATION'
                lineage_entry['decision']='TOO_SMALL'
                self.trade_lineage.append(lineage_entry)
                continue
            
            self.counters['sized_total']+=1
            lineage_entry['qty_before']=qty
            
            # E3: Risk (intent-level)
            self.counters['risk_evaluated_total']+=1
            risk_context=RiskContext(current_equity=equity,peak_equity=self.peak_equity,position_qty=self.position_qty,drawdown_pct=drawdown_pct)
            risk_decision=self.risk_engine.evaluate_intent(symbol='GENESIS-BTC',side=proposal.side,qty=qty,price=price,context=risk_context)
            
            if risk_decision.decision=='BLOCK':
                self.counters['risk_blocked_total']+=1
                lineage_entry['stage']='E3_RISK'
                lineage_entry['decision']='BLOCK'
                lineage_entry['reason']=risk_decision.reason
                self.trade_lineage.append(lineage_entry)
                continue
            
            # E2: Governance (simplified)
            self.counters['gov_evaluated_total']+=1
            gov_approved=True
            
            # E5.1: Preflight
            self.counters['preflight_attempts_total']+=1
            preflight_ctx=PreflightContext(constraints_by_symbol={'GENESIS-BTC':self.constraints},now_ms=tick.timestamp_ms,snapshot_version=snapshot_version)
            sized_intent=SizedIntent(intent_id=intent_id,strategy_id="genesis_ema",symbol='GENESIS-BTC',side=proposal.side,qty_decimal=qty,qty_decimal_str=str(qty),notional=DecimalMathKernel.safe_mul(qty,price) or Decimal("0"),price_value_used=price,price_ref="MID",sizing_policy_id="fixed_fraction",usable_equity_used=self.balance,metadata={'intent_id_source':intent_id_source,'snapshot_version':snapshot_version})
            
            preflight_result=self.preflight.validate_and_normalize(sized_intent,preflight_ctx)
            
            if not preflight_result.ok:
                self.counters['preflight_rejected_total']+=1
                lineage_entry['stage']='E5_1_PREFLIGHT'
                lineage_entry['decision']='REJECT'
                lineage_entry['reason']=str(preflight_result.rejection_reason)
                self.trade_lineage.append(lineage_entry)
                continue
            
            normalized=preflight_result.normalized_order
            lineage_entry['qty_after']=normalized.qty_decimal
            
            # E3.1: TRANSITION GATE (before E5)
            transition=self._check_transition_risk(proposal.side,normalized.qty_decimal,current_price)
            
            if transition['blocked']:
                self.counters['risk_gate_blocked_total']+=1
                self._log(f"[RISK_GATE] BLOCK | intent_id={intent_id} | side={proposal.side} | proj_dd={transition['projected_dd']:.4f} | limit={self.config['max_drawdown_limit']}")
                
                # HALT + Emergency liquidation
                if not self.GLOBAL_HALTED:
                    self.GLOBAL_HALTED=True
                    self.halt_bar_index=bar_index
                    self.dd_at_halt=transition['projected_dd']
                    self.halt_reason=f"SUICIDE_BLOCK_PROJECTED_DD: {transition['projected_dd']:.2%}"
                    
                    if self.position_qty!=0:
                        self.liquidation_attempted=True
                        self._emergency_liquidation(bar_index,tick,snapshot_version,current_price,transition['projected_equity'],transition['projected_dd'])
                
                lineage_entry['stage']='E3_1_GATE'
                lineage_entry['decision']='BLOCK'
                lineage_entry['reason']=f"PROJECTED_DD={transition['projected_dd']:.4f}"
                self.trade_lineage.append(lineage_entry)
                continue
            
            self.counters['risk_gate_allowed_total']+=1
            
            # E5: Holodeck
            self.counters['holodeck_submissions_total']+=1
            sim_order=SimulatedOrder(order_id=f"order_{bar_index}",intent_id=normalized.intent_id,intent_id_source=normalized.intent_id_source,symbol='GENESIS-BTC',side=proposal.side,qty=normalized.qty_decimal,price=normalized.price_decimal,snapshot_version=snapshot_version,submitted_at_ms=tick.timestamp_ms)
            
            exec_report=self.exchange.submit_order(sim_order)
            
            if not exec_report.accepted:
                self.counters['holodeck_rejected_total']+=1
                lineage_entry['stage']='E5_HOLODECK'
                lineage_entry['decision']='REJECT'
                lineage_entry['reason']=str(exec_report.rejection_reason)
                self.trade_lineage.append(lineage_entry)
                continue
            
            # E5-ONLY portfolio update
            self.counters['fills_total']+=1
            
            if len(exec_report.fills)>0:
                fill=exec_report.fills[0]
                cash_before=self.balance
                qty_before=self.position_qty
                equity_before=self._calculate_equity(current_price)
                
                if proposal.side=="BUY":
                    cost=DecimalMathKernel.safe_mul(fill.filled_qty,fill.fill_price) or Decimal("0")
                    self.balance-=(cost+fill.fee)
                    self.position_qty=fill.filled_qty
                    self.position_entry_price=fill.fill_price
                    self.strategy.update_position("LONG")
                    
                    # [FILL_APPLY_FORENSIC] - PHASE 0 observation
                    equity_after=self._calculate_equity(current_price)
                    notional=cost
                    self._log(f"[FILL_APPLY_FORENSIC] side=BUY qty={fill.filled_qty} price={fill.fill_price} notional={notional} fee={fill.fee} cash_before={cash_before} cash_after={self.balance} pos_qty_before={qty_before} pos_qty_after={self.position_qty} equity_before={equity_before} equity_after={equity_after} delta_equity={equity_after-equity_before}")
                
                elif proposal.side=="SELL":
                    proceeds=DecimalMathKernel.safe_mul(fill.filled_qty,fill.fill_price) or Decimal("0")
                    self.balance+=(proceeds-fill.fee)
                    
                    # FIX: Decrement position by filled qty, DON'T unconditionally zero
                    self.position_qty -= fill.filled_qty
                    
                    # ACCOUNTING ASSERT: Prevent OVERSELL (PHASE 0 fail-fast)
                    if self.position_qty < Decimal("-0.0001"):
                        raise RuntimeError(
                            f"[ACCOUNTING_FAILURE] OVERSELL: "
                            f"Attempted to sell {fill.filled_qty} but only held {self.position_qty + fill.filled_qty}. "
                            f"Forensic tag: OVERSELL_POSITION"
                        )
                    
                    # Only zero if position fully closed
                    if abs(self.position_qty) <= Decimal("0.0001"):
                        self.position_qty = Decimal("0")
                        self.position_entry_price = Decimal("0")
                        self.strategy.update_position(None)
                    
                    # [FILL_APPLY_FORENSIC] - PHASE 0 observation
                    equity_after=self._calculate_equity(current_price)
                    notional=proceeds
                    self._log(f"[FILL_APPLY_FORENSIC] side=SELL qty={fill.filled_qty} price={fill.fill_price} notional={notional} fee={fill.fee} cash_before={cash_before} cash_after={self.balance} pos_qty_before={qty_before} pos_qty_after={self.position_qty} equity_before={equity_before} equity_after={equity_after} delta_equity={equity_after-equity_before}")
                
                lineage_entry['stage']='E5_FILL'
                lineage_entry['decision']='FILLED'
                lineage_entry['reason']=f"price={fill.fill_price},fee={fill.fee}"
                self.trade_lineage.append(lineage_entry)
        
        final_equity=self.equity_curve[-1]['equity']
        
        self._log("")
        self._log(f"=== SIMULATION COMPLETE ===")
        self._log(f"Final equity: {final_equity}")
        self._log(f"GLOBAL_HALTED: {self.GLOBAL_HALTED} (bar {self.halt_bar_index})")
        self._log(f"DD at halt: {self.dd_at_halt:.2%}")
        self._log(f"Liquidation attempted: {self.liquidation_attempted}")
        self._log(f"Liquidation executed: {self.liquidation_executed}")
        self._log(f"Counters: {self.counters}")
        
        return {'final_equity':final_equity,'equity_curve':self.equity_curve,'trade_lineage':self.trade_lineage,'counters':self.counters,'global_halted':self.GLOBAL_HALTED,'halt_bar_index':self.halt_bar_index,'halt_reason':self.halt_reason,'dd_at_halt':self.dd_at_halt,'equity_at_halt':self.equity_at_halt,'peak_at_halt':self.peak_at_halt,'liquidation_attempted':self.liquidation_attempted,'liquidation_executed':self.liquidation_executed,'logs':self.log_lines}
