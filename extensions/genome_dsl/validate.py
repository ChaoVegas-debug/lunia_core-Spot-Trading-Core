"""
PHASE 11B — GENOME DSL: Static Validation

Constitutional enforcement per Section 4.1:
- DAG cycle detection (topological sort)
- Whitelist enforcement
- Type and dimension compatibility checking
- CostGate presence verification
- Structural limit enforcement

All violations are deterministic and auditable.
"""

from dataclasses import dataclass
from typing import List, Set, Dict, Any, Optional
from collections import deque
from extensions.genome_dsl import types


# ────────────────────────────────────────────────────────────────────────────────
# VIOLATION CODES (from Compliance Pack Annex)
# ────────────────────────────────────────────────────────────────────────────────

class ViolationCode:
    """Deterministic violation codes from Constitution Annex."""
    DAG_CYCLE = "E_DAG_CYCLE"
    UNKNOWN_NODE = "E_UNKNOWN_NODE"
    DIM_MISMATCH = "E_DIM_MISMATCH"
    TYPE_MISMATCH = "E_TYPE_MISMATCH"
    COMPLEXITY_CAP = "E_COMPLEXITY_CAP"
    COSTGATE_MISSING = "E_COSTGATE_MISSING"
    STRUCTURAL_LIMIT = "E_STRUCTURAL_LIMIT"


@dataclass
class Violation:
    """Single validation violation."""
    code: str
    node_path: str
    severity: str  # "REJECT" | "BLOCK" | "WARN"
    message: str


@dataclass
class ValidationResult:
    """Result of static validation."""
    passed: bool
    violations: List[Violation]
    
    def add_violation(self, code: str, node_path: str, severity: str, message: str):
        """Add a violation and mark validation as failed."""
        self.passed = False
        self.violations.append(Violation(code, node_path, severity, message))


# ────────────────────────────────────────────────────────────────────────────────
# WHITELISTED NODES (from Constitution Section 3.3)
# ────────────────────────────────────────────────────────────────────────────────

WHITELISTED_NODES = {
    # Literals
    "ConstFloat", "ConstInt", "ConstBool", "ConstString",
    # Market Data
    "PriceMid", "PriceBid", "PriceAsk", "SpreadPct", "Volume", "VolatilityState",
    # Indicators
    "SMA", "EMA", "RSI", "ATR", "Highest", "Lowest", "ROC",
    # Comparators
    "GreaterThan", "LessThan", "Equal", "CrossAbove", "CrossBelow",
    # Boolean Logic
    "And", "Or", "Not", "IfThenElse",
    # Gates & Filters
    "RegimeFilter", "CostGate", "TimeWindow",
    # Actions
    "SignalEntry", "SignalExit", "SizingFixed", "SizingATRBased",
    # Root
    "StrategyGenome", "ExitPlanNode",
}


# ────────────────────────────────────────────────────────────────────────────────
# VALIDATION FUNCTIONS
# ────────────────────────────────────────────────────────────────────────────────

def validate_genome(genome: types.StrategyGenome) -> ValidationResult:
    """
    Perform complete static validation per Constitution Section 4.1.
    
    Args:
        genome: Strategy genome to validate
    
    Returns:
        ValidationResult with pass/fail and violations list
    """
    result = ValidationResult(passed=True, violations=[])
    
    # 1. Whitelist enforcement
    _validate_whitelist(genome, result)
    
    # 2. DAG cycle detection
    _validate_dag(genome, result)
    
    # 3. Type checking (basic; full type checking requires interpreter context)
    _validate_types(genome, result)
    
    # 4. Structural limits
    _validate_structural_limits(genome, result)
    
    # 5. CostGate presence
    _validate_costgate_presence(genome, result)
    
    return result


def _validate_whitelist(genome: types.StrategyGenome, result: ValidationResult):
    """Validate all nodes are in whitelist."""
    def check_node(node: Any, path: str):
        if node is None:
            return
        
        node_type = type(node).__name__
        
        if node_type not in WHITELISTED_NODES:
            result.add_violation(
                code=ViolationCode.UNKNOWN_NODE,
                node_path=path,
                severity="REJECT",
                message=f"Unknown node type '{node_type}' at {path}"
            )
            return
        
        # Recursively check child nodes
        if hasattr(node, '__dict__'):
            for field_name, field_value in node.__dict__.items():
                if isinstance(field_value, list):
                    for i, item in enumerate(field_value):
                        check_node(item, f"{path}.{field_name}[{i}]")
                elif hasattr(field_value, '__dict__'):
                    check_node(field_value, f"{path}.{field_name}")
    
    check_node(genome.entry_condition, "entry_condition")
    check_node(genome.exit_condition, "exit_condition")
    check_node(genome.sizing_logic, "sizing_logic")


def _validate_dag(genome: types.StrategyGenome, result: ValidationResult):
    """
    Validate genome is a DAG (no cycles) using topological sort.
    
    Simplified version: check for direct recursion in AST.
    Full DAG validation requires node ID tracking which isn't in current types.
    """
    # For MVP: check that no node references itself directly
    # Full implementation would build dependency graph and use Kahn's algorithm
    visited = set()
    
    def check_cycle(node: Any, path: str, ancestors: Set[int]):
        if node is None:
            return
        
        node_id = id(node)
        
        if node_id in ancestors:
            result.add_violation(
                code=ViolationCode.DAG_CYCLE,
                node_path=path,
                severity="REJECT",
                message=f"Cycle detected: node at {path} references ancestor"
            )
            return
        
        if node_id in visited:
            return  # Already checked this subtree
        
        visited.add(node_id)
        new_ancestors = ancestors | {node_id}
        
        # Recursively check children
        if hasattr(node, '__dict__'):
            for field_name, field_value in node.__dict__.items():
                if isinstance(field_value, list):
                    for i, item in enumerate(field_value):
                        check_cycle(item, f"{path}.{field_name}[{i}]", new_ancestors)
                elif hasattr(field_value, '__dict__'):
                    check_cycle(field_value, f"{path}.{field_name}", new_ancestors)
    
    check_cycle(genome.entry_condition, "entry_condition", set())
    check_cycle(genome.exit_condition, "exit_condition", set())
    check_cycle(genome.sizing_logic, "sizing_logic", set())


