"""
PHASE 11C — GENOME DSL: Integration Bridge (Genome → Phase 9/10)

Transforms genome evaluation evidence into StrategyIntent (Phase 9) and ProposalCard (Phase 10).

CRITICAL RULES:
- Deterministic decision_id (SHA256 of genome_id + snapshot_hash + context_hash)
- Confidence penalties (fallback, violations)
- Top-5 salient node selection for UI reasoning
- Validate using Phase 9 ValidationChain
- Use Phase 10 factory for ProposalCard
- Fail-closed: errors → NOOP intent/proposal
"""

import hashlib
import json
from typing import Dict, Any, Optional, List
from extensions.genome_dsl import types, interpreter
from extensions.genome_dsl.canonical import to_canonical_json, genome_id
from extensions.protocol.protocol import (
    StrategyIntent, TradeExitPlan, IntentType, TradeDirection,
    StrategyFrequency, MarketSnapshot, PROTOCOL_VERSION
)
from extensions.sandbox.validator import ValidationChain
from extensions.proposals.factory import create_proposal
from extensions.proposals.types import ProposalContext, ProposalCard, ProposalStatus


# ────────────────────────────────────────────────────────────────────────────────
# HASH HELPERS (Deterministic)
# ────────────────────────────────────────────────────────────────────────────────

def snapshot_hash(snapshot: Dict[str, Any]) -> str:
    """Generate deterministic snapshot hash."""
    # Normalize and sort
    canonical = to_canonical_json(snapshot)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def context_hash(context: Dict[str, Any]) -> str:
    """Generate deterministic context hash."""
    # Include only deterministic fields
    deterministic_ctx = {
        "now_ms": context.get("now_ms", 0),
        "governance_level": context.get("governance_level", "AUTO"),
    }
    canonical = to_canonical_json(deterministic_ctx)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def decision_id(genome: types.StrategyGenome, snapshot: Dict[str, Any], context: Dict[str, Any]) -> str:
    """
    Generate deterministic decision ID.
    
    SHA256(genome_id + snapshot_hash + context_hash)
    
    Returns:
        16-hex decision ID
    """
    gid = genome_id(genome)
    shash = snapshot_hash(snapshot)
    chash = context_hash(context)
    
    combined = f"{gid}:{shash}:{chash}"
    digest = hashlib.sha256(combined.encode('utf-8')).hexdigest()
    return digest[:16]


# ────────────────────────────────────────────────────────────────────────────────
# CONFIDENCE PENALTIES
# ────────────────────────────────────────────────────────────────────────────────

def apply_confidence_penalties(evidence: types.DecisionEvidence) -> float:
    """
    Apply deterministic confidence penalties.
    
    Base = 1.0
    - Fallback penalty: -0.1 per fallback (cap -0.3)
    - Critical path WARN/BLOCK penalty: -0.2
    - Constitutional violation: → 0.0
    
    Returns:
        Final confidence [0.0, 1.0]
    """
    base = evidence.confidence_raw
    
    # Constitutional violation → zero confidence
    if evidence.constitutional_violations:
        return 0.0
    
    # Fallback penalty
    fallback_penalty = min(evidence.fallback_count * 0.1, 0.3)
    base -= fallback_penalty
    
    # Critical path WARN/BLOCK penalty
    has_critical_warn_or_block = any(
        node.severity in ["WARN", "BLOCK"]
        for node in evidence.logic_trace
    )
    if has_critical_warn_or_block:
        base -= 0.2
    
    # Clamp
    return max(0.0, min(1.0, base))


# ────────────────────────────────────────────────────────────────────────────────
# TOP-5 SALIENT NODES (for UI reasoning)
# ────────────────────────────────────────────────────────────────────────────────

def select_top_5_nodes(evidence: types.DecisionEvidence) -> List[types.NodeEvidence]:
    """
    Select top 5 salient nodes for UI reasoning.
    
    Priority:
    1. BLOCK severity
    2. WARN severity
    3. Critical path nodes (info from significant node types)
    4. Lexicographic node_id tiebreak
    
    Returns:
        List of up to 5 NodeEvidence entries
    """
    # Sort by priority
    def priority(node: types.NodeEvidence) -> tuple:
        severity_rank = {"BLOCK": 0, "WARN": 1, "INFO": 2}.get(node.severity, 3)
        # Critical node types: comparators, gates, signals
        is_critical = node.node_type in [
            "GreaterThan", "LessThan", "Equal", "CrossAbove", "CrossBelow",
            "CostGate", "RegimeFilter", "SignalEntry", "SignalExit"
        ]
        critical_rank = 0 if is_critical else 1
        return (severity_rank, critical_rank, node.node_id)
    
    sorted_nodes = sorted(evidence.logic_trace, key=priority)
    return sorted_nodes[:5]


