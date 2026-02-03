"""
PHASE 11C — GENOME DSL: Deterministic Interpreter (Physics Engine)

Iterative genome evaluator with fail-closed semantics.

CRITICAL RULES:
- NO recursion (topological execution plan)
- NO eval/exec/compile
- NO I/O, network, filesystem
- Deterministic float normalization (8 decimals)
- Fail-closed: errors → NOOP + evidence
- StepBudget guard (hard runtime limit)
- Runtime dimension checks (defense-in-depth)
"""

import math
from typing import Any, Dict, List, Set, Tuple, Optional
from collections import deque
from extensions.genome_dsl import types
from extensions.genome_dsl.types import (
    Dimension, NodeEvidence, DecisionEvidence, VetoFlag
)
from extensions.genome_dsl.canonical import FLOAT_PRECISION


# ────────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ────────────────────────────────────────────────────────────────────────────────

MIN_STEP_BUDGET = 10
STEP_BUDGET_MULTIPLIER = 2
MAX_RATIONALE_LEN = 256


# ────────────────────────────────────────────────────────────────────────────────
# FLOAT NORMALIZATION (Deterministic)
# ────────────────────────────────────────────────────────────────────────────────

def normalize_float(value: float) -> float:
    """Normalize float to 8 decimals for determinism."""
    if math.isnan(value) or math.isinf(value):
        return 0.0  # Fail-safe
    return round(value, FLOAT_PRECISION)


def safe_float(value: Any, fallback: float = 0.0) -> Tuple[float, bool]:
    """
    Convert value to float safely.
    
    Returns:
        (normalized_float, is_fallback)
    """
    try:
        if value is None:
            return fallback, True
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return fallback, True
        return normalize_float(f), False
    except (TypeError, ValueError):
        return fallback, True


# ────────────────────────────────────────────────────────────────────────────────
# DIMENSION METADATA (for runtime checking)
# ────────────────────────────────────────────────────────────────────────────────

def get_dimension(node_type: str) -> Dimension:
    """Get dimension for node type (runtime defense-in-depth)."""
    if node_type in ["PriceMid", "PriceBid", "PriceAsk", "SMA", "EMA", "ATR"]:
        return Dimension.PRICE
    elif node_type in ["RSI", "ROC", "SpreadPct"]:
        return Dimension.OSC
    elif node_type in ["ConstFloat", "ConstInt", "Volume", "Highest", "Lowest", "SizingFixed", "SizingATRBased"]:
        return Dimension.NONE
    else:
        return Dimension.NONE


# ────────────────────────────────────────────────────────────────────────────────
# EXECUTION PLANNING (Topological Sort)
# ────────────────────────────────────────────────────────────────────────────────

