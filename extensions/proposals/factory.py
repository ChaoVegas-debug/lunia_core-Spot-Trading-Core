"""
PHASE 10 — PROPOSAL SYSTEM: Factory (Intent → ProposalCard)

Transforms StrategyIntent into human-readable ProposalCard.

REQUIREMENTS:
- ENTRY intents only (EXIT/NOOP → None)
- Deterministic proposal_id
- Risk metrics derived or proxied
- Humanization (side_pretty, rationale_sections)
"""

from typing import Optional, List, Dict, Any

from extensions.protocol.protocol import (
    StrategyIntent,
    MarketSnapshot,
    IntentType,
    TradeDirection,
)
from extensions.proposals.types import ProposalCard, ProposalContext, ProposalStatus
from extensions.proposals.canonical import sha16_from_fields


# ────────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ────────────────────────────────────────────────────────────────────────────────

DEFAULT_PROPOSAL_TTL_MS = 600_000  # 10 minutes


# ────────────────────────────────────────────────────────────────────────────────
# FACTORY
# ────────────────────────────────────────────────────────────────────────────────


def create_proposal(
    intent: StrategyIntent,
    market: MarketSnapshot,
    ctx: ProposalContext,
) -> Optional[ProposalCard]:
    """
    Create ProposalCard from StrategyIntent.
    
    Args:
        intent: Strategy intent to transform
        market: Market snapshot for risk calculations
        ctx: Proposal context (injectable deps)
    
    Returns:
        ProposalCard if ENTRY intent, None otherwise
    """
    # Only ENTRY intents become proposals
    if intent.intent_type != IntentType.ENTRY:
        return None
    
    # Derive human fields
    side_pretty, side_style = _derive_side_display(intent.direction)
    size_pretty = _derive_size_display(intent, market)
    
    # Parse rationale into sections
    rationale_text = intent.rationale
    rationale_sections = _parse_rationale_sections(intent.rationale)
    
    # Derive risk metrics
    entry_price = market.mid  # Deterministic: use mid price
    risk_metrics = _derive_risk_metrics(intent, market, entry_price)
    exit_plan_view = _derive_exit_plan_view(intent, market, entry_price)
    
    # Determine expires_at_ms (priority: exit_plan TTL → governance default → hardcoded)
    expires_at_ms = _determine_expiry(intent, ctx)
    
    # Generate deterministic proposal_id
    proposal_id = _generate_proposal_id(intent, ctx, expires_at_ms, exit_plan_view)
    
    return ProposalCard(
        proposal_id=proposal_id,
        intent_id=intent.intent_id,
        run_id=ctx.run_id,
        correlation_id=ctx.correlation_id,
        strategy_id=intent.strategy_id,
        strategy_name=ctx.strategy_name,
        symbol=intent.symbol or "UNKNOWN",
        side_pretty=side_pretty,
        side_style=side_style,
        size_pretty=size_pretty,
        rationale_text=rationale_text,
        rationale_sections=rationale_sections,
        risk_metrics=risk_metrics,
        exit_plan_view=exit_plan_view,
        status=ProposalStatus.PENDING,
        created_at_ms=ctx.now_ms,
        expires_at_ms=expires_at_ms,
        decided_at_ms=None,
        decided_by=None,
        executed_at_ms=None,
    )


# ────────────────────────────────────────────────────────────────────────────────
# HUMANIZATION
# ────────────────────────────────────────────────────────────────────────────────


def _derive_side_display(direction: Optional[TradeDirection]) -> tuple[str, str]:
    """
    Derive (side_pretty, side_style) from TradeDirection.
    
    Returns:
        (side_pretty, side_style) tuple
    """
    if direction == TradeDirection.LONG:
        return ("BUY", "success")
    elif direction == TradeDirection.SHORT:
        return ("SELL", "danger")
    else:
        return ("NEUTRAL", "neutral")


def _derive_size_display(intent: StrategyIntent, market: MarketSnapshot) -> str:
    """
    Derive human-readable size string.
    
    Args:
        intent: Strategy intent
        market: Market snapshot
    
    Returns:
        Size string (e.g., "0.5 BTC")
    """
    if intent.size_base is not None:
        # Extract base currency from symbol (e.g., "BTC/USD" → "BTC")
        base = market.symbol.split("/")[0] if "/" in market.symbol else "BASE"
        return f"{intent.size_base:.6f} {base}"
    elif intent.size_quote is not None:
        # Extract quote currency
        quote = market.symbol.split("/")[1] if "/" in market.symbol else "QUOTE"
        return f"{intent.size_quote:.2f} {quote}"
    else:
        return "UNKNOWN SIZE"


