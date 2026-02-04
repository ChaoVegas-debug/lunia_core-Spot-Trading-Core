"""
AI Governance Configuration - Single Source of Truth

This module defines the canonical governance configuration for the AI system.
It controls IF, WHEN, and AT WHAT COST AI may be used.

CRITICAL RULES:
- ai_global_enabled defaults to FALSE (opt-in, not opt-out)
- Missing/invalid config → AI DISABLED (fail-closed)
- All values must be serializable and loggable
- No secrets in this config (use env vars for API keys)
"""

from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class AIGovernanceConfig:
    """
    Canonical governance configuration for AI system.
    
    This config is the ONLY source of truth for AI runtime behavior.
    All AI Gateway operations must respect these constraints.
    """
    
    # ========== RUNTIME CONTROL ==========
    
    ai_global_enabled: bool = False
    """
    Global AI kill switch.
    
    - False: ALL AI providers disabled, only logs
    - True: AI enabled (subject to shadow_mode and budget)
    
    DEFAULT: False (opt-in safety)
    """
    
    shadow_mode_default: bool = True
    """
    Default shadow mode for AI inference.
    
    - True: AI runs but outputs not shown to operators (calibration phase)
    - False: AI outputs visible and auditable
    
    DEFAULT: True (trust must be earned)
    """
    
    fast_path_timeout_ms: int = 400
    """
    Timeout for FAST PATH inference (quick triage/sanity check).
    
    HARD LIMIT: Calls exceeding this timeout are killed.
    
    DEFAULT: 400ms (aggressive for low-latency operations)
    """
    
    deep_path_timeout_ms: int = 2000
    """
    Timeout for DEEP PATH inference (contextual reasoning).
    
    HARD LIMIT: Calls exceeding this timeout are killed.
    
    DEFAULT: 2000ms (2 seconds, balances quality vs latency)
    """
    
    circuit_breaker_failures: int = 5
    """
    Number of consecutive failures before circuit breaker opens.
    
    Once open, AI requests are blocked for circuit_breaker_reset_seconds.
    
    DEFAULT: 5 failures
    """
    
    circuit_breaker_reset_seconds: int = 60
    """
    Cooldown period (seconds) before circuit breaker attempts to close.
    
    After this period, circuit breaker enters HALF_OPEN state.
    
    DEFAULT: 60 seconds
    """
    
    # ========== BUDGET GOVERNANCE ==========
    
    daily_budget_usd: float = 5.00
    """
    Maximum USD spend per day (UTC calendar day).
    
    Once exceeded:
    - If hard_stop_on_budget_exceed=True: AI disabled
    - Otherwise: fallback to mock provider
    
    DEFAULT: $5.00 (conservative for testing)
    """
    
    per_signal_budget_usd: float = 0.05
    """
    Maximum USD cost per individual signal analysis.
    
    Prevents single expensive calls from draining budget.
    
    DEFAULT: $0.05 (5 cents per signal)
    """
    
    hard_stop_on_budget_exceed: bool = True
    """
    Behavior when daily budget exceeded.
    
    - True: Immediately disable AI (no fallback)
    - False: Force fallback to mock provider
    
    DEFAULT: True (strict cost control)
    """
    
    budget_warning_ratio: float = 0.8
    """
    Emit warning event when daily spend exceeds this ratio.
    
    Example: 0.8 = warn at 80% of daily budget
    
    DEFAULT: 0.8 (80%)
    """
    
    fallback_provider_on_exceed: str = "mock"
    """
    Provider to use when budget exceeded and hard_stop=False.
    
    MUST be a zero-cost provider (e.g. "mock").
    
    DEFAULT: "mock"
    """
    
    # ========== NOISE GATE (POLICY ONLY) ==========
    # NOTE: Logic not implemented in Phase 8.0, only config definition
    
    min_confidence_threshold: float = 0.5
    """
    [POLICY] Minimum signal confidence to trigger AI analysis.
    
    Signals below this threshold are ignored (noise reduction).
    
    DEFAULT: 0.5 (50% confidence)
    """
    
    cooldown_seconds_per_symbol: int = 300
    """
    [POLICY] Minimum seconds between AI analyses for same symbol.
    
    Prevents spam of similar signals.
    
    DEFAULT: 300 seconds (5 minutes)
    """
    
    regime_aware_filter: bool = False
    """
    [POLICY] Enable regime-specific noise filtering.
    
    If True, noise gate adapts to market regime (trend/range/vol).
    
    DEFAULT: False (not implemented yet)
    """
    
    # ========== PROVIDER ROUTING (POLICY ONLY) ==========
    # NOTE: Only mock provider exists in Phase 8.0
    
    primary_fast: str = "mock"
    """
    [POLICY] Primary provider for FAST PATH.
    
    DEFAULT: "mock" (only available provider in Phase 8.0)
    """
    
    primary_deep: str = "mock"
    """
    [POLICY] Primary provider for DEEP PATH.
    
    DEFAULT: "mock" (only available provider in Phase 8.0)
    """
    
    fallback: str = "mock"
    """
    [POLICY] Fallback provider when primary fails.
    
    DEFAULT: "mock"
    """
    
    # ========== METHODS ==========
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize config to dictionary.
        
        Safe for logging (no secrets).
        """
        return asdict(self)
    
    def to_json(self) -> str:
        """
        Serialize config to JSON string.
        """
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AIGovernanceConfig':
        """
        Deserialize config from dictionary.
        
        Args:
            data: Dictionary with config values
            
        Returns:
            AIGovernanceConfig instance
            
        Note:
            Unknown keys are ignored (forward compatibility).
            Missing keys use defaults.
        """
        # Filter to known fields only
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        
        return cls(**filtered)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'AIGovernanceConfig':
        """
        Deserialize config from JSON string.
        """
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate config for sanity.
        
        Returns:
            (is_valid, error_message)
            
        Validation Rules:
        - Timeouts must be positive
        - Budget must be non-negative
        - Budget warning ratio must be 0.0-1.0
        - Fallback provider must be "mock" (only safe option)
        """
        if self.fast_path_timeout_ms <= 0:
            return False, "fast_path_timeout_ms must be positive"
        
        if self.deep_path_timeout_ms <= 0:
            return False, "deep_path_timeout_ms must be positive"
        
        if self.daily_budget_usd < 0:
            return False, "daily_budget_usd cannot be negative"
        
        if self.per_signal_budget_usd < 0:
            return False, "per_signal_budget_usd cannot be negative"
        
        if not (0.0 <= self.budget_warning_ratio <= 1.0):
            return False, "budget_warning_ratio must be 0.0-1.0"
        
        if self.circuit_breaker_failures <= 0:
            return False, "circuit_breaker_failures must be positive"
        
        if self.circuit_breaker_reset_seconds <= 0:
            return False, "circuit_breaker_reset_seconds must be positive"
        
        # Fallback provider MUST be mock (only zero-cost option in Phase 8.0)
        if self.fallback_provider_on_exceed != "mock":
            return False, f"fallback_provider_on_exceed must be 'mock', got '{self.fallback_provider_on_exceed}'"
        
        return True, None
    
    def sanitized_repr(self) -> str:
        """
        String representation safe for logging.
        
        Omits sensitive fields (none in this config, but future-proof).
        """
        return (
            f"AIGovernanceConfig("
            f"enabled={self.ai_global_enabled}, "
            f"shadow={self.shadow_mode_default}, "
            f"daily_budget=${self.daily_budget_usd:.2f}, "
            f"per_signal=${self.per_signal_budget_usd:.4f})"
        )


