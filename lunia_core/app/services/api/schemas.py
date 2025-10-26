"""Pydantic schemas for the Flask API."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class TradeRequest(BaseModel):
    symbol: str = Field(..., description="Trading pair symbol, e.g. BTCUSDT")
    side: str = Field(..., description="Order side BUY or SELL")
    qty: float = Field(..., gt=0, description="Quantity to trade")

    @model_validator(mode="before")
    @classmethod
    def validate_fields(cls, values: Any) -> Any:
        if isinstance(values, dict):
            side = values.get("side", "").upper()
            if side not in {"BUY", "SELL"}:
                raise ValueError("side must be BUY or SELL")
            values["side"] = side
            values["symbol"] = values.get("symbol", "").upper()
            if "type" in values and isinstance(values["type"], str):
                values["type"] = values["type"].upper()
        return values


class SignalPayload(BaseModel):
    symbol: str = Field(...)
    side: str = Field(...)
    qty: float = Field(..., gt=0)

    @model_validator(mode="before")
    @classmethod
    def normalize(cls, values: Any) -> Any:
        if isinstance(values, dict):
            values["side"] = values.get("side", "").upper()
            values["symbol"] = values.get("symbol", "").upper()
            if values["side"] not in {"BUY", "SELL"}:
                raise ValueError("side must be BUY or SELL")
        return values


class SignalsEnvelope(BaseModel):
    signals: List[SignalPayload]
    enable: Dict[str, int] = Field(default_factory=lambda: {"SPOT": 1})


class FuturesTradeRequest(TradeRequest):
    leverage: float = Field(1.0, gt=0, description="Leverage multiplier")
    type: str = Field("MARKET", description="Order type for futures")


class PortfolioPosition(BaseModel):
    symbol: str
    quantity: float
    average_price: float
    unrealized_pnl: float


class PortfolioSnapshot(BaseModel):
    realized_pnl: float
    unrealized_pnl: float
    positions: List[PortfolioPosition]
    equity_usd: float


class BalanceEntry(BaseModel):
    asset: str
    free: float
    locked: float


class BalancesResponse(BaseModel):
    balances: List[BalanceEntry]


class OpsState(BaseModel):
    auto_mode: bool
    global_stop: bool
    trading_on: bool
    agent_on: bool
    arb_on: bool
    sched_on: bool
    manual_override: bool
    manual_strategy: Optional[Dict[str, Any]]
    scalp: Dict[str, float]
    arb: Dict[str, Any]
    spot: Dict[str, Any]
    reserves: Dict[str, float]
    ops: Dict[str, Any]

    class Config:
        extra = "allow"


class OpsStateUpdate(BaseModel):
    auto_mode: Optional[bool] = None
    global_stop: Optional[bool] = None
    trading_on: Optional[bool] = None
    agent_on: Optional[bool] = None
    arb_on: Optional[bool] = None
    sched_on: Optional[bool] = None
    manual_override: Optional[bool] = None
    manual_strategy: Optional[Dict[str, Any]] = None
    scalp: Optional[Dict[str, float]] = None
    arb: Optional[Dict[str, Any]] = None
    spot: Optional[Dict[str, Any]] = None
    reserves: Optional[Dict[str, float]] = None
    ops: Optional[Dict[str, Any]] = None

    class Config:
        extra = "allow"


class CapitalRequest(BaseModel):
    cap_pct: float = Field(..., ge=0.0, le=1.0)


class StrategyWeightsRequest(BaseModel):
    weights: Dict[str, float]
    enabled: Optional[bool] = None


class ReserveUpdateRequest(BaseModel):
    portfolio: Optional[float]
    arbitrage: Optional[float]


class SpotRiskUpdate(BaseModel):
    max_positions: Optional[int]
    max_trade_pct: Optional[float]
    risk_per_trade_pct: Optional[float]
    max_symbol_exposure_pct: Optional[float]
    tp_pct_default: Optional[float]
    sl_pct_default: Optional[float]


class ResearchRequest(BaseModel):
    pairs: Optional[List[str]] = None


class ResearchResponse(BaseModel):
    results: List[Dict[str, Any]]


class ArbitrageOpportunities(BaseModel):
    opportunities: List[Dict[str, Any]]