def compress_reasoning(top_nodes: List[types.NodeEvidence]) -> str:
    """
    Compress top nodes into human-readable reasoning string.
    
    Returns:
        Reasoning string (≤500 chars recommended)
    """
    if not top_nodes:
        return "No evaluation evidence available"
    
    lines = []
    for i, node in enumerate(top_nodes, 1):
        # Format: "1. NodeType: rationale"
        line = f"{i}. {node.node_type}: {node.rationale}"
        lines.append(line)
    
    reasoning = " | ".join(lines)
    
    # Truncate if too long
    if len(reasoning) > 500:
        reasoning = reasoning[:497] + "..."
    
    return reasoning


# ────────────────────────────────────────────────────────────────────────────────
# GENOME → INTENT
# ────────────────────────────────────────────────────────────────────────────────

def genome_to_intent(
    genome: types.StrategyGenome,
    snapshot: Dict[str, Any],
    context: Dict[str, Any],
) -> StrategyIntent:
    """
    Transform genome evaluation into StrategyIntent.
    
    Args:
        genome: StrategyGenome AST
        snapshot: Market snapshot dict
        context: Execution context dict
    
    Returns:
        StrategyIntent (validated or NOOP if validation fails)
    """
    # Evaluate genome
    evidence = interpreter.evaluate(genome, snapshot, context)
    
    # Generate deterministic ID
    intent_id = decision_id(genome, snapshot, context)
    
    # Apply confidence penalties
    confidence = apply_confidence_penalties(evidence)
    
    # Select top 5 nodes for reasoning
    top_nodes = select_top_5_nodes(evidence)
    reasoning = compress_reasoning(top_nodes)
    
    # Map signal to intent type
    if evidence.signal == "ENTRY":
        intent_type = IntentType.ENTRY
    elif evidence.signal == "EXIT":
        intent_type = IntentType.EXIT
    else:
        intent_type = IntentType.NOOP
    
    # Extract direction from genome entry_condition (if SignalEntry exists)
    direction = None
    symbol = snapshot.get("symbol", "UNKNOWN")
    size_base = None
    
    if intent_type == IntentType.ENTRY:
        # Search for SignalEntry in genome
        direction_str = _extract_signal_direction(genome.entry_condition)
        if direction_str == "BUY":
            direction = TradeDirection.LONG
        elif direction_str == "SELL":
            direction = TradeDirection.SHORT
        
        # Use sizing_pct from evidence
        size_base = evidence.sizing_pct / 100.0  # Convert pct to decimal
    
    # Map exit plan
    exit_plan = None
    if intent_type == IntentType.ENTRY and genome.exit_plan:
        exit_plan = TradeExitPlan(
            stop_loss_price=None,
            stop_loss_pct=genome.exit_plan.stop_loss_pct,
            take_profit_price=None,
            take_profit_pct=genome.exit_plan.take_profit_pct,
            time_limit_ms=genome.exit_plan.time_limit_ms,
            trail_start_pct=None,
        )
    
    # Get strategy metadata
    strategy_id = genome.metadata.get("strategy_id", "genome_strategy")
    strategy_name = genome.metadata.get("name", "Genome Strategy")
    
    # Construct intent
    now_ms = context.get("now_ms", 0)
    correlation_id = context.get("correlation_id", intent_id)
    
    intent = StrategyIntent(
        intent_id=intent_id,
        ts_ms=now_ms,
        protocol_version=PROTOCOL_VERSION,
        correlation_id=correlation_id,
        intent_type=intent_type,
        direction=direction,
        symbol=symbol,
        size_base=size_base,
        size_quote=None,
        exit_plan=exit_plan,
        confidence=confidence,
        rationale=reasoning,
        strategy_id=strategy_id,
        strategy_frequency=StrategyFrequency.INTRADAY,  # Default
        is_hedge=False,
        is_scaling=False,
    )
    
    # Validate using Phase 9 validator
    validator = ValidationChain()
    
    # Create minimal governance context for validation
    from extensions.protocol.protocol import GovernanceContext, RiskState
    gov_context = GovernanceContext(
        ts_ms=now_ms,
        run_id=context.get("run_id", "genome_run"),
        correlation_id=correlation_id,
        is_live=False,
        is_reduce_only=False,
        allow_new_entries=True,
        max_position_size=10000.0,
        max_leverage=3.0,
        risk_state=RiskState.GREEN,
        emergency_override_active=False,
    )
    
    validation_result = validator.validate(intent, gov_context)
    
    if not validation_result.is_valid:
        # Validation failed: return NOOP intent
        return StrategyIntent(
            intent_id=intent_id,
            ts_ms=now_ms,
            protocol_version=PROTOCOL_VERSION,
            correlation_id=correlation_id,
            intent_type=IntentType.NOOP,
            direction=None,
            symbol=None,
            size_base=None,
            size_quote=None,
            exit_plan=None,
            confidence=0.0,
            rationale=f"Validation failed: {validation_result.reject_code}",
            strategy_id=strategy_id,
            strategy_frequency=StrategyFrequency.INTRADAY,
            is_hedge=False,
            is_scaling=False,
        )
    
    return intent


