"""
EPOCH B: Ghost Engine - Deterministic Simulation Foundation
Scaffolding for execution simulation (no real market data yet)
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Tuple

from ...services.proposal.schemas import GhostResult, ThesisDNA


class GhostEngine:
    """
    Ghost Test Engine - EPOCH B Scaffolding
    
    RULES:
    - Deterministic output (NO random())
    - Depends only on thesis_dna + volatility proxy
    - No real market data integration yet
    
    Purpose: UI + architecture readiness for EPOCH C
    """
    
    def __init__(self):
        # Volatility proxies (hardcoded for determinism)
        self.volatility_map = {
            "BTC": 0.045,   # 4.5% daily vol
            "ETH": 0.055,   # 5.5%
            "SOL": 0.075,   # 7.5%
            "LINK": 0.065,  # 6.5%
            "DOGE": 0.120,  # 12%
            "DEFAULT": 0.060
        }
    
    def run_ghost_test(
        self,
        asset: str,
        action: str,
        thesis_dna: Dict,
        confidence_score: float,
        size_scenarios: List[float]
    ) -> List[GhostResult]:
        """
        Run deterministic ghost test simulation
        
        Returns GhostResult for each size scenario
        """
        results = []
        
        # Extract volatility
        vol = self.volatility_map.get(asset, self.volatility_map["DEFAULT"])
        
        # Parse thesis DNA for signal strength
        signal_strength = self._compute_signal_strength(thesis_dna, confidence_score)
        
        for size_pct in size_scenarios:
            result = self._simulate_scenario(
                asset=asset,
                action=action,
                volatility=vol,
                signal_strength=signal_strength,
                confidence=confidence_score,
                size_pct=size_pct
            )
            results.append(result)
        
        return results
    
    def _compute_signal_strength(self, thesis_dna: Dict, confidence: float) -> float:
        """
        Compute aggregate signal strength from thesis DNA
        Deterministic based on chromosome composition
        """
        if not thesis_dna or "chromosomes" not in thesis_dna:
            return 0.5
        
        chromosomes = thesis_dna["chromosomes"]
        
        # Weight each chromosome
        weights = {
            "technical": 0.30,
            "fundamental": 0.25,
            "sentiment": 0.15,
            "flow": 0.20,
            "macro": 0.10
        }
        
        signal = 0.0
        for chrom_name, weight in weights.items():
            genes = chromosomes.get(chrom_name, [])
            if genes:
                # Average gene confidence for this chromosome
                chrom_confidence = sum(g.get("confidence", 0.5) for g in genes) / len(genes)
                signal += chrom_confidence * weight
        
        # Adjust by overall confidence
        signal = (signal + confidence) / 2.0
        
        return max(0.0, min(1.0, signal))
    
    def _simulate_scenario(
        self,
        asset: str,
        action: str,
        volatility: float,
        signal_strength: float,
        confidence: float,
        size_pct: float
    ) -> GhostResult:
        """
        Simulate single size scenario
        Deterministic formula-based (no random)
        """
        # Base ROI from signal strength
        base_roi = signal_strength * 0.15  # 15% max base ROI
        
        # Adjust for volatility (higher vol = higher potential but also risk)
        vol_adjusted_roi = base_roi * (1.0 + (volatility - 0.05))
        
        # Drawdown scales with size and volatility
        base_drawdown = volatility * 2.0  # 2x vol as baseline drawdown
        size_impact = size_pct * 0.3  # larger size = more drawdown
        estimated_drawdown = base_drawdown + size_impact
        
        # Win rate from confidence
        estimated_win_rate = 0.4 + (confidence * 0.4)  # 40-80% range
        
        # Confidence impact (larger sizes reduce confidence)
        confidence_impact = -0.05 * size_pct  # -5% max
        
        # Slippage estimate (scales with size)
        slippage_base = volatility * 0.1  # 10% of vol
        slippage_estimate = slippage_base * (1.0 + size_pct * 2.0)
        
        # Market impact (scales quadratically with size)
        market_impact_estimate = (size_pct ** 1.5) * 0.02  # up to 2%
        
        # Warnings
        warnings = []
        if size_pct > 0.7:
            warnings.append("Large size may cause significant market impact")
        if estimated_drawdown > 0.15:
            warnings.append(f"High drawdown risk: {estimated_drawdown * 100:.1f}%")
        if slippage_estimate > 0.01:
            warnings.append(f"Slippage may exceed 1%: {slippage_estimate * 100:.2f}%")
        
        return GhostResult(
            scenario_size=size_pct,
            estimated_roi=vol_adjusted_roi,
            estimated_drawdown=estimated_drawdown,
            estimated_win_rate=estimated_win_rate,
            confidence_impact=confidence_impact,
            slippage_estimate=slippage_estimate,
            market_impact_estimate=market_impact_estimate,
            warnings=warnings
        )