def build_execution_plan(genome: types.StrategyGenome) -> Tuple[List[Tuple[str, Any]], Dict[int, str], Optional[str]]:
    """
    Build topological execution plan for required nodes only.
    
    Returns:
        (execution_plan, mem_to_id_mapping, error_code)
        execution_plan: List[(node_id, node)] in evaluation order
        mem_to_id_mapping: Dict[mem_id, node_id] for child resolution
        error_code: None if success, "E_CYCLE" if cycle detected
    """
    # Build global mem_id -> (node_id, node) mapping
    mem_to_id: Dict[int, str] = {}
    id_to_node: Dict[str, Any] = {}
    node_counter = [0]
    
    def collect_node(node: Any):
        """Recursively collect all nodes."""
        if node is None or not hasattr(node, '__dict__'):
            return
        
        mem_id = id(node)
        if mem_id in mem_to_id:
            return  # Already processed
        
        # Assign ID
        node_type = type(node).__name__
        node_id = f"{node_type}_{node_counter[0]}"
        node_counter[0] += 1
        
        mem_to_id[mem_id] = node_id
        id_to_node[node_id] = node
        
        # Recurse children
        for field_name, field_value in node.__dict__.items():
            if field_name in ['metadata', 'exit_plan', 'return_type']:
                continue
            if isinstance(field_value, list):
                for item in field_value:
                    collect_node(item)
            elif hasattr(field_value, '__dict__'):
                collect_node(field_value)
    
    # Collect all nodes
    collect_node(genome.entry_condition)
    collect_node(genome.exit_condition)
    collect_node(genome.sizing_logic)
    
    # Build dependency graph: node_id -> [child_node_ids] (children must be evaluated first)
    dependencies: Dict[str, List[str]] = {nid: [] for nid in id_to_node}
    
    for node_id, node in id_to_node.items():
        if hasattr(node, '__dict__'):
            for field_name, field_value in node.__dict__.items():
                if field_name in ['metadata', 'exit_plan', 'return_type']:
                    continue
                if isinstance(field_value, list):
                    for item in field_value:
                        if item is not None and id(item) in mem_to_id:
                            child_id = mem_to_id[id(item)]  
                            dependencies[node_id].append(child_id)
                elif field_value is not None and hasattr(field_value, '__dict__') and id(field_value) in mem_to_id:
                    child_id = mem_to_id[id(field_value)]
                    dependencies[node_id].append(child_id)
    
    # Topological sort for execution: children first, then parents
    # out_degree: number of children (dependencies) a node has
    out_degree = {nid: len(children) for nid, children in dependencies.items()}
    
    # Start with nodes that have no dependencies (true leaves)
    queue = deque([nid for nid, deg in out_degree.items() if deg == 0])
    queue = deque(sorted(queue))  # Stable order
    
    execution_plan: List[Tuple[str, Any]] = []
    
    while queue:
        current_id = queue.popleft()
        current_node = id_to_node[current_id]
        execution_plan.append((current_id, current_node))
        
        # Find all parents (nodes that depend on current_id) and decrement their out-degree
        for parent_id, children in dependencies.items():
            if current_id in children:
                out_degree[parent_id] -= 1
                if out_degree[parent_id] == 0:
                    queue.append(parent_id)
        
        queue = deque(sorted(queue))  # Stable order
    
    # Check cycle
    if len(execution_plan) != len(id_to_node):
        return [], {}, "E_CYCLE"
    
    return execution_plan, mem_to_id, None



# ────────────────────────────────────────────────────────────────────────────────
# EVALUATOR
# ────────────────────────────────────────────────────────────────────────────────

def evaluate(
    genome: types.StrategyGenome,
    snapshot: Dict[str, Any],
    context: Dict[str, Any],
) -> DecisionEvidence:
    """
    Evaluate genome deterministically (fail-closed).
    
    Args:
        genome: StrategyGenome AST
        snapshot: Market snapshot + indicators (dict)
        context: Execution context (now_ms, governance_level, etc.)
    
    Returns:
        DecisionEvidence with signal, confidence, evidence trace
    """
    now_ms = context.get("now_ms", 0)
    
    # Build execution plan
    execution_plan, mem_to_id, cycle_error = build_execution_plan(genome)
    
    if cycle_error:
        # Fail-closed: cycle detected
        return DecisionEvidence(
            signal="NOOP",
            confidence_raw=0.0,
            sizing_pct=0.0,
            veto_flags=sorted([VetoFlag.CONSTITUTIONAL_VIOLATION]),
            logic_trace=[],
            fallback_count=0,
            constitutional_violations=sorted(["E_DAG_CYCLE"]),
            evaluated_node_count=0,
            step_budget_used=0,
            step_budget_limit=0,
        )
    
    # StepBudget
    step_budget_limit = max(STEP_BUDGET_MULTIPLIER * len(execution_plan), MIN_STEP_BUDGET)
    step_budget_used = 0
    
    # Value store and evidence store
    value_store: Dict[str, Any] = {}
    evidence_store: List[NodeEvidence] = []
    fallback_count = 0
    veto_flags_set: Set[str] = set()
    constitutional_violations_set: Set[str] = set()
    
    # Evaluate nodes in topological order
    for node_id, node in execution_plan:
        step_budget_used += 1
        
        # Check budget
        if step_budget_used > step_budget_limit:
            # Fail-closed: budget exceeded
            veto_flags_set.add(VetoFlag.STEP_BUDGET)
            constitutional_violations_set.add("E_STEP_BUDGET_EXCEEDED")
            evidence_store.append(NodeEvidence(
                node_id="BUDGET_EXCEEDED",
                node_type="SYSTEM",
                inputs={},
                output=None,
                pass_fail=False,
                severity="BLOCK",
                is_fallback=False,
                fallback_reason=None,
                rationale=f"Step budget {step_budget_limit} exceeded",
                timestamp_ms=now_ms,
            ))
            break
        
        # Evaluate node
        output, node_evidence = evaluate_node(
            node_id, node, value_store, snapshot, context, now_ms, mem_to_id
        )
        
        value_store[node_id] = output
        evidence_store.append(node_evidence)
        
        # Track fallbacks and vetos
        if node_evidence.is_fallback:
            fallback_count += 1
        if node_evidence.severity == "BLOCK":
            veto_flags_set.add(VetoFlag.MISSING_DATA)
        if "DIM_MISMATCH" in node_evidence.rationale:
            veto_flags_set.add(VetoFlag.DIMENSION_MISMATCH)
    
    # Extract final signal from entry_condition
    entry_id = find_root_id(genome.entry_condition, execution_plan)
    exit_id = find_root_id(genome.exit_condition, execution_plan)
    sizing_id = find_root_id(genome.sizing_logic, execution_plan)
    
    signal = "NOOP"
    sizing_pct = 0.0
    confidence_raw = 1.0
    
    if entry_id and entry_id in value_store:
        entry_result = value_store[entry_id]
        if isinstance(entry_result, bool) and entry_result:
            signal = "ENTRY"
    
    if exit_id and exit_id in value_store:
        exit_result = value_store[exit_id]
        if isinstance(exit_result, bool) and exit_result:
            signal = "EXIT"
    
    if sizing_id and sizing_id in value_store:
        sizing_result = value_store[sizing_id]
        sizing_pct, _ = safe_float(sizing_result, 0.0)
    
    # Override signal if constitutional violations or veto flags
    if constitutional_violations_set or VetoFlag.STEP_BUDGET in veto_flags_set:
        signal = "NOOP"
        confidence_raw = 0.0
    
    return DecisionEvidence(
        signal=signal,
        confidence_raw=confidence_raw,
        sizing_pct=sizing_pct,
        veto_flags=sorted(list(veto_flags_set)),
        logic_trace=evidence_store,
        fallback_count=fallback_count,
        constitutional_violations=sorted(list(constitutional_violations_set)),
        evaluated_node_count=len(execution_plan),
        step_budget_used=step_budget_used,
        step_budget_limit=step_budget_limit,
    )


