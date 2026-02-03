"""
PHASE 10 — PROPOSAL SYSTEM TESTS

Comprehensive tests for proposal layer covering:
A)  Factory logic (3 tests)
B) Humanization (2 tests)
C) Risk metrics (1 test)
D) Store lifecycle (3 tests)
E) Integration (3 tests)
F) Determinism (1 test)

Total: 13+ tests
"""

import pytest
from extensions.protocol.protocol import (
    PROTOCOL_VERSION,
    StrategyIntent,
    TradeExitPlan,
    MarketSnapshot,
    GovernanceContext,
    IntentType,
    TradeDirection,
    StrategyFrequency,
    VolatilityState,
    MarketRegime,
)
from extensions.sandbox.paper_types import TradeOutcome
from extensions.proposals.types import ProposalCard, ProposalContext, ProposalStatus
from extensions.proposals.factory import create_proposal
from extensions.proposals.store import ProposalStore
from extensions.proposals.audit import ProposalAuditStore
from extensions.proposals.integration import ProposalIntegration
from extensions.proposals.canonical import sha16_from_fields

# For integration test with real strategy
from extensions.strategies.volatility_trend_follower import VolatilityTrendFollower


# ────────────────────────────────────────────────────────────────────────────────
# TEST FIXTURES
# ────────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fixed_clock():
    """Fixed clock for deterministic testing."""
    return lambda: 1737600000000  # Phase 10 timestamp


@pytest.fixture
def sample_market():
    """Sample market snapshot."""
    return MarketSnapshot(
        symbol="BTC/USD",
        ts_ms=1737600000000,
        bid=50000.0,
        ask=50001.0,
        mid=50000.5,
        volume_24h=1000000.0,
        volatility_state=VolatilityState.NORMAL,
        market_regime=MarketRegime.TREND_UP,
        atr_14=300.0,
        spread_pct=0.0002,
    )


@pytest.fixture
def sample_entry_intent():
    """Sample ENTRY intent."""
    return StrategyIntent(
        intent_id="test_intent_001",
        ts_ms=1737600000000,
        protocol_version=PROTOCOL_VERSION,
        correlation_id="test_corr_001",
        intent_type=IntentType.ENTRY,
        direction=TradeDirection.LONG,
        symbol="BTC/USD",
        size_base=0.5,
        size_quote=None,
        exit_plan=TradeExitPlan(
            stop_loss_price=None,
            stop_loss_pct=2.0,
            take_profit_price=None,
            take_profit_pct=6.0,
            time_limit_ms=3600000,  # 1 hour
            trail_start_pct=None,
        ),
        confidence=0.75,
        rationale="Test entry: vol_state=normal | expected_move=250.0 | Cost Gate PASS",
        strategy_id="test_strategy_v1",
        strategy_frequency=StrategyFrequency.INTRADAY,
    )


@pytest.fixture
def sample_noop_intent():
    """Sample NOOP intent."""
    return StrategyIntent(
        intent_id="test_noop_001",
        ts_ms=1737600000000,
        protocol_version=PROTOCOL_VERSION,
        correlation_id="test_corr_001",
        intent_type=IntentType.NOOP,
        direction=None,
        symbol=None,
        size_base=None,
        size_quote=None,
        exit_plan=None,
        confidence=1.0,
        rationale="Cost gate failed",
        strategy_id="test_strategy_v1",
        strategy_frequency=StrategyFrequency.INTRADAY,
    )


@pytest.fixture
def sample_context(fixed_clock):
    """Sample proposal context."""
    return ProposalContext(
        strategy_id="test_strategy_v1",
        strategy_name="Test Strategy",
        run_id="run_001",
        correlation_id="test_corr_001",
        governance_snapshot=None,
        now_ms=fixed_clock(),
    )


# ────────────────────────────────────────────────────────────────────────────────
# A) FACTORY TESTS (3)
# ────────────────────────────────────────────────────────────────────────────────