def _parse_rationale_sections(rationale: str) -> List[Dict[str, str]]:
    """
    Parse rationale string into structured sections.
    
    Args:
        rationale: Rationale string from intent
    
    Returns:
        List of dicts with keys ["label", "value"]
    """
    sections = []
    
    # Split by " | " delimiter (common in Phase 9.4 strategies)
    parts = rationale.split(" | ")
    
    for part in parts:
        part = part.strip()
        if ":" in part:
            # Format: "label: value" or "label=value"
            if "=" in part and ":" not in part.split("=")[0]:
                label, value = part.split("=", 1)
            else:
                label, value = part.split(":", 1)
            sections.append({"label": label.strip(), "value": value.strip()})
        elif "=" in part:
            label, value = part.split("=", 1)
            sections.append({"label": label.strip(), "value": value.strip()})
        else:
            # No delimiter: treat as standalone value
            sections.append({"label": "info", "value": part})
    
    return sections


# ────────────────────────────────────────────────────────────────────────────────
# RISK METRICS
# ────────────────────────────────────────────────────────────────────────────────


def _derive_risk_metrics(
    intent: StrategyIntent,
    market: MarketSnapshot,
    entry_price: float,
) -> Dict[str, float]:
    """
    Derive risk metrics from intent and market data.
    
    REQUIRED keys: implied_loss_pct, reward_to_risk, max_loss_quote
    
    Args:
        intent: Strategy intent
        market: Market snapshot
        entry_price: Entry price (market.mid)
    
    Returns:
        Dict with risk metric keys
    """
    metrics = {
        "implied_loss_pct": 0.0,
        "reward_to_risk": 0.0,
        "max_loss_quote": 0.0,
    }
    
    if not intent.exit_plan:
        # No exit plan: use proxy markers
        metrics["implied_loss_pct"] = 0.0
        metrics["reward_to_risk"] = 0.0
        metrics["max_loss_quote"] = 0.0
        return metrics
    
    # Calculate stop loss price
    stop_loss_price = None
    if intent.exit_plan.stop_loss_price is not None:
        stop_loss_price = intent.exit_plan.stop_loss_price
    elif intent.exit_plan.stop_loss_pct is not None:
        # Derive from percentage
        if intent.direction == TradeDirection.LONG:
            stop_loss_price = entry_price * (1 - intent.exit_plan.stop_loss_pct / 100.0)
        elif intent.direction == TradeDirection.SHORT:
            stop_loss_price = entry_price * (1 + intent.exit_plan.stop_loss_pct / 100.0)
    
    # Calculate take profit price
    take_profit_price = None
    if intent.exit_plan.take_profit_price is not None:
        take_profit_price = intent.exit_plan.take_profit_price
    elif intent.exit_plan.take_profit_pct is not None:
        # Derive from percentage
        if intent.direction == TradeDirection.LONG:
            take_profit_price = entry_price * (1 + intent.exit_plan.take_profit_pct / 100.0)
        elif intent.direction == TradeDirection.SHORT:
            take_profit_price = entry_price * (1 - intent.exit_plan.take_profit_pct / 100.0)
    
    # Calculate implied loss %
    if stop_loss_price is not None:
        if intent.direction == TradeDirection.LONG:
            metrics["implied_loss_pct"] = ((entry_price - stop_loss_price) / entry_price) * 100.0
        elif intent.direction == TradeDirection.SHORT:
            metrics["implied_loss_pct"] = ((stop_loss_price - entry_price) / entry_price) * 100.0
    
    # Calculate reward-to-risk
    if stop_loss_price and take_profit_price:
        risk = abs(entry_price - stop_loss_price)
        reward = abs(take_profit_price - entry_price)
        if risk > 0:
            metrics["reward_to_risk"] = reward / risk
    
    # Calculate max loss in quote currency
    if stop_loss_price and intent.size_base:
        loss_per_unit = abs(entry_price - stop_loss_price)
        metrics["max_loss_quote"] = loss_per_unit * intent.size_base
    
    return metrics