def _extract_signal_direction(entry_node: Any) -> Optional[str]:
    """Extract direction from SignalEntry node (DFS search)."""
    if entry_node is None:
        return None
    
    if type(entry_node).__name__ == "SignalEntry":
        return entry_node.side
    
    # Recurse through children
    if hasattr(entry_node, '__dict__'):
        for field_name, field_value in entry_node.__dict__.items():
            if field_name in ['metadata', 'exit_plan', 'return_type']:
                continue
            if isinstance(field_value, list):
                for item in field_value:
                    result = _extract_signal_direction(item)
                    if result:
                        return result
            elif hasattr(field_value, '__dict__'):
                result = _extract_signal_direction(field_value)
                if result:
                    return result
    
    return None


# ────────────────────────────────────────────────────────────────────────────────
# GENOME → PROPOSAL
# ────────────────────────────────────────────────────────────────────────────────

def genome_to_proposal(
    genome: types.StrategyGenome,
    snapshot: Dict[str, Any],
    context: Dict[str, Any],
) -> ProposalCard:
    """
    Transform genome evaluation into ProposalCard.
    
    Args:
        genome: StrategyGenome AST
        snapshot: Market snapshot dict
        context: Execution context dict
    
    Returns:
        ProposalCard (or minimal NOOP card if creation fails)
    """
    # Generate intent
    intent = genome_to_intent(genome, snapshot, context)
    
    # Create MarketSnapshot from dict
    from extensions.protocol.protocol import VolatilityState, MarketRegime
    
    try:
        market = MarketSnapshot(
            symbol=snapshot.get("symbol", "UNKNOWN"),
            ts_ms=snapshot.get("ts_ms", context.get("now_ms", 0)),
            bid=snapshot.get("bid", 0.0),
            ask=snapshot.get("ask", 0.0),
            mid=snapshot.get("mid", 0.0),
            volume_24h=snapshot.get("volume_24h", 0.0),
            volatility_state=VolatilityState(snapshot.get("volatility_state", "normal")),
            market_regime=MarketRegime(snapshot.get("market_regime", "chop")),
            atr_14=snapshot.get("atr_14", 0.0),
            spread_pct=snapshot.get("spread_pct", 0.0),
        )
    except (ValueError, KeyError) as e:
        # Snapshot conversion failed: return minimal NOOP card
        return _create_noop_proposal(intent, context, f"Snapshot conversion failed: {e}")
    
    # Create ProposalContext
    strategy_id = genome.metadata.get("strategy_id", "genome_strategy")
    strategy_name = genome.metadata.get("name", "Genome Strategy")
    now_ms = context.get("now_ms", 0)
    
    proposal_ctx = ProposalContext(
        strategy_id=strategy_id,
        strategy_name=strategy_name,
        run_id=context.get("run_id", "genome_run"),
        correlation_id=context.get("correlation_id", intent.intent_id),
        governance_snapshot=None,
        now_ms=now_ms,
    )
    
    # Use Phase 10 factory
    try:
        proposal = create_proposal(intent, market, proposal_ctx)
        
        if proposal is None:
            # Not an ENTRY intent: return minimal NOOP card
            return _create_noop_proposal(intent, context, "Non-ENTRY intent")
        
        return proposal
    
    except Exception as e:
        # Factory failed: return minimal NOOP card
        return _create_noop_proposal(intent, context, f"Proposal factory failed: {e}")


def _create_noop_proposal(intent: StrategyIntent, context: Dict[str, Any], reason: str) -> ProposalCard:
    """Create minimal NOOP ProposalCard for error cases."""
    now_ms = context.get("now_ms", 0)
    
    return ProposalCard(
        proposal_id="noop_" + intent.intent_id,
        intent_id=intent.intent_id,
        run_id=context.get("run_id", "genome_run"),
        correlation_id=context.get("correlation_id", intent.intent_id),
        strategy_id=intent.strategy_id,
        strategy_name="Genome Strategy (NOOP)",
        symbol="N/A",
        side_pretty="NOOP",
        side_style="neutral",
        size_pretty="0.0",
        rationale_text=reason,
        rationale_sections=[{"label": "error", "value": reason}],
        risk_metrics={"implied_loss_pct": 0.0, "reward_to_risk": 0.0, "max_loss_quote": 0.0},
        exit_plan_view={"stop_loss_price": None, "take_profit_price": None, "time_limit_ms": None, "time_limit_human": None},
        status=ProposalStatus.PENDING,
        created_at_ms=now_ms,
        expires_at_ms=now_ms + 600_000,  # 10 min default
        decided_at_ms=None,
        decided_by=None,
        executed_at_ms=None,
    )