def find_root_id(root_node: Any, execution_plan: List[Tuple[str, Any]]) -> Optional[str]:
    """Find node_id for root node in execution plan."""
    if root_node is None:
        return None
    root_mem_id = id(root_node)
    for node_id, node in execution_plan:
        if id(node) == root_mem_id:
            return node_id
    return None


# ────────────────────────────────────────────────────────────────────────────────
# NODE EVALUATOR (Explicit Dispatch)
# ────────────────────────────────────────────────────────────────────────────────

def evaluate_node(
    node_id: str,
    node: Any,
    value_store: Dict[str, Any],
    snapshot: Dict[str, Any],
    context: Dict[str, Any],
    now_ms: int,
    mem_to_id: Dict[int, str],
) -> Tuple[Any, NodeEvidence]:
    """
    Evaluate single node.
    
    Returns:
        (output_value, node_evidence)
    """
    node_type = type(node).__name__
    
    # Dispatch to handler
    if node_type == "ConstFloat":
        return eval_const_float(node, node_id, node_type, now_ms)
    elif node_type == "ConstInt":
        return eval_const_int(node, node_id, node_type, now_ms)
    elif node_type == "ConstBool":
        return eval_const_bool(node, node_id, node_type, now_ms)
    elif node_type == "ConstString":
        return eval_const_string(node, node_id, node_type, now_ms)
    elif node_type == "PriceMid":
        return eval_price_mid(snapshot, node_id, node_type, now_ms)
    elif node_type == "PriceBid":
        return eval_price_bid(snapshot, node_id, node_type, now_ms)
    elif node_type == "PriceAsk":
        return eval_price_ask(snapshot, node_id, node_type, now_ms)
    elif node_type == "SpreadPct":
        return eval_spread_pct(snapshot, node_id, node_type, now_ms)
    elif node_type == "Volume":
        return eval_volume(snapshot, node_id, node_type, now_ms)
    elif node_type in ["SMA", "EMA", "RSI", "ATR", "Highest", "Lowest", "ROC"]:
        return eval_indicator(node, node_type, snapshot, node_id, now_ms)
    elif node_type in ["GreaterThan", "LessThan", "Equal"]:
        return eval_comparator(node, node_type, value_store, node_id, now_ms, mem_to_id)
    elif node_type in ["CrossAbove", "CrossBelow"]:
        return eval_cross(node, node_type, value_store, snapshot, node_id, now_ms)
    elif node_type == "And":
        return eval_and(node, value_store, node_id, node_type, now_ms, mem_to_id)
    elif node_type == "Or":
        return eval_or(node, value_store, node_id, node_type, now_ms, mem_to_id)
    elif node_type == "Not":
        return eval_not(node, value_store, node_id, node_type, now_ms, mem_to_id)
    elif node_type == "IfThenElse":
        return eval_if_then_else(node, value_store, node_id, node_type, now_ms, mem_to_id)
    elif node_type == "RegimeFilter":
        return eval_regime_filter(node, snapshot, node_id, node_type, now_ms)
    elif node_type == "CostGate":
        return eval_cost_gate(node, value_store, snapshot, node_id, node_type, now_ms, mem_to_id)
    elif node_type == "TimeWindow":
        return eval_time_window(node, context, node_id, node_type, now_ms)
    elif node_type in ["SignalEntry", "SignalExit"]:
        return eval_signal(node, node_type, node_id, now_ms)
    elif node_type in ["SizingFixed", "SizingATRBased"]:
        return eval_sizing(node, node_type, snapshot, node_id, now_ms)
    else:
        # Unknown node: fail-safe
        return None, NodeEvidence(
            node_id=node_id,
            node_type=node_type,
            inputs={},
            output=None,
            pass_fail=False,
            severity="BLOCK",
            is_fallback=False,
            fallback_reason=None,
            rationale=f"Unknown node type: {node_type}",
            timestamp_ms=now_ms,
        )