def test_factory_creates_proposal_for_entry(sample_entry_intent, sample_market, sample_context):
    """Test factory creates ProposalCard for ENTRY intent."""
    proposal = create_proposal(sample_entry_intent, sample_market, sample_context)
    
    assert proposal is not None
    assert isinstance(proposal, ProposalCard)
    assert proposal.intent_id == sample_entry_intent.intent_id
    assert proposal.status == ProposalStatus.PENDING
    assert proposal.symbol == "BTC/USD"
    assert len(proposal.proposal_id) == 16  # 16-hex ID


def test_factory_returns_none_for_noop_or_exit(sample_noop_intent, sample_market, sample_context):
    """Test factory returns None for NOOP/EXIT intents."""
    proposal = create_proposal(sample_noop_intent, sample_market, sample_context)
    
    assert proposal is None


def test_proposal_id_deterministic_two_runs(sample_entry_intent, sample_market, sample_context):
    """Test proposal_id is deterministic for same inputs."""
    proposal1 = create_proposal(sample_entry_intent, sample_market, sample_context)
    proposal2 = create_proposal(sample_entry_intent, sample_market, sample_context)
    
    assert proposal1.proposal_id == proposal2.proposal_id


# ────────────────────────────────────────────────────────────────────────────────
# B) HUMANIZATION TESTS (2)
# ────────────────────────────────────────────────────────────────────────────────


def test_side_pretty_and_style(sample_entry_intent, sample_market, sample_context):
    """Test side_pretty and side_style humanization."""
    # LONG direction
    proposal = create_proposal(sample_entry_intent, sample_market, sample_context)
    assert proposal.side_pretty == "BUY"
    assert proposal.side_style == "success"
    
    # SHORT direction
    short_intent = StrategyIntent(
        **{**sample_entry_intent.__dict__, "direction": TradeDirection.SHORT}
    )
    proposal_short = create_proposal(short_intent, sample_market, sample_context)
    assert proposal_short.side_pretty == "SELL"
    assert proposal_short.side_style == "danger"


def test_rationale_sections_include_required_evidence(sample_entry_intent, sample_market, sample_context):
    """Test rationale_sections parsing includes evidence."""
    proposal = create_proposal(sample_entry_intent, sample_market, sample_context)
    
    assert len(proposal.rationale_sections) > 0
    
    # Check for evidence keys
    labels = [section["label"] for section in proposal.rationale_sections]
    assert "Test entry" in labels or "vol_state" in labels


# ────────────────────────────────────────────────────────────────────────────────
# C) RISK METRICS TEST (1)
# ────────────────────────────────────────────────────────────────────────────────


def test_risk_metrics_computable_or_proxy_marked(sample_entry_intent, sample_market, sample_context):
    """Test risk metrics are computed or proxied."""
    proposal = create_proposal(sample_entry_intent, sample_market, sample_context)
    
    # Required keys must exist
    assert "implied_loss_pct" in proposal.risk_metrics
    assert "reward_to_risk" in proposal.risk_metrics
    assert "max_loss_quote" in proposal.risk_metrics
    
    # implied_loss_pct should be computed (2% stop loss)
    assert proposal.risk_metrics["implied_loss_pct"] > 0
    assert proposal.risk_metrics["implied_loss_pct"] < 10  # Reasonable range
    
    # reward_to_risk should be computed (6% TP / 2% SL = 3:1)
    assert proposal.risk_metrics["reward_to_risk"] > 2.5
    assert proposal.risk_metrics["reward_to_risk"] < 3.5


# ────────────────────────────────────────────────────────────────────────────────
# D) STORE LIFECYCLE TESTS (3)
# ────────────────────────────────────────────────────────────────────────────────


