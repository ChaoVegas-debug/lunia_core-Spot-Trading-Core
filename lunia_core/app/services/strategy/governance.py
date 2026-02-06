"""
Epoch 9.1: Strategy Governance Contracts

This module defines the HARD CONTRACT for all First-Citizen Governed Strategies.

Architecture:
- StrategyDescriptor: Immutable metadata contract (dataclass)
- GovernedStrategy: Protocol for all governed strategies
- Classification system for strategy intelligence level
- Risk profiling for operating boundary enforcement

Invariants:
- AI execution is FORBIDDEN (ai_execution_allowed HARD FALSE)
- Strategies MUST provide deterministic reasoning
- Metadata is machine-readable and enforceable
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, Optional, FrozenSet, TYPE_CHECKING

if TYPE_CHECKING:
    from .context import StrategyContext
    from .intent import ExecutionIntent


class StrategyClassification(str, Enum):
    """
    Strategy intelligence classification.
    
    Determines how the strategy uses market intelligence.
    """
    DETERMINISTIC_CORE = "deterministic_core"  # Pure logic, no ML, no market_state
    CONTEXT_AWARE = "context_aware"            # Consumes market_state deterministically
    AI_EXPLAINED = "ai_explained"              # AI shadow interpretation enabled


class RiskProfile(str, Enum):
    """
    Strategy risk classification.
    
    Determines operating boundaries and governance constraints.
    """
    SAFE = "safe"          # Conservative, low volatility tolerance
    RISKY = "risky"        # Moderate risk, higher volatility
    DANGEROUS = "dangerous"  # Aggressive, high volatility/leverage


class ConflictReasonCode(str, Enum):
    """
    Conflict classification between core logic and AI interpretation.
    
    Used for audit trail when AI disagrees with strategy decision.
    """
    NO_CONFLICT = "no_conflict"
    REGIME_MISMATCH = "regime_mismatch"      # AI sees different market regime
    RISK_MISMATCH = "risk_mismatch"          # AI risk assessment differs
    LIQUIDITY_WARNING = "liquidity_warning"  # AI warns about liquidity stress
    VOLATILITY_CONCERN = "volatility_concern"  # AI sees excessive volatility
    OTHER = "other"


class ConflictSeverity(str, Enum):
    """
    Conflict severity classification.
    
    Escalates based on market conditions (e.g., DANGEROUS market → HIGH severity).
    """
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class StrategyDescriptor:
    """
    HARD CONTRACT for all governed strategies.
    
    Strategies cannot be instantiated without this metadata.
    This is not documentation—it is enforceable governance.
    
    Invariants:
    - strategy_id must be non-empty
    - version must be semver (enforced in validation)
    - ai_execution_allowed MUST be False (hard floor)
    
    Example:
        descriptor = StrategyDescriptor(
            strategy_id="context_momentum_v1",
            version="1.0.0",
            classification=StrategyClassification.CONTEXT_AWARE,
            risk_profile=RiskProfile.SAFE,
            required_market_state_fields=frozenset([
                "volatility.vol_regime",
                "regime.regime"
            ]),
            allowed_market_regimes=frozenset(["RANGE", "TREND"]),
            max_volatility_regime="MEDIUM"
        )
        descriptor.validate()  # Raises AssertionError if invalid
    """
    
    # Identity
    strategy_id: str
    version: str  # Semver format (e.g., "1.0.0")
    
    # Classification
    classification: StrategyClassification
    risk_profile: RiskProfile
    
    # Market state requirements (dot-notation paths)
    required_market_state_fields: FrozenSet[str] = field(default_factory=frozenset)
    # Examples:
    # - "volatility.atr"
    # - "volatility.vol_regime"
    # - "regime.regime"
    # - "liquidity.spread_pct"
    # - "market_risk_flag"
    
    # Operating boundaries (certification metadata)
    allowed_market_regimes: FrozenSet[str] = field(
        default_factory=lambda: frozenset(["RANGE", "TREND", "BREAKOUT", "UNKNOWN"])
    )
    max_volatility_regime: str = "HIGH"  # UNKNOWN | LOW | MEDIUM | HIGH
    liquidity_tolerance: str = "NORMAL"  # NORMAL | WARNING | CRITICAL
    
    # AI governance (HARD ENFORCEMENT)
    ai_shadow_enabled: bool = True
    ai_execution_allowed: bool = False  # HARD FALSE — AI NEVER executes
    
    def validate(self) -> None:
        """
        Validate descriptor integrity.
        
        Raises:
            AssertionError: If any invariant is violated
        """
        assert self.strategy_id, "strategy_id cannot be empty"
        assert self.version, "version cannot be empty"
        assert "." in self.version, f"version must be semver format (e.g., '1.0.0'), got: {self.version}"
        
        # HARD FLOOR: AI execution is FORBIDDEN
        assert self.ai_execution_allowed is False, (
            "GOVERNANCE VIOLATION: ai_execution_allowed MUST be False. "
            "AI is shadow-only in this architecture."
        )
        
        # Validate enums
        assert isinstance(self.classification, StrategyClassification), (
            f"classification must be StrategyClassification enum, got: {type(self.classification)}"
        )
        assert isinstance(self.risk_profile, RiskProfile), (
            f"risk_profile must be RiskProfile enum, got: {type(self.risk_profile)}"
        )
        
        # Validate volatility regime
        valid_vol_regimes = {"UNKNOWN", "LOW", "MEDIUM", "HIGH"}
        assert self.max_volatility_regime in valid_vol_regimes, (
            f"max_volatility_regime must be one of {valid_vol_regimes}, got: {self.max_volatility_regime}"
        )
        
        # Validate liquidity tolerance
        valid_liq_tolerances = {"NORMAL", "WARNING", "CRITICAL"}
        assert self.liquidity_tolerance in valid_liq_tolerances, (
            f"liquidity_tolerance must be one of {valid_liq_tolerances}, got: {self.liquidity_tolerance}"
        )


class GovernedStrategy(Protocol):
    """
    Protocol for all First-Citizen Strategies.
    
    Enforcement:
    - MUST provide descriptor (StrategyDescriptor)
    - MUST implement evaluate() with deterministic output
    - MUST provide deterministic_reasoning() for audit trail
    
    This is a typing.Protocol, not an ABC, to avoid forcing inheritance.
    Strategies can use composition or inheritance as they prefer.
    
    Example:
        class MyStrategy:
            def __init__(self):
                self._descriptor = StrategyDescriptor(...)
                self._descriptor.validate()
            
            @property
            def descriptor(self) -> StrategyDescriptor:
                return self._descriptor
            
            def evaluate(self, context: StrategyContext) -> Optional[ExecutionIntent]:
                # Deterministic logic here
                ...
            
            def deterministic_reasoning(
                self, context: StrategyContext, intent: Optional[ExecutionIntent]
            ) -> str:
                return "Explanation of decision..."
    """
    
    @property
    def descriptor(self) -> StrategyDescriptor:
        """
        Strategy metadata contract.
        
        Returns:
            Validated StrategyDescriptor
        
        Note:
            Implementations should call descriptor.validate() in __init__
        """
        ...
    
    def evaluate(self, context: StrategyContext) -> Optional[ExecutionIntent]:
        """
        Deterministic evaluation logic.
        
        This is the CORE decision function. It must be:
        - Deterministic: Same inputs → same output
        - Side-effect free: No database writes, no network calls
        - Fast: < 1ms execution time (target)
        
        Args:
            context: Complete market context (L1, L2, L3, market_state)
        
        Returns:
            ExecutionIntent if signal generated, None otherwise
        
        Note:
            Missing market_state should degrade gracefully (return None or use defaults)
        """
        ...
    
    def deterministic_reasoning(
        self,
        context: StrategyContext,
        intent: Optional[ExecutionIntent]
    ) -> str:
        """
        Human-readable explanation of core logic decision.
        
        This is the strategy's OWN explanation, NOT AI-generated.
        Used for:
        - Audit trail
        - AI comparison (core vs AI reasoning)
        - Debugging and forensics
        
        Args:
            context: Same context passed to evaluate()
            intent: Result from evaluate()
        
        Returns:
            Human-readable explanation string
        
        Example:
            "BUY signal: momentum=0.0234, volatility=LOW, regime=TREND"
            "No signal: momentum below threshold (0.0045 < 0.01)"
        """
        ...