# ────────────────────────────────────────────────────────────────────────────────
# NODE HANDLERS (Explicit, No Reflection)
# ────────────────────────────────────────────────────────────────────────────────

def eval_const_float(node, node_id, node_type, now_ms):
    val = normalize_float(node.value)
    return val, NodeEvidence(
        node_id=node_id, node_type=node_type, inputs={}, output=val,
        pass_fail=None, severity="INFO", is_fallback=False, fallback_reason=None,
        rationale=f"Constant: {val}", timestamp_ms=now_ms
    )

def eval_const_int(node, node_id, node_type, now_ms):
    val = float(node.value)
    return val, NodeEvidence(
        node_id=node_id, node_type=node_type, inputs={}, output=val,
        pass_fail=None, severity="INFO", is_fallback=False, fallback_reason=None,
        rationale=f"Constant: {val}", timestamp_ms=now_ms
    )

def eval_const_bool(node, node_id, node_type, now_ms):
    val = node.value
    return val, NodeEvidence(
        node_id=node_id, node_type=node_type, inputs={}, output=val,
        pass_fail=None, severity="INFO", is_fallback=False, fallback_reason=None,
        rationale=f"Constant: {val}", timestamp_ms=now_ms
    )

def eval_const_string(node, node_id, node_type, now_ms):
    val = node.value
    return val, NodeEvidence(
        node_id=node_id, node_type=node_type, inputs={}, output=val,
        pass_fail=None, severity="INFO", is_fallback=False, fallback_reason=None,
        rationale=f"Constant: '{val}'", timestamp_ms=now_ms
    )

def eval_price_mid(snapshot, node_id, node_type, now_ms):
    val, is_fb = safe_float(snapshot.get("mid"), 0.0)
    severity = "WARN" if is_fb else "INFO"
    fb_reason = "MISSING_MID_PRICE" if is_fb else None
    return val, NodeEvidence(
        node_id=node_id, node_type=node_type, inputs={"snapshot_mid": snapshot.get("mid")},
        output=val, pass_fail=None, severity=severity, is_fallback=is_fb,
        fallback_reason=fb_reason, rationale=f"PriceMid: {val}", timestamp_ms=now_ms
    )

def eval_price_bid(snapshot, node_id, node_type, now_ms):
    val, is_fb = safe_float(snapshot.get("bid"), 0.0)
    severity = "WARN" if is_fb else "INFO"
    fb_reason = "MISSING_BID_PRICE" if is_fb else None
    return val, NodeEvidence(
        node_id=node_id, node_type=node_type, inputs={"snapshot_bid": snapshot.get("bid")},
        output=val, pass_fail=None, severity=severity, is_fallback=is_fb,
        fallback_reason=fb_reason, rationale=f"PriceBid: {val}", timestamp_ms=now_ms
    )