def test_valid_transitions_pending_to_approved(sample_entry_intent, sample_market, sample_context):
    """Test valid transition PENDING → APPROVED."""
    audit_store = ProposalAuditStore()
    store = ProposalStore(audit_store)
    
    proposal = create_proposal(sample_entry_intent, sample_market, sample_context)
    store.add(proposal)
    
    # Update to APPROVED
    updated = store.update_status(
        proposal_id=proposal.proposal_id,
        new_status=ProposalStatus.APPROVED,
        actor="USER",
        reason="User approved",
        now_ms=sample_context.now_ms + 1000,
    )
    
    assert updated.status == ProposalStatus.APPROVED
    assert updated.decided_at_ms is not None
    assert updated.decided_by == "USER"


def test_invalid_transition_rejected(sample_entry_intent, sample_market, sample_context):
    """Test invalid transition raises ValueError."""
    audit_store = ProposalAuditStore()
    store = ProposalStore(audit_store)
    
    proposal = create_proposal(sample_entry_intent, sample_market, sample_context)
    store.add(proposal)
    
    # Try invalid transition: PENDING → EXECUTED (must go through APPROVED first)
    with pytest.raises(ValueError, match="Invalid transition"):
        store.update_status(
            proposal_id=proposal.proposal_id,
            new_status=ProposalStatus.EXECUTED,
            actor="SYSTEM",
            reason="Invalid",
            now_ms=sample_context.now_ms + 1000,
        )


def test_prune_expired_moves_to_expired(sample_entry_intent, sample_market, sample_context):
    """Test prune_expired moves PENDING proposals to EXPIRED."""
    audit_store = ProposalAuditStore()
    store = ProposalStore(audit_store)
    
    proposal = create_proposal(sample_entry_intent, sample_market, sample_context)
    store.add(proposal)
    
    # Prune with time after expiry
    future_ms = proposal.expires_at_ms + 1000
    expired_list = store.prune_expired(future_ms)
    
    assert len(expired_list) == 1
    assert expired_list[0].status == ProposalStatus.EXPIRED


# ────────────────────────────────────────────────────────────────────────────────
# E) INTEGRATION TESTS (3)
# ────────────────────────────────────────────────────────────────────────────────


def test_integration_with_real_phase9_4_strategy(sample_market, fixed_clock):
    """Test integration with VolatilityTrendFollower from Phase 9.4."""
    # Create governance context
    from extensions.protocol.protocol import GovernanceContext, RiskState, ShadowPortfolio
    
    governance = GovernanceContext(
        ts_ms=fixed_clock(),
        run_id="run_integration_001",
        correlation_id="corr_integration_001",
        is_live=False,
        is_reduce_only=False,
        allow_new_entries=True,
        max_position_size=10000.0,
        max_leverage=3.0,
        risk_state=RiskState.GREEN,
        emergency_override_active=False,
    )
    
    portfolio = ShadowPortfolio(
        base_currency="USD",
        equity=100000.0,
        available_balance=95000.0,
        margin_used=5000.0,
        margin_available=95000.0,
        positions={},
        daily_pnl=0.0,
        total_pnl=0.0,
        peak_equity=100000.0,
        drawdown_pct=0.0,
    )
    
    # Generate intent from strategy
    strategy = VolatilityTrendFollower()
    intent = strategy.generate_intent(governance, portfolio, [sample_market])
    
    # Create proposal via integration
    integration = ProposalIntegration()
    ctx = ProposalContext(
        strategy_id=intent.strategy_id,
        strategy_name="Volatility Trend Follower",
        run_id=governance.run_id,
        correlation_id=governance.correlation_id,
        governance_snapshot=None,
        now_ms=fixed_clock(),
    )
    
    proposal_id = integration.on_strategy_intent(intent, sample_market, ctx)
    
    # Should create proposal if intent is ENTRY
    if intent.intent_type == IntentType.ENTRY:
        assert proposal_id is not None
        proposal = integration.store.get(proposal_id)
        assert proposal.status == ProposalStatus.PENDING
    else:
        assert proposal_id is None


