"""
Phase 8.2A: Noise Gate v1
Pre-AI filter to reduce spend and avoid thrash
"""
from __future__ import annotations

import logging
import time
from typing import Dict, Tuple, Optional, List
from collections import deque
from datetime import datetime

logger = logging.getLogger(__name__)


class NoiseGateConfig:
    """Noise Gate configuration knobs"""
    
    def __init__(
        self,
        enabled: bool = True,
        confidence_threshold_default: float = 0.60,
        confidence_threshold_range: float = 0.75,
        confidence_threshold_trend: float = 0.60,
        cooldown_seconds_per_symbol: int = 60,
        novelty_window: int = 20,
        novelty_threshold: float = 0.85,
        regime_aware: bool = True
    ):
        self.enabled = enabled
        self.confidence_threshold_default = confidence_threshold_default
        self.confidence_threshold_range = confidence_threshold_range
        self.confidence_threshold_trend = confidence_threshold_trend
        self.cooldown_seconds_per_symbol = cooldown_seconds_per_symbol
        self.novelty_window = novelty_window
        self.novelty_threshold = novelty_threshold
        self.regime_aware = regime_aware


class NoiseGate:
    """
    Noise Gate v1 — Pre-AI Filter
    
    Purpose: Reduce AI spend by filtering low-value signals before analysis
    
    Rules:
    1. Cooldown: Block if last AI call within cooldown window
    2. Confidence: Block if below regime-specific threshold
    3. Novelty: Block if too similar to recent signals (low information value)
    4. Regime-aware: Use different thresholds based on market regime
    
    HARD LAWS:
    - Noise Gate does NOT affect strategy decisions (post-persistence only)
    - Never blocks persistence to ExecutionJournal
    - Logs all block decisions (structured, no secrets)
    - O(1) amortized per signal
    """
    
    def __init__(self, config: Optional[NoiseGateConfig] = None):
        """
        Initialize noise gate
        
        Args:
            config: Noise gate configuration
        """
        self.config = config or NoiseGateConfig()
        
        # Cooldown tracking: symbol -> last_ai_call_timestamp
        self._last_ai_call: Dict[str, float] = {}
        
        # Novelty tracking: (strategy_id, symbol) -> deque of feature vectors
        self._signal_history: Dict[Tuple[str, str], deque] = {}
        
        # Stats
        self.stats = {
            "total_evaluated": 0,
            "passed": 0,
            "blocked_cooldown": 0,
            "blocked_low_confidence": 0,
            "blocked_low_novelty": 0,
            "blocked_regime": 0
        }
        
        logger.info(f"NoiseGate initialized (enabled={self.config.enabled})")
    
    def should_analyze(
        self,
        strategy_id: str,
        symbol: str,
        signal_type: str,
        confidence: float,
        regime: Optional[str] = None,
        feature_vector: Optional[Dict[str, float]] = None
    ) -> Tuple[bool, str]:
        """
        Determine if signal should be sent to AI for analysis
        
        Args:
            strategy_id: Strategy identifier
            symbol: Trading symbol
            signal_type: BUY/SELL/HOLD
            confidence: Signal strength (0.0-1.0)
            regime: Market regime (None if unavailable)
            feature_vector: Signal features for novelty check (optional)
        
        Returns:
            (should_analyze, block_reason) tuple
            - should_analyze: True if should send to AI, False if blocked
            - block_reason: Explanation if blocked, empty string if passed
        """
        self.stats["total_evaluated"] += 1
        
        if not self.config.enabled:
            self.stats["passed"] += 1
            return True, ""
        
        now = time.time()
        
        # Rule 1: Cooldown
        last_call = self._last_ai_call.get(symbol)
        if last_call is not None:
            elapsed = now - last_call
            if elapsed < self.config.cooldown_seconds_per_symbol:
                self.stats["blocked_cooldown"] += 1
                logger.debug(
                    f"Noise gate BLOCK (cooldown): {strategy_id}:{symbol} "
                    f"(elapsed={elapsed:.1f}s < {self.config.cooldown_seconds_per_symbol}s)"
                )
                return False, "cooldown_active"
        
        # Rule 2: Confidence threshold
        threshold = self._get_confidence_threshold(regime)
        if confidence < threshold:
            self.stats["blocked_low_confidence"] += 1
            logger.debug(
                f"Noise gate BLOCK (low_confidence): {strategy_id}:{symbol} "
                f"(confidence={confidence:.2f} < threshold={threshold:.2f}, regime={regime})"
            )
            return False, "low_confidence"
        
        # Rule 3: Novelty check
        if feature_vector is not None:
            is_novel, novelty_score = self._check_novelty(
                strategy_id,
                symbol,
                feature_vector
            )
            
            if not is_novel:
                self.stats["blocked_low_novelty"] += 1
                logger.debug(
                    f"Noise gate BLOCK (low_novelty): {strategy_id}:{symbol} "
                    f"(novelty_score={novelty_score:.2f} < {1 - self.config.novelty_threshold:.2f})"
                )
                return False, "low_novelty"
        
        # PASS: signal should be analyzed
        self.stats["passed"] += 1
        
        # Record AI call timestamp for cooldown
        self._last_ai_call[symbol] = now
        
        logger.info(
            f"Noise gate PASS: {strategy_id}:{symbol} "
            f"(confidence={confidence:.2f}, regime={regime})"
       )
        
        return True, ""
    
    def _get_confidence_threshold(self, regime: Optional[str]) -> float:
        """
        Get confidence threshold based on market regime
        
        Args:
            regime: Market regime (None, "TREND", "RANGE", etc.)
        
        Returns:
            Confidence threshold
        """
        if not self.config.regime_aware or regime is None:
            return self.config.confidence_threshold_default
        
        regime_thresholds = {
            "RANGE": self.config.confidence_threshold_range,
            "TREND": self.config.confidence_threshold_trend
        }
        
        return regime_thresholds.get(regime.upper(), self.config.confidence_threshold_default)
    
    def _check_novelty(
        self,
        strategy_id: str,
        symbol: str,
        feature_vector: Dict[str, float]
    ) -> Tuple[bool, float]:
        """
        Check if signal is novel compared to recent history
        
        Args:
            strategy_id: Strategy identifier
            symbol: Trading symbol
            feature_vector: Signal features (normalized)
        
        Returns:
            (is_novel, novelty_score) tuple
            - is_novel: True if sufficiently different from history
            - novelty_score: Similarity score (0.0=identical, 1.0=completely different)
        """
        key = (strategy_id, symbol)
        
        # Get or create history deque
        if key not in self._signal_history:
            self._signal_history[key] = deque(maxlen=self.config.novelty_window)
        
        history = self._signal_history[key]
        
        # First signal for this (strategy, symbol) is always novel
        if not history:
            history.append(feature_vector)
            return True, 1.0
        
        # Calculate similarity to recent signals (simple normalized distance)
        max_similarity = 0.0
        
        for historical_features in history:
            similarity = self._compute_similarity(feature_vector, historical_features)
            max_similarity = max(max_similarity, similarity)
        
        # Novel if max similarity < novelty threshold
        is_novel = max_similarity < self.config.novelty_threshold
        novelty_score = 1.0 - max_similarity
        
        # Add to history regardless of novelty (for future comparisons)
        history.append(feature_vector)
        
        return is_novel, novelty_score
    
    def _compute_similarity(
        self,
        vec1: Dict[str, float],
        vec2: Dict[str, float]
    ) -> float:
        """
        Compute similarity between two feature vectors
        
        Uses simple normalized Euclidean distance (not cosine; faster)
        
        Args:
            vec1: First feature vector
            vec2: Second feature vector
        
        Returns:
            Similarity score (0.0=completely different, 1.0=identical)
        """
        # Get common keys
        keys = set(vec1.keys()) & set(vec2.keys())
        
        if not keys:
            return 0.0
        
        # Compute normalized distance
        distance_sum = 0.0
        for key in keys:
            distance_sum += abs(vec1[key] - vec2[key]) ** 2
        
        distance = (distance_sum / len(keys)) ** 0.5
        
        # Convert distance to similarity (inverse)
        # Assume max distance ~2.0 for normalized features
        similarity = max(0.0, 1.0 - (distance / 2.0))
        
        return similarity
    
    def get_stats(self) -> Dict[str, any]:
        """
        Get noise gate statistics
        
        Returns:
            Stats dict with counters and pass rate
        """
        total = self.stats["total_evaluated"]
        return {
            **self.stats,
            "pass_rate": self.stats["passed"] / total if total > 0 else 0.0,
            "block_rate_cooldown": self.stats["blocked_cooldown"] / total if total > 0 else 0.0,
            "block_rate_confidence": self.stats["blocked_low_confidence"] / total if total > 0 else 0.0,
            "block_rate_novelty": self.stats["blocked_low_novelty"] / total if total > 0 else 0.0
        }
    
    def reset_stats(self):
        """Reset statistics counters"""
        self.stats = {
            "total_evaluated": 0,
            "passed": 0,
            "blocked_cooldown": 0,
            "blocked_low_confidence": 0,
            "blocked_low_novelty": 0,
            "blocked_regime": 0
        }
        logger.info("Noise gate stats reset")
    
    def reset_cooldown(self, symbol: Optional[str] = None):
        """
        Reset cooldown state (for manual intervention)
        
        Args:
            symbol: Symbol to reset (None = all symbols)
        """
        if symbol is None:
            self._last_ai_call.clear()
            logger.info("Noise gate cooldown reset (all symbols)")
        else:
            if symbol in self._last_ai_call:
                del self._last_ai_call[symbol]
            logger.info(f"Noise gate cooldown reset: {symbol}")