def eval_price_ask(snapshot, node_id, node_type, now_ms):
    val, is_fb = safe_float(snapshot.get("ask"), 0.0)
    severity = "WARN" if is_fb else "INFO"
    fb_reason = "MISSING_ASK_PRICE" if is_fb else None
    return val, NodeEvidence(
        node_id=node_id, node_type=node_type, inputs={"snapshot_ask": snapshot.get("ask")},
        output=val, pass_fail=None, severity=severity, is_fallback=is_fb,
        fallback_reason=fb_reason, rationale=f"PriceAsk: {val}", timestamp_ms=now_ms
    )

def eval_spread_pct(snapshot, node_id, node_type, now_ms):
    val, is_fb = safe_float(snapshot.get("spread_pct"), 0.0)
    severity = "WARN" if is_fb else "INFO"
    fb_reason = "MISSING_SPREAD" if is_fb else None
    return val, NodeEvidence(
        node_id=node_id, node_type=node_type, inputs={"snapshot_spread_pct": snapshot.get("spread_pct")},
        output=val, pass_fail=None, severity=severity, is_fallback=is_fb,
        fallback_reason=fb_reason, rationale=f"Spread: {val}%", timestamp_ms=now_ms
    )

def eval_volume(snapshot, node_id, node_type, now_ms):
    val, is_fb = safe_float(snapshot.get("volume_24h"), 0.0)
    severity = "WARN" if is_fb else "INFO"
    fb_reason = "MISSING_VOLUME" if is_fb else None
    return val, NodeEvidence(
        node_id=node_id, node_type=node_type, inputs={"snapshot_volume": snapshot.get("volume_24h")},
        output=val, pass_fail=None, severity=severity, is_fallback=is_fb,
        fallback_reason=fb_reason, rationale=f"Volume: {val}", timestamp_ms=now_ms
    )

def eval_indicator(node, node_type, snapshot, node_id, now_ms):
    """Evaluate indicator from snapshot (pre-computed)."""
    # Map node type to snapshot key
    if node_type == "RSI":
        key = f"rsi_{node.window}"
        fallback = 50.0  # Neutral
    elif node_type == "SMA":
        key = f"sma_{node.window}"
        fallback = snapshot.get("mid", 0.0)  # Use current price
    elif node_type == "EMA":
        key = f"ema_{node.window}"
        fallback = snapshot.get("mid", 0.0)
    elif node_type == "ATR":
        key = f"atr_{node.window}"
        fallback = 0.0
    elif node_type in ["Highest", "Lowest", "ROC"]:
        # These would require history; fallback
        fallback = 0.0
        key = None
    else:
        fallback = 0.0
        key = None
    
    if key and key in snapshot:
        val, is_fb = safe_float(snapshot[key], fallback)
    else:
        val = fallback
        is_fb = True
    
    severity = "WARN" if is_fb else "INFO"
    fb_reason = "HISTORY_UNAVAILABLE" if is_fb else None
    rationale = f"{node_type}({getattr(node, 'window', '?')}): {val}"
    
    return val, NodeEvidence(
        node_id=node_id, node_type=node_type,
        inputs={"snapshot_key": key, "snapshot_value": snapshot.get(key) if key else None},
        output=val, pass_fail=None, severity=severity, is_fallback=is_fb,
        fallback_reason=fb_reason, rationale=rationale[:MAX_RATIONALE_LEN], timestamp_ms=now_ms
    )

def eval_comparator(node, node_type, value_store, node_id, now_ms, mem_to_id):
    """Evaluate comparator (GT/LT/EQ) with dimension checking."""
    left_id = find_child_id(node.left, mem_to_id)
    right_id = find_child_id(node.right, mem_to_id)
    
    left_val = value_store.get(left_id, 0.0)
    right_val = value_store.get(right_id, 0.0)
    
    left_float, _ = safe_float(left_val, 0.0)
    right_float, _ = safe_float(right_val, 0.0)
    
    # Runtime dimension check (defense-in-depth)
    left_type = type(node.left).__name__ if hasattr(node, 'left') else "Unknown"
    right_type = type(node.right).__name__ if hasattr(node, 'right') else "Unknown"
    left_dim = get_dimension(left_type)
    right_dim = get_dimension(right_type)
    
    dim_mismatch = False
    if left_dim != Dimension.NONE and right_dim != Dimension.NONE and left_dim != right_dim:
        dim_mismatch = True
    
    if dim_mismatch:
        result = False
        severity = "BLOCK"
        rationale = f"DIM_MISMATCH: {left_type}({left_dim.value}) vs {right_type}({right_dim.value})"
    else:
        if node_type == "GreaterThan":
            result = left_float > right_float
        elif node_type == "LessThan":
            result = left_float < right_float
        elif node_type == "Equal":
            result = abs(left_float - right_float) < 1e-8
        else:
            result = False
        
        severity = "INFO"
        rationale = f"{node_type}: {left_float} vs {right_float} → {result}"
    
    return result, NodeEvidence(
        node_id=node_id, node_type=node_type,
        inputs={"left": left_float, "right": right_float},
        output=result, pass_fail=result, severity=severity, is_fallback=False,
        fallback_reason=None, rationale=rationale[:MAX_RATIONALE_LEN], timestamp_ms=now_ms
    )