def test_user_veto_sets_terminal_status(sample_entry_intent, sample_market, sample_context):
    """Test user veto sets VETOED_BY_USER status."""
    integration = ProposalIntegration()
    
    proposal_id = integration.on_strategy_intent(sample_entry_intent, sample_market, sample_context)
    
    # User vetos
    updated = integration.on_user_decision(
        proposal_id=proposal_id,
        approve=False,
        actor="USER",
        now_ms=sample_context.now_ms + 1000,
    )
    
    assert updated.status == ProposalStatus.VETOED_BY_USER
    assert updated.decided_by == "USER"


def test_sync_from_trade_outcome_sets_executed(sample_entry_intent, sample_market, sample_context):
    """Test sync_from_trade_outcome sets EXECUTED only when APPROVED."""
    integration = ProposalIntegration()
    
    # Create and approve proposal
    proposal_id = integration.on_strategy_intent(sample_entry_intent, sample_market, sample_context)
    integration.on_user_decision(proposal_id, approve=True, now_ms=sample_context.now_ms + 1000)
    
    # Create mock TradeOutcome
    outcome = TradeOutcome(
        outcome_id="outcome_001",
        symbol="BTC/USD",
        side="long",
        qty=0.5,
        entry_ts_ms=sample_context.now_ms,
        exit_ts_ms=sample_context.now_ms + 2000,
        holding_time_ms=2000,
        entry_price=50000.0,
        exit_price=50100.0,
        gross_pnl=50.0,
        fee_total=2.0,
        spread_total=1.0,
        slippage_total=0.5,
        latency_total=0.0,
        net_pnl=46.5,
        exit_reason="take_profit",
        entry_intent_id=sample_entry_intent.intent_id,
        exit_intent_id="exit_intent_001",
        entry_run_id=sample_context.run_id,
        exit_run_id=sample_context.run_id,
        entry_correlation_id=sample_context.correlation_id,
        exit_correlation_id=sample_context.correlation_id,
        strategy_id=sample_entry_intent.strategy_id,
    )
    
    # Sync
    synced = integration.sync_from_trade_outcome(outcome, now_ms=sample_context.now_ms + 3000)
    
    assert synced is not None
    assert synced.status == ProposalStatus.EXECUTED
    assert synced.executed_at_ms is not None


# ────────────────────────────────────────────────────────────────────────────────
# F) DETERMINISM PROOF (1)
# ────────────────────────────────────────────────────────────────────────────────


def test_audit_store_integrity_hash_deterministic(sample_entry_intent, sample_market, fixed_clock):
    """Test audit store integrity hash is deterministic."""
    # Run 1
    ctx1 = ProposalContext(
        strategy_id="test_strategy_v1",
        strategy_name="Test Strategy",
        run_id="run_determ",
        correlation_id="corr_determ",
        governance_snapshot=None,
        now_ms=fixed_clock(),
    )
    integration1 = ProposalIntegration()
    proposal_id1 = integration1.on_strategy_intent(sample_entry_intent, sample_market, ctx1)
    integration1.on_user_decision(proposal_id1, approve=True, now_ms=fixed_clock() + 1000)
    hash1 = integration1.audit_store.integrity_hash()
    
    # Run 2 (identical inputs)
    ctx2 = ProposalContext(
        strategy_id="test_strategy_v1",
        strategy_name="Test Strategy",
        run_id="run_determ",
        correlation_id="corr_determ",
        governance_snapshot=None,
        now_ms=fixed_clock(),
    )
    integration2 = ProposalIntegration()
    proposal_id2 = integration2.on_strategy_intent(sample_entry_intent, sample_market, ctx2)
    integration2.on_user_decision(proposal_id2, approve=True, now_ms=fixed_clock() + 1000)
    hash2 = integration2.audit_store.integrity_hash()
    
    # Hashes must match
    assert hash1 == hash2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
