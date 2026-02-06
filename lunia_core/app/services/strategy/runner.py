"""
Epoch 9.2: Strategy Runner — The Engine

Responsibilities:
- Run multiple GovernedStrategy instances deterministically
- Provide isolation (one strategy failure doesn't crash the loop)
- Track time budgets (soft limits with warnings)
- Ensure context immutability
- Collect IntentProposals from all strategies
- Provide observability metrics

Safety Guarantees:
- Context is immutable (deepcopy per strategy)
- Failures are isolated and logged
- Time budgets are soft (warnings only, never kill)
- Execution order is deterministic
- Zero side effects (pure function)
"""
import time
import logging
import copy
from typing import List, Dict, Union
from dataclasses import dataclass, field

from .governance import GovernedStrategy
from .models import StrategyContext, IntentProposal

logger = logging.getLogger(__name__)


@dataclass
class StrategyRunnerConfig:
    """
    Configuration for StrategyRunner behavior.
    
    All defaults bias toward safety and observability.
    """
    soft_timeout_ms: int = 5  # Soft limit per strategy (warning only)
    total_budget_ms: int = 50  # Total soft budget for all strategies
    enable_timing: bool = True  # Track per-strategy timing
    enable_deepcopy: bool = True  # Deepcopy context for immutability


@dataclass
class StrategyRunMetrics:
    """
    In-memory metrics for StrategyRunner observability.
    
    These are lightweight counters for monitoring.
    """
    strategies_run_total: int = 0
    strategies_failed_total: int = 0
    strategies_timeout_soft_total: int = 0
    intents_emitted_total: int = 0
    
    # Per-strategy breakdown (optional)
    per_strategy_timings: Dict[str, List[float]] = field(default_factory=dict)
    per_strategy_failures: Dict[str, int] = field(default_factory=dict)


class StrategyRunner:
    """
    Deterministic strategy execution engine.
    
    Runs multiple GovernedStrategy instances in a deterministic order,
    collects their IntentProposals, and provides isolation guarantees.
    
    Features:
    - **Isolation**: try/except per strategy (one failure doesn't crash loop)
    - **Immutability**: deepcopy context per strategy (prevents mutation)
    - **Time Budgets**: soft limits with warnings (never kills strategies)
    - **Determinism**: stable execution order
    - **Observability**: metrics and structured logging
    
    Usage:
        runner = StrategyRunner(strategies=[strat1, strat2, strat3])
        intents = runner.run_all(context)
    """
    
    def __init__(
        self,
        strategies: List[GovernedStrategy],
        config: Union[StrategyRunnerConfig, None] = None
    ):
        """
        Initialize runner with strategy list and config.
        
        Args:
            strategies: List of GovernedStrategy instances (deterministic order)
            config: Optional configuration (uses safe defaults if None)
        """
        self.strategies = strategies
        self.config = config or StrategyRunnerConfig()
        self.metrics = StrategyRunMetrics()
        
        # Validate strategies
        for i, strategy in enumerate(self.strategies):
            if not hasattr(strategy, 'descriptor'):
                raise ValueError(
                    f"Strategy at index {i} does not have 'descriptor' property "
                    f"(GovernedStrategy protocol violation)"
                )
            if not hasattr(strategy, 'evaluate'):
                raise ValueError(
                    f"Strategy at index {i} does not have 'evaluate' method "
                    f"(GovernedStrategy protocol violation)"
                )
    
    def run_all(self, context: StrategyContext) -> List[IntentProposal]:
        """
        Run all strategies and collect IntentProposals.
        
        Execution guarantees:
        - Deterministic order (strategies list is stable)
        - Isolation (try/except per strategy)
        - Immutability (context is deepcopied per strategy)
        - Time budget tracking (soft warnings only)
        
        Args:
            context: Immutable strategy context (snapshot + market_state)
        
        Returns:
            List of IntentProposals from all successful strategies
            (may be empty if all strategies fail or return None)
        """
        intents: List[IntentProposal] = []
        start_time_total = time.perf_counter() if self.config.enable_timing else None
        
        for strategy in self.strategies:
            strategy_id = strategy.descriptor.strategy_id
            
            # Create immutable copy of context (prevent mutation)
            if self.config.enable_deepcopy:
                try:
                    strategy_context = copy.deepcopy(context)
                except Exception as e:
                    logger.warning(
                        f"Failed to deepcopy context for strategy {strategy_id}: {e}. "
                        f"Using original context (mutation risk)."
                    )
                    strategy_context = context
            else:
                strategy_context = context
            
            # Run strategy with isolation
            start_time = time.perf_counter() if self.config.enable_timing else None
            
            try:
                intent = strategy.evaluate(strategy_context)
                
                # Track timing
                if self.config.enable_timing and start_time is not None:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    
                    # Record timing
                    if strategy_id not in self.metrics.per_strategy_timings:
                        self.metrics.per_strategy_timings[strategy_id] = []
                    self.metrics.per_strategy_timings[strategy_id].append(elapsed_ms)
                    
                    # Check soft timeout
                    if elapsed_ms > self.config.soft_timeout_ms:
                        self.metrics.strategies_timeout_soft_total += 1
                        logger.warning(
                            f"Strategy {strategy_id} exceeded soft timeout: "
                            f"{elapsed_ms:.2f}ms > {self.config.soft_timeout_ms}ms "
                            f"(continuing execution)"
                        )
                
                # Collect intent if present
                if intent is not None:
                    intents.append(intent)
                    self.metrics.intents_emitted_total += 1
                
                self.metrics.strategies_run_total += 1
                
                logger.debug(
                    f"Strategy {strategy_id} executed successfully "
                    f"(intent={'emitted' if intent else 'None'})"
                )
            
            except Exception as e:
                # Isolation: log error and continue
                self.metrics.strategies_failed_total += 1
                
                if strategy_id not in self.metrics.per_strategy_failures:
                    self.metrics.per_strategy_failures[strategy_id] = 0
                self.metrics.per_strategy_failures[strategy_id] += 1
                
                logger.error(
                    f"Strategy {strategy_id} raised exception (isolated): {e}",
                    exc_info=True
                )
                
                # Continue to next strategy (isolation guarantee)
                continue
        
        # Check total budget (informational only)
        if self.config.enable_timing and start_time_total is not None:
            total_elapsed_ms = (time.perf_counter() - start_time_total) * 1000
            if total_elapsed_ms > self.config.total_budget_ms:
                logger.warning(
                    f"Total runner execution exceeded soft budget: "
                    f"{total_elapsed_ms:.2f}ms > {self.config.total_budget_ms}ms"
                )
        
        return intents
    
    def get_metrics(self) -> Dict:
        """
        Get current metrics snapshot.
        
        Returns:
            Dictionary with metric names and values
        """
        return {
            "strategies_run_total": self.metrics.strategies_run_total,
            "strategies_failed_total": self.metrics.strategies_failed_total,
            "strategies_timeout_soft_total": self.metrics.strategies_timeout_soft_total,
            "intents_emitted_total": self.metrics.intents_emitted_total,
            "per_strategy_failures": dict(self.metrics.per_strategy_failures),
            "per_strategy_avg_timing_ms": {
                strategy_id: sum(timings) / len(timings) if timings else 0.0
                for strategy_id, timings in self.metrics.per_strategy_timings.items()
            }
        }
    
    def reset_metrics(self):
        """Reset all metrics to zero (useful for testing)"""
        self.metrics = StrategyRunMetrics()