def eval_cross(node, node_type, value_store, snapshot, node_id, now_ms):
    """Evaluate CrossAbove/CrossBelow (requires previous values)."""
    # For MVP: use snapshot "previous" field if available, else fallback to False
    result = False  # Fail-safe: no cross
    severity = "WARN"
    rationale = f"{node_type}: Requires history (fallback False)"
    
    return result, NodeEvidence(
        node_id=node_id, node_type=node_type, inputs={}, output=result,
        pass_fail=result, severity=severity, is_fallback=True,
        fallback_reason="HISTORY_UNAVAILABLE", rationale=rationale[:MAX_RATIONALE_LEN],
        timestamp_ms=now_ms
    )

def eval_and(node, value_store, node_id, node_type, now_ms, mem_to_id):
    """Evaluate AND of child nodes."""
    results = []
    for child in node.nodes:
        child_id = find_child_id(child, mem_to_id)
        child_val = value_store.get(child_id, False)
        results.append(bool(child_val))
    
    result = all(results)
    rationale = f"AND({len(results)} children) → {result}"
    
    return result, NodeEvidence(
        node_id=node_id, node_type=node_type, inputs={"children": results},
        output=result, pass_fail=result, severity="INFO", is_fallback=False,
        fallback_reason=None, rationale=rationale[:MAX_RATIONALE_LEN], timestamp_ms=now_ms
    )

def eval_or(node, value_store, node_id, node_type, now_ms, mem_to_id):
    """Evaluate OR of child nodes."""
    results = []
    for child in node.nodes:
        child_id = find_child_id(child, mem_to_id)
        child_val = value_store.get(child_id, False)
        results.append(bool(child_val))
    
    result = any(results)
    rationale = f"OR({len(results)} children) → {result}"
    
    return result, NodeEvidence(
        node_id=node_id, node_type=node_type, inputs={"children": results},
        output=result, pass_fail=result, severity="INFO", is_fallback=False,
        fallback_reason=None, rationale=rationale[:MAX_RATIONALE_LEN], timestamp_ms=now_ms
    )

def eval_not(node, value_store, node_id, node_type, now_ms, mem_to_id):
    """Evaluate NOT of child node."""
    child_id = find_child_id(node.node, mem_to_id)
    child_val = bool(value_store.get(child_id, False))
    result = not child_val
    rationale = f"NOT({child_val}) → {result}"
    
    return result, NodeEvidence(
        node_id=node_id, node_type=node_type, inputs={"child": child_val},
        output=result, pass_fail=result, severity="INFO", is_fallback=False,
        fallback_reason=None, rationale=rationale[:MAX_RATIONALE_LEN], timestamp_ms=now_ms
    )

def eval_if_then_else(node, value_store, node_id, node_type, now_ms, mem_to_id):
    """Evaluate IfThenElse conditional."""
    cond_id = find_child_id(node.condition, mem_to_id)
    cond_val = bool(value_store.get(cond_id, False))
    
    if cond_val:
        then_id = find_child_id(node.then_node, mem_to_id)
        result = value_store.get(then_id, 0.0)
        branch = "then"
    else:
        else_id = find_child_id(node.else_node, mem_to_id)
        result = value_store.get(else_id, 0.0)
        branch = "else"
    
    rationale = f"IfThenElse: {branch} branch → {result}"
    
    return result, NodeEvidence(
        node_id=node_id, node_type=node_type,
        inputs={"condition": cond_val, "branch": branch},
        output=result, pass_fail=None, severity="INFO", is_fallback=False,
        fallback_reason=None, rationale=rationale[:MAX_RATIONALE_LEN], timestamp_ms=now_ms
    )

