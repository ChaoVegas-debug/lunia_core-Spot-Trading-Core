from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Optional

class PortfolioType(str, Enum):
    LONG_TERM = "LONG_TERM"
    TACTICAL = "TACTICAL"

class RiskProfile(str, Enum):
    CONSERVATIVE = "CONSERVATIVE"
    BALANCED = "BALANCED"
    AGGRESSIVE = "AGGRESSIVE"

class PortfolioStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DE_RISKING = "DE_RISKING"

@dataclass
class AssetCard:
    symbol: str
    weight: float
    confidence: float
    reason: List[str]
    sector: str = "General"
    risk_note: str = ""

@dataclass
class PortfolioRule:
    entry_mode: str = "IMMEDIATE"
    rebalance_interval_days: int = 7
    profit_take_pct: float = 0.20
    stop_loss_pct: float = 0.10

@dataclass
class PortfolioDefinition:
    id: str
    type: PortfolioType
    risk_profile: RiskProfile
    horizon: str
    assets: List[AssetCard]
    rules: PortfolioRule
    status: PortfolioStatus = PortfolioStatus.ACTIVE
    base_currency: str = "USDT"
    total_capital_allocation: float = 0.0

    last_rebalanced_at: Optional[float] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "risk_profile": self.risk_profile.value,
            "horizon": self.horizon,
            "assets": [
                {
                    "symbol": a.symbol,
                    "weight": a.weight,
                    "confidence": a.confidence,
                    "reason": a.reason,
                    "sector": a.sector,
                    "risk_note": a.risk_note
                } for a in self.assets
            ],
            "rules": {
                "entry_mode": self.rules.entry_mode,
                "rebalance_interval_days": self.rules.rebalance_interval_days,
                "profit_take_pct": self.rules.profit_take_pct,
                "stop_loss_pct": self.rules.stop_loss_pct
            },
            "status": self.status.value,
            "base_currency": self.base_currency,
            "total_capital_allocation": self.total_capital_allocation,
            "last_rebalanced_at": self.last_rebalanced_at
        }