def _derive_exit_plan_view(
    intent: StrategyIntent,
    market: MarketSnapshot,
    entry_price: float,
) -> Dict[str, Any]:
    """
    Derive exit plan view dict from intent.
    
    Args:
        intent: Strategy intent
        market: Market snapshot
        entry_price: Entry price
    
    Returns:
        Dict with exit plan fields
    """
    view = {
        "stop_loss_price": None,
        "take_profit_price": None,
        "time_limit_ms": None,
        "time_limit_human": None,
    }
    
    if not intent.exit_plan:
        return view
    
    # Stop loss
    if intent.exit_plan.stop_loss_price is not None:
        view["stop_loss_price"] = round(intent.exit_plan.stop_loss_price, 8)
    elif intent.exit_plan.stop_loss_pct is not None:
        if intent.direction == TradeDirection.LONG:
            view["stop_loss_price"] = round(entry_price * (1 - intent.exit_plan.stop_loss_pct / 100.0), 8)
        elif intent.direction == TradeDirection.SHORT:
            view["stop_loss_price"] = round(entry_price * (1 + intent.exit_plan.stop_loss_pct / 100.0), 8)
    
    # Take profit
    if intent.exit_plan.take_profit_price is not None:
        view["take_profit_price"] = round(intent.exit_plan.take_profit_price, 8)
    elif intent.exit_plan.take_profit_pct is not None:
        if intent.direction == TradeDirection.LONG:
            view["take_profit_price"] = round(entry_price * (1 + intent.exit_plan.take_profit_pct / 100.0), 8)
        elif intent.direction == TradeDirection.SHORT:
            view["take_profit_price"] = round(entry_price * (1 - intent.exit_plan.take_profit_pct / 100.0), 8)
    
    # Time limit
    if intent.exit_plan.time_limit_ms is not None:
        view["time_limit_ms"] = intent.exit_plan.time_limit_ms
        view["time_limit_human"] = _format_time_limit(intent.exit_plan.time_limit_ms)
    
    return view


def _format_time_limit(time_limit_ms: int) -> str:
    """Format time limit in human-readable form."""
    hours = time_limit_ms // (60 * 60 * 1000)
    minutes = (time_limit_ms % (60 * 60 * 1000)) // (60 * 1000)
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


# ────────────────────────────────────────────────────────────────────────────────
# EXPIRY & ID GENERATION
# ────────────────────────────────────────────────────────────────────────────────


def _determine_expiry(intent: StrategyIntent, ctx: ProposalContext) -> int:
    """
    Determine proposal expiry timestamp.
    
    Priority:
    1. intent.exit_plan.time_limit_ms (if exists)
    2. ctx.governance_snapshot["default_proposal_ttl_ms"] (if provided)
    3. DEFAULT_PROPOSAL_TTL_MS (10 minutes)
    
    Args:
        intent: Strategy intent
        ctx: Proposal context
    
    Returns:
        Expiry timestamp (milliseconds)
    """
    # Priority 1: exit plan TTL
    if intent.exit_plan and intent.exit_plan.time_limit_ms:
        return ctx.now_ms + intent.exit_plan.time_limit_ms
    
    # Priority 2: governance default
    if ctx.governance_snapshot and "default_proposal_ttl_ms" in ctx.governance_snapshot:
        return ctx.now_ms + ctx.governance_snapshot["default_proposal_ttl_ms"]
    
    # Priority 3: hardcoded default
    return ctx.now_ms + DEFAULT_PROPOSAL_TTL_MS


def _generate_proposal_id(
    intent: StrategyIntent,
    ctx: ProposalContext,
    expires_at_ms: int,
    exit_plan_view: Dict[str, Any],
) -> str:
    """
    Generate deterministic proposal_id.
    
    Based on SHA256 of core fields.
    
    Args:
        intent: Strategy intent
        ctx: Proposal context
        expires_at_ms: Expiry timestamp
        exit_plan_view: Exit plan view dict
    
    Returns:
        16-hex proposal ID
    """
    id_fields = {
        "intent_id": intent.intent_id,
        "run_id": ctx.run_id,
        "correlation_id": ctx.correlation_id,
        "strategy_id": intent.strategy_id,
        "symbol": intent.symbol,
        "direction": intent.direction.value if intent.direction else None,
        "created_at_ms": ctx.now_ms,
        "expires_at_ms": expires_at_ms,
        "exit_plan_view": exit_plan_view,
        "confidence": round(intent.confidence, 8),
    }
    
    return sha16_from_fields(id_fields)
