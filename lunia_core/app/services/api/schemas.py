"""Pydantic schemas for the Flask API."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator, root_validator


# -------- Basic trading requests / responses --------

class TradeRequest(BaseModel):
    symbol: str = Field(..., description="Trading pair symbol, e.g. BTCUSDT")
    side: str = Field(..., description="Order side BUY or SELL")
    qty: float = Field(..., gt=0, description="Quantity to trade")

    @root_validator(pre=True)
    def validate_fields(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values

        side = str(values.get("side", "")).upper()
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        values["side"] = side

        if "symbol" in values:
            if not values["symbol"]:
                raise ValueError("symbol field required")
            values["symbol"] = str(values["symbol"]).upper()
        else:
            raise ValueError("symbol field required")

        if "type" in values and isinstance(values["type"], str):
            values["type"] = values["type"].upper()
        return values


class TradeResponse(BaseModel):
    status: str
    txid: Optional[str] = None

    @validator("status")
    def non_empty_status(cls, v: str) -> str:
        if not v:
            raise ValueError("status must be non-empty")
        return v


class PingResponse(BaseModel):
    status: str
    version: Optional[str] = None

    @validator("status")
    def non_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("status must be non-empty")
        return v


# -------- Signals --------

class SignalPayload(BaseModel):
    symbol: str = Field(...)
    side: str = Field(...)
    qty: float = Field(..., gt=0)

    @root_validator(pre=True)
    def normalize(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values

        if "side" in values:
            values["side"] = str(values["side"]).upper()
            if values["side"] not in {"BUY", "SELL"}:
                raise ValueError("side must be BUY or SELL")

        if "symbol" in values:
            if not values["symbol"]:
                raise ValueError("symbol field required")
            values["symbol"] = str(values["symbol"]).upper()
        else:
            raise ValueError("symbol field required")

        return values


class SignalsEnvelope(BaseModel):
    signals: List[SignalPayload]
    enable: Dict[str, int] = Field(default_factory=lambda: {"SPOT": 1})


# -------- Futures --------

class FuturesTradeRequest(TradeRequest):
    leverage: float = Field(1.0, gt=0, description="Leverage multiplier")
    type: str = Field("MARKET", description="Order type for futures")


# -------- Portfolio / Balances --------

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


# -------- Ops State --------

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


# -------- Controls / Config --------

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


# -------- Research / Arbitrage --------

class ResearchRequest(BaseModel):
    pairs: Optional[List[str]] = None


class ResearchResponse(BaseModel):
    results: List[Dict[str, Any]]


class ArbitrageOpportunities(BaseModel):
    opportunities: List[Dict[str, Any]]


class ActivityComponent(BaseModel):
    status: str
    last_tick: Optional[float] = None
    notes: Optional[str] = None


class ActivityItem(BaseModel):
    ts: str
    actor: str
    action: str
    ok: bool = True
    details: Optional[str] = None


class ActivityResponse(BaseModel):
    components: Dict[str, ActivityComponent]
    last_actions: List[ActivityItem] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class SignalFeedItem(BaseModel):
    ts: str
    symbol: str
    side: str
    confidence: float
    strategy: str
    rationale: Optional[str] = None
    source: str


class SignalsFeed(BaseModel):
    items: List[SignalFeedItem]
    cursor: Optional[str] = None


class PortfolioAggregate(BaseModel):
    equity_total_usd: float
    tradable_equity_usd: Optional[float] = None
    cap_pct: Optional[float] = None
    reserves: Optional[Dict[str, float]] = None
    positions: List[PortfolioPosition] = Field(default_factory=list)
    balances: List[BalanceEntry] = Field(default_factory=list)
    realized_pnl: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    timestamp: str


class LogEntry(BaseModel):
    ts: str
    level: str
    message: str


class LogsResponse(BaseModel):
    items: List[LogEntry]


# -------- Auth / Admin --------


class UserOut(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    created_at: str
    last_login_at: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    expires_at: str


class FeatureFlagSchema(BaseModel):
    key: str
    value: Any
    updated_at: str
    updated_by: Optional[int] = None


class LimitSchema(BaseModel):
    scope: str
    subject: Optional[str] = None
    key: str
    value: Any
    updated_at: str
    updated_by: Optional[int] = None


class AuditEventSchema(BaseModel):
    id: str
    ts: str
    actor_user_id: Optional[int]
    actor_role: Optional[str]
    action: str
    target: Optional[str]
    result: str
    ip: Optional[str]
    user_agent: Optional[str]
    metadata: Optional[Dict[str, Any]]