def eval_regime_filter(node, snapshot, node_id, node_type, now_ms):
    """Evaluate regime filter."""
    regime = snapshot.get("market_regime", "unknown")
    regime_str = regime.value if hasattr(regime, 'value') else str(regime)
    expected = node.regime_value
    result = regime_str == expected
    rationale = f"Regime: {regime_str} == {expected} → {result}"
    
    return result, NodeEvidence(
        node_id=node_id, node_type=node_type,
        inputs={"regime": regime_str, "expected": expected},
        output=result, pass_fail=result, severity="INFO", is_fallback=False,
        fallback_reason=None, rationale=rationale[:MAX_RATIONALE_LEN], timestamp_ms=now_ms
    )

def eval_cost_gate(node, value_store, snapshot, node_id, node_type, now_ms, mem_to_id):
    """Evaluate cost gate."""
    profit_id = find_child_id(node.expected_profit, mem_to_id)
    profit, _ = safe_float(value_store.get(profit_id, 0.0), 0.0)
    
    # Estimated cost: use spread as proxy
    spread_pct, _ = safe_float(snapshot.get("spread_pct", 0.01), 0.01)
    estimated_cost = spread_pct * 2.0  # Round-trip
    
    multiplier = node.cost_multiplier
    threshold = estimated_cost * multiplier
    
    result = profit >= threshold
    rationale = f"CostGate: {profit} >= {threshold} (K={multiplier}) → {result}"
    
    return result, NodeEvidence(
        node_id=node_id, node_type=node_type,
        inputs={"profit": profit, "cost": estimated_cost, "multiplier": multiplier},
        output=result, pass_fail=result, severity="INFO", is_fallback=False,
        fallback_reason=None, rationale=rationale[:MAX_RATIONALE_LEN], timestamp_ms=now_ms
    )

def eval_time_window(node, context, node_id, node_type, now_ms):
    """Evaluate time window."""
    current_ms = context.get("now_ms", now_ms)
    start_ms = node.start_ms
    end_ms = node.end_ms
    result = start_ms <= current_ms <= end_ms
    rationale = f"TimeWindow: {start_ms} <= {current_ms} <= {end_ms} → {result}"
    
    return result, NodeEvidence(
        node_id=node_id, node_type=node_type,
        inputs={"now_ms": current_ms, "start_ms": start_ms, "end_ms": end_ms},
        output=result, pass_fail=result, severity="INFO", is_fallback=False,
        fallback_reason=None, rationale=rationale[:MAX_RATIONALE_LEN], timestamp_ms=now_ms
    )

def eval_signal(node, node_type, node_id, now_ms):
    """Evaluate signal node (Entry/Exit)."""
    if node_type == "SignalEntry":
        side = node.side
        confidence = node.confidence
        rationale = f"SignalEntry: {side} (confidence={confidence})"
    else:
        reason = node.reason
        rationale = f"SignalExit: {reason}"
    
    return True, NodeEvidence(
        node_id=node_id, node_type=node_type, inputs={}, output=True,
        pass_fail=True, severity="INFO", is_fallback=False, fallback_reason=None,
        rationale=rationale[:MAX_RATIONALE_LEN], timestamp_ms=now_ms
    )

def eval_sizing(node, node_type, snapshot, node_id, now_ms):
    """Evaluate sizing node."""
    if node_type == "SizingFixed":
        result = node.percent
        rationale = f"SizingFixed: {result}%"
    else:  # SizingATRBased
        atr, _ = safe_float(snapshot.get("atr_14", 0.0), 0.0)
        result = atr * node.atr_multiple
        rationale = f"SizingATRBased: ATR({atr}) * {node.atr_multiple} = {result}%"
    
    return result, NodeEvidence(
        node_id=node_id, node_type=node_type, inputs={}, output=result,
        pass_fail=None, severity="INFO", is_fallback=False, fallback_reason=None,
        rationale=rationale[:MAX_RATIONALE_LEN], timestamp_ms=now_ms
    )


def find_child_id(child_node: Any, mem_to_id: Dict[int, str]) -> Optional[str]:
    """Find node_id for a child node using memory ID mapping."""
    if child_node is None:
        return None
    child_mem_id = id(child_node)
    return mem_to_id.get(child_mem_id, None)
