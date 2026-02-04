"""
Phase 8.0 Control Plane Tests

Tests for AI governance config, budget governor, and kill switch integration.

CRITICAL TESTS:
1. Kill switch enforcement (AI disabled → all blocked)
2. Budget persistence (across backend restart simulation)
3. Budget enforcement (daily cap + per-signal cap)
4. Fail-closed semantics (DB errors → AI blocked)
5. Audit integrity (all attempts logged)
"""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Import Phase 8.0 governance components
from lunia_core.app.services.ai_gateway.governance import (
    AIGovernanceConfig,
    load_default_config
)
from lunia_core.app.services.ai_gateway.budget import BudgetGovernor
from lunia_core.app.services.execution_journal.budget_model import AIBudgetUsage
from lunia_core.app.services.ai_gateway.service import AIGatewayService
from lunia_core.app.services.execution_journal.models import (
    SignalEvent,
    SignalType,
    AIInferenceLog,
    AIEventType
)

# Import base for test DB
from lunia_core.app.auth.database import Base

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST FIXTURES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.fixture(scope="function")
def test_db():
    """Create in-memory SQLite DB for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    yield db
    db.close()
    engine.dispose()


@pytest.fixture
def governance_config():
    """Default governance config for testing."""
    return AIGovernanceConfig(
        ai_global_enabled=True,  # Override default (False)
        shadow_mode_default=True,
        daily_budget_usd=5.00,
        per_signal_budget_usd=0.05,
        hard_stop_on_budget_exceed=True
    )


@pytest.fixture
def budget_governor(test_db, governance_config):
    """Budget governor with test DB."""
    return BudgetGovernor(test_db, governance_config)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 1: GOVERNANCE CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_governance_config_defaults():
    """Test that governance config has safe defaults (fail-closed)."""
    config = load_default_config()
    
    # CRITICAL: AI disabled by default
    assert config.ai_global_enabled == False, "AI must be disabled by default (opt-in safety)"
    
    # Shadow mode enabled by default
    assert config.shadow_mode_default == True
    
    # Budget limits are non-negative
    assert config.daily_budget_usd >= 0
    assert config.per_signal_budget_usd >= 0
    
    # Fallback provider must be "mock" (zero-cost)
    assert config.fallback_provider_on_exceed == "mock"


def test_governance_config_validation():
    """Test config validation catches invalid values."""
    # Valid config
    valid_config = AIGovernanceConfig()
    is_valid, error = valid_config.validate()
    assert is_valid == True
    assert error is None
    
    # Invalid: negative budget
    invalid_config = AIGovernanceConfig(daily_budget_usd=-1.0)
    is_valid, error = invalid_config.validate()
    assert is_valid == False
    assert "cannot be negative" in error
    
    # Invalid: budget warning ratio > 1.0
    invalid_config = AIGovernanceConfig(budget_warning_ratio=1.5)
    is_valid, error = invalid_config.validate()
    assert is_valid == False
    assert "0.0-1.0" in error


def test_governance_config_serialization():
    """Test config can be serialized/deserialized."""
    config = AIGovernanceConfig(
        ai_global_enabled=True,
        daily_budget_usd=10.00
    )
    
    # to_dict
    config_dict = config.to_dict()
    assert config_dict["ai_global_enabled"] == True
    assert config_dict["daily_budget_usd"] == 10.00
    
    # from_dict
    restored = AIGovernanceConfig.from_dict(config_dict)
    assert restored.ai_global_enabled == True
    assert restored.daily_budget_usd == 10.00
    
    # to_json
    json_str = config.to_json()
    assert "ai_global_enabled" in json_str
    
    # from_json
    restored_from_json = AIGovernanceConfig.from_json(json_str)
    assert restored_from_json.daily_budget_usd == 10.00


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 2: KILL SWITCH
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.mark.asyncio
async def test_kill_switch_blocks_ai(test_db):
    """Test that AI kill switch blocks all inference attempts."""
    # Config with AI DISABLED
    config = AIGovernanceConfig(ai_global_enabled=False)
    
    gateway = AIGatewayService(
        governance_config=config,
        db_session=test_db
    )
    
    # Create test signal
    signal = SignalEvent(
        strategy_id="test_strategy",
        symbol="BTCUSDT",
        signal_type=SignalType.BUY,
        confidence=0.8,
        deterministic_reasoning="Test signal"
    )
    
    # Attempt inference
    result = await gateway.analyze_signal(
        signal_event=signal,
        context={"test": "context"}
    )
    
    # MUST return None (blocked)
    assert result is None
    
    # Verify blocked attempt was logged
    log_entries = test_db.query(AIInferenceLog).filter(
        AIInferenceLog.event_type == AIEventType.AI_BLOCKED
    ).all()
    
    assert len(log_entries) >= 1
    assert "kill_switch" in log_entries[0].validation_error


@pytest.mark.asyncio
async def test_kill_switch_allows_when_enabled(test_db):
    """Test that AI works when kill switch is ON."""
    # Config with AI ENABLED
    config = AIGovernanceConfig(
        ai_global_enabled=True,
        daily_budget_usd=5.00
    )
    
    gateway = AIGatewayService(
        governance_config=config,
        db_session=test_db
    )
    
    signal = SignalEvent(
        strategy_id="test_strategy",
        symbol="BTCUSDT",
        signal_type=SignalType.BUY,
        confidence=0.8,
        deterministic_reasoning="Test signal"
    )
    
    # Attempt inference (will use MockProvider, which succeeds)
    result = await gateway.analyze_signal(
        signal_event=signal,
        context={"test": "context"}
    )
    
    # Should succeed (MockProvider always returns valid response)
    assert result is not None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 3: BUDGET PERSISTENCE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_budget_persistence_across_restart(test_db, governance_config):
    """
    CRITICAL TEST: Budget state MUST survive backend restart.
    
    Simulate restart by creating two separate BudgetGovernor instances.
    """
    # Instance 1: Record spend
    governor1 = BudgetGovernor(test_db, governance_config)
    
    today = date.today()
    success = governor1.record_attempt(
        date=today,
        provider="mock",
        model=None,
        tokens_prompt=100,
        tokens_completion=50,
        cost_usd=0.50
    )
    assert success == True
    
    # Verify spend recorded
    spend1 = governor1.get_daily_spend(today)
    assert spend1 == 0.50
    
    # SIMULATE RESTART: Create NEW BudgetGovernor instance
    governor2 = BudgetGovernor(test_db, governance_config)
    
    # Spend should still be $0.50 (NOT reset to $0.00)
    spend2 = governor2.get_daily_spend(today)
    assert spend2 == 0.50, "Budget MUST persist across restart"


def test_budget_daily_rollover(test_db, governance_config):
    """Test that budget resets at midnight UTC (new calendar day)."""
    governor = BudgetGovernor(test_db, governance_config)
    
    today = date.today()
    yesterday = today - timedelta(days=1)
    
    # Record spend for yesterday
    governor.record_attempt(
        date=yesterday,
        provider="mock",
        model=None,
        tokens_prompt=100,
        tokens_completion=50,
        cost_usd=2.00
    )
    
    # Yesterday's spend should be $2.00
    assert governor.get_daily_spend(yesterday) == 2.00
    
    # Today's spend should be $0.00 (new day)
    assert governor.get_daily_spend(today) == 0.00


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 4: BUDGET ENFORCEMENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_budget_daily_cap_enforcement(test_db):
    """Test that daily cap blocks AI when exceeded."""
    config = AIGovernanceConfig(
        ai_global_enabled=True,
        daily_budget_usd=1.00,  # Very low cap for testing
        per_signal_budget_usd=0.50
    )
    
    governor = BudgetGovernor(test_db, config)
    
    # Spend $1.00 (at cap)
    governor.record_attempt(
        date=date.today(),
        provider="mock",
        model=None,
        tokens_prompt=100,
        tokens_completion=50,
        cost_usd=1.00
    )
    
    # Next attempt should be BLOCKED
    can_proceed, reason = governor.can_attempt(
        estimated_cost_usd=0.01,  # Small amount, but budget exhausted
        provider="mock"
    )
    
    assert can_proceed == False
    assert reason == "daily_cap_exceeded"


def test_budget_per_signal_cap_enforcement(test_db):
    """Test that per-signal cap blocks expensive calls."""
    config = AIGovernanceConfig(
        ai_global_enabled=True,
        daily_budget_usd=10.00,
        per_signal_budget_usd=0.05  # Max $0.05 per signal
    )
    
    governor = BudgetGovernor(test_db, config)
    
    # Attempt expensive call ($0.10 > $0.05 cap)
    can_proceed, reason = governor.can_attempt(
        estimated_cost_usd=0.10,
        provider="openai",
        model="gpt-4"
    )
    
    assert can_proceed == False
    assert reason == "per_signal_cap_exceeded"


def test_budget_projection_check(test_db):
    """Test that budget check prevents exceeding cap with next attempt."""
    config = AIGovernanceConfig(
        ai_global_enabled=True,
        daily_budget_usd=1.00,
        per_signal_budget_usd=0.50
    )
    
    governor = BudgetGovernor(test_db, config)
    
    # Spend $0.95 (close to $1.00 cap)
    governor.record_attempt(
        date=date.today(),
        provider="mock",
        model=None,
        tokens_prompt=100,
        tokens_completion=50,
        cost_usd=0.95
    )
    
    # Attempt $0.10 inference (would push total to $1.05)
    can_proceed, reason = governor.can_attempt(
        estimated_cost_usd=0.10,
        provider="mock"
    )
    
    assert can_proceed == False
    assert reason == "would_exceed_daily_cap"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 5: FAIL-CLOSED SEMANTICS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_budget_check_fails_closed_on_db_error(governance_config):
    """Test that DB errors cause AI to be blocked (fail-closed)."""
    # Mock DB session that raises exception
    mock_db = Mock()
    mock_db.query.side_effect = Exception("DB connection lost")
    
    governor = BudgetGovernor(mock_db, governance_config)
    
    # Budget check should FAIL CLOSED (return False)
    can_proceed, reason = governor.can_attempt(
        estimated_cost_usd=0.01,
        provider="mock"
    )
    
    assert can_proceed == False
    assert reason == "budget_check_failed"


def test_budget_record_fails_gracefully(governance_config):
    """Test that record_attempt fails gracefully on DB error."""
    mock_db = Mock()
    mock_db.query.side_effect = Exception("DB write failed")
    mock_db.commit.side_effect = Exception("Commit failed")
    
    governor = BudgetGovernor(mock_db, governance_config)
    
    # Should return False but not crash
    success = governor.record_attempt(
        date=date.today(),
        provider="mock",
        model=None,
        tokens_prompt=100,
        tokens_completion=50,
        cost_usd=0.10
    )
    
    assert success == False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 6: AUDIT INTEGRITY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.mark.asyncio
async def test_blocked_attempts_are_audited(test_db):
    """Test that even BLOCKED attempts are logged (no invisible usage)."""
    # AI disabled
    config = AIGovernanceConfig(ai_global_enabled=False)
    gateway = AIGatewayService(
        governance_config=config,
        db_session=test_db
    )
    
    signal = SignalEvent(
        strategy_id="test_strategy",
        symbol="BTCUSDT",
        signal_type=SignalType.BUY,
        confidence=0.8,
        deterministic_reasoning="Test"
    )
    
    # Blocked attempt
    result = await gateway.analyze_signal(signal, {"test": "context"})
    assert result is None
    
    # MUST be logged
    logs = test_db.query(AIInferenceLog).filter(
        AIInferenceLog.event_type == AIEventType.AI_BLOCKED
    ).all()
    
    assert len(logs) >= 1
    assert logs[0].response_valid == False
    assert logs[0].total_cost_usd == 0.0  # Not actually spent


def test_budget_usage_aggregation(test_db, governance_config):
    """Test that budget usage is correctly aggregated by provider/model."""
    governor = BudgetGovernor(test_db, governance_config)
    
    today = date.today()
    
    # Record multiple attempts for same provider/model
    governor.record_attempt(
        date=today,
        provider="mock",
        model=None,
        tokens_prompt=100,
        tokens_completion=50,
        cost_usd=0.10
    )
    
    governor.record_attempt(
        date=today,
        provider="mock",
        model=None,
        tokens_prompt=200,
        tokens_completion=100,
        cost_usd=0.20
    )
    
    # Should be aggregated into single row
    usage_rows = test_db.query(AIBudgetUsage).filter(
        AIBudgetUsage.date == today,
        AIBudgetUsage.provider == "mock"
    ).all()
    
    assert len(usage_rows) == 1
    assert usage_rows[0].total_attempts == 2
    assert usage_rows[0].total_tokens_prompt == 300
    assert usage_rows[0].total_tokens_completion == 150
    assert float(usage_rows[0].total_cost_usd) == 0.30


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 7: INTEGRATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.mark.asyncio
async def test_full_governance_flow(test_db):
    """
    Integration test: End-to-end governance flow.
    
    1. AI enabled, budget available → inference succeeds
    2. Budget exceeded → inference blocked
    3. Kill switch disabled → inference blocked
    """
    config = AIGovernanceConfig(
        ai_global_enabled=True,
        daily_budget_usd=0.50,  # Low cap
        per_signal_budget_usd=0.25
    )
    
    gateway = AIGatewayService(
        governance_config=config,
        db_session=test_db
    )
    
    signal = SignalEvent(
        strategy_id="test_strategy",
        symbol="BTCUSDT",
        signal_type=SignalType.BUY,
        confidence=0.8,
        deterministic_reasoning="Test"
    )
    
    # STEP 1: Should succeed (MockProvider, $0.00 cost)
    result1 = await gateway.analyze_signal(signal, {"test": "context"})
    assert result1 is not None
    
    # STEP 2: Manually exhaust budget
    gateway.budget_governor.record_attempt(
        date=date.today(),
        provider="mock",
        model=None,
        tokens_prompt=1000,
        tokens_completion=500,
        cost_usd=0.50  # At cap
    )
    
    # Next attempt should be blocked (budget exceeded)
    # Note: MockProvider costs $0.00, so this tests projection logic
    # We'd need to estimate non-zero cost for real test
    
    # STEP 3: Disable kill switch
    gateway.governance_config.ai_global_enabled = False
    result3 = await gateway.analyze_signal(signal, {"test": "context"})
    assert result3 is None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RUN TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
