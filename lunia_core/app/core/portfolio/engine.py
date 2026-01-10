from typing import List, Dict
from .types import (
    PortfolioDefinition, PortfolioType, RiskProfile, 
    AssetCard, PortfolioRule, PortfolioStatus
)

class PortfolioEngine:
    """Logic engine for constructing and managing portfolios."""

    @staticmethod
    def generate_portfolio(
        type: PortfolioType, 
        risk: RiskProfile, 
        capital: float
    ) -> PortfolioDefinition:
        
        assets = []
        rules = PortfolioRule()

        if type == PortfolioType.LONG_TERM:
            rules.rebalance_interval_days = 30
            if risk == RiskProfile.CONSERVATIVE:
                assets = [
                    AssetCard("BTC", 0.60, 0.95, ["Store of value", "High Liquidity"], "L1", "Low Volatility"),
                    AssetCard("ETH", 0.30, 0.90, ["Smart Contract Leader", "Yield Bearing"], "L1", "Medium Volatility"),
                    AssetCard("SOL", 0.10, 0.85, ["High Throughput", "Adoption"], "L1", "Medium Volatility"),
                ]
            elif risk == RiskProfile.AGGRESSIVE:
                 assets = [
                    AssetCard("BTC", 0.40, 0.95, ["Base Layer"], "L1"),
                    AssetCard("ETH", 0.30, 0.90, ["DeFi Hub"], "L1"),
                    AssetCard("SOL", 0.20, 0.85, ["Growth L1"], "L1"),
                    AssetCard("DOGE", 0.10, 0.70, ["Meme/Community"], "Meme", "High Volatility"),
                ]
            else: # Balanced
                 assets = [
                    AssetCard("BTC", 0.50, 0.95, ["Market Leader"], "L1"),
                    AssetCard("ETH", 0.30, 0.90, ["DeFi Hub"], "L1"),
                    AssetCard("SOL", 0.20, 0.85, ["Growth"], "L1"),
                ]
        
        else: # TACTICAL
            rules.rebalance_interval_days = 3
            # Mock tactical selection
            assets = [
                AssetCard("ARB", 0.40, 0.75, ["L2 Momentum"], "L2", "Short term catalyst"),
                AssetCard("OP", 0.40, 0.75, ["L2 Momentum"], "L2", "Short term catalyst"),
                AssetCard("LDO", 0.20, 0.80, ["Yield narrative"], "DeFi", "Merge play"),
            ]

        return PortfolioDefinition(
            id=f"{type.value}_{risk.value}".lower(),
            type=type,
            risk_profile=risk,
            horizon="12 Months" if type == PortfolioType.LONG_TERM else "2 Weeks",
            assets=assets,
            rules=rules,
            status=PortfolioStatus.ACTIVE,
            total_capital_allocation=capital
        )

    @staticmethod
    def validate_weights(assets: List[AssetCard]) -> bool:
        total = sum(a.weight for a in assets)
        return abs(total - 1.0) < 0.001