# ========== DEFAULT INSTANCE ==========

def load_default_config() -> AIGovernanceConfig:
    """
    Load default governance config.
    
    This is the FAIL-CLOSED default:
    - AI disabled by default
    - Shadow mode enabled
    - Conservative budget
    
    Returns:
        AIGovernanceConfig with safe defaults
    """
    config = AIGovernanceConfig()
    
    is_valid, error = config.validate()
    if not is_valid:
        logger.error(f"Default config invalid: {error}")
        # Return ultra-safe config
        return AIGovernanceConfig(
            ai_global_enabled=False,
            shadow_mode_default=True,
            daily_budget_usd=0.0,  # No spend allowed
            per_signal_budget_usd=0.0
        )
    
    logger.info(f"Loaded default governance config: {config.sanitized_repr()}")
    return config


# ========== FUTURE: DB-BACKED CONFIG ==========
# Phase 8.0: File/env-based config only
# Phase 8.x: Add database-backed config with hot reload

def load_config_from_env() -> AIGovernanceConfig:
    """
    [FUTURE] Load config from environment variables.
    
    Currently returns default config.
    Phase 8.x will implement env var overrides.
    """
    # TODO: Read from env vars (AI_GLOBAL_ENABLED, AI_DAILY_BUDGET_USD, etc.)
    return load_default_config()