def _validate_types(genome: types.StrategyGenome, result: ValidationResult):
    """
    Basic type validation.
    
    Full type checking requires runtime context (e.g., knowing dimension of outputs).
    This validates basic type constraints like And/Or only accepting BOOL children.
    """
    def check_types(node: Any, path: str):
        if node is None:
            return
        
        node_type = type(node).__name__
        
        # Check And/Or only have BOOL children
        if node_type in ["And", "Or"]:
            if hasattr(node, 'nodes'):
                for i, child in enumerate(node.nodes):
                    if hasattr(child, 'return_type') and child.return_type != types.BOOL:
                        result.add_violation(
                            code=ViolationCode.TYPE_MISMATCH,
                            node_path=f"{path}.nodes[{i}]",
                            severity="REJECT",
                            message=f"{node_type} requires BOOL children, got {child.return_type}"
                        )
        
        # Check Not only has BOOL child
        if node_type == "Not":
            if hasattr(node, 'node') and hasattr(node.node, 'return_type'):
                if node.node.return_type != types.BOOL:
                    result.add_violation(
                        code=ViolationCode.TYPE_MISMATCH,
                        node_path=f"{path}.node",
                        severity="REJECT",
                        message=f"Not requires BOOL child, got {node.node.return_type}"
                    )
        
        # Recursively check children
        if hasattr(node, '__dict__'):
            for field_name, field_value in node.__dict__.items():
                if isinstance(field_value, list):
                    for i, item in enumerate(field_value):
                        check_types(item, f"{path}.{field_name}[{i}]")
                elif hasattr(field_value, '__dict__') and field_name not in ['metadata', 'exit_plan']:
                    check_types(field_value, f"{path}.{field_name}")
    
    check_types(genome.entry_condition, "entry_condition")
    check_types(genome.exit_condition, "exit_condition")
    check_types(genome.sizing_logic, "sizing_logic")


def _validate_structural_limits(genome: types.StrategyGenome, result: ValidationResult):
    """
    Validate structural limits per Constitution Section 3.4:
    - Max depth: 7
    - Max nodes: 50
    - Max branches (And/Or): 5
    """
    node_count = [0]  # Mutable counter
    max_depth = [0]  # Track max depth seen
    
    def count_and_check_depth(node: Any, path: str, depth: int):
        if node is None:
            return
        
        node_count[0] += 1
        max_depth[0] = max(max_depth[0], depth)
        
        # Check depth limit
        if depth > 7:
            result.add_violation(
                code=ViolationCode.STRUCTURAL_LIMIT,
                node_path=path,
                severity="REJECT",
                message=f"Depth {depth} exceeds maximum 7 at {path}"
            )
        
        # Check branch limit for And/Or
        node_type = type(node).__name__
        if node_type in ["And", "Or"] and hasattr(node, 'nodes'):
            if len(node.nodes) > 5:
                result.add_violation(
                    code=ViolationCode.STRUCTURAL_LIMIT,
                    node_path=path,
                    severity="REJECT",
                    message=f"{node_type} has {len(node.nodes)} branches, maximum is 5"
                )
        
        # Recursively check children
        if hasattr(node, '__dict__'):
            for field_name, field_value in node.__dict__.items():
                if isinstance(field_value, list):
                    for i, item in enumerate(field_value):
                        count_and_check_depth(item, f"{path}.{field_name}[{i}]", depth + 1)
                elif hasattr(field_value, '__dict__') and field_name not in ['metadata', 'exit_plan']:
                    count_and_check_depth(field_value, f"{path}.{field_name}", depth + 1)
    
    # Count nodes in all three trees
    count_and_check_depth(genome.entry_condition, "entry_condition", 0)
    count_and_check_depth(genome.exit_condition, "exit_condition", 0)
    count_and_check_depth(genome.sizing_logic, "sizing_logic", 0)
    
    # Check total node count
    if node_count[0] > 50:
        result.add_violation(
            code=ViolationCode.STRUCTURAL_LIMIT,
            node_path="genome",
            severity="REJECT",
            message=f"Genome has {node_count[0]} nodes, maximum is 50"
        )


def _validate_costgate_presence(genome: types.StrategyGenome, result: ValidationResult):
    """
    Validate CostGate is present in entry_condition path.
    
    Per Constitution Section 2.7: Every genome MUST include CostGate in entry path.
    """
    found_costgate = [False]  # Mutable flag
    
    def search_costgate(node: Any):
        if node is None:
            return
        
        if type(node).__name__ == "CostGate":
            found_costgate[0] = True
            return
        
        # Recursively search children
        if hasattr(node, '__dict__'):
            for field_name, field_value in node.__dict__.items():
                if isinstance(field_value, list):
                    for item in field_value:
                        search_costgate(item)
                elif hasattr(field_value, '__dict__') and field_name not in ['metadata', 'exit_plan']:
                    search_costgate(field_value)
    
    search_costgate(genome.entry_condition)
    
    if not found_costgate[0]:
        result.add_violation(
            code=ViolationCode.COSTGATE_MISSING,
            node_path="entry_condition",
            severity="REJECT",
            message="Mandatory CostGate not found in entry_condition"
        )
