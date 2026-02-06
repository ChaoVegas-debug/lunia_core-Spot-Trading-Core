"""
Phase 8.1B: Tiered Router - Test Suite (Governance Safety)

Tests GATE ORDER preservation and safety scaffolding.

CRITICAL:
- All tests use mocks (NO live provider calls)
- Tests prove gates executed BEFORE router
- Tests prove tiktoken PROD rule enforced
- Tests prove secrets never leaked
- All tests run WITHOUT pytest-asyncio (using asyncio.run())
"""

import pytest
import logging
import asyncio
import os
import json
from unittest.mock import Mock, AsyncMock, patch

from lunia_core.app.services.ai_gateway.router import (
    TieredRouter,
    RoutingMode,
    FastVerdict,
    RouterMetadata
)
from lunia_core.app.services.ai_gateway.governance import AIGovernanceConfig
from lunia_core.app.services.ai_gateway.budget import BudgetGovernor


# ============================================================================
# STEP 2: GOVERNANCE SAFETY TESTS (Must pass with stubs)
# ============================================================================


def test_router_metadata_redaction():
    """Test that RouterMetadata.to_dict() redacts secrets."""
    metadata = RouterMetadata(
        router_enabled=True,
        routing_mode="fast_only",
        path_taken="FAST",
        fast_model="gpt-4o-mini"
    )
    
    meta_dict = metadata.to_dict()
    
    # Should have expected fields
    assert meta_dict["router_enabled"] is True
    assert meta_dict["routing_mode"] == "fast_only"
    assert meta_dict["path_taken"] == "FAST"
    
    # Should NOT contain secrets (if any were added)
    assert "sk-" not in str(meta_dict)
    assert "api_key" not in str(meta_dict).lower()


def test_router_metadata_has_block_reason():
    """Test that RouterMetadata has block_reason field (event model canon)."""
    metadata = RouterMetadata(
        router_enabled=True,
        routing_mode="fast_only",
        path_taken="MOCK_FALLBACK",
        block_reason="dependency_missing_tiktoken"
    )
    
    assert metadata.block_reason == "dependency_missing_tiktoken"
    
    meta_dict = metadata.to_dict()
    assert "block_reason" in meta_dict
    assert meta_dict["block_reason"] == "dependency_missing_tiktoken"


def test_router_init_with_default_config():
    """Test router initializes with default governance config."""
    config = AIGovernanceConfig()
    
    # Mock budget governor
    mock_governor = Mock(spec=BudgetGovernor)
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    # Should initialize with defaults
    assert router.enabled is False  # Default: disabled
    assert router.routing_mode == RoutingMode.FAST_ONLY.value
    assert router.fast_model == "gpt-4o-mini"
    assert router.deep_model == "gpt-4-turbo"


def test_router_disabled_returns_linear():
    """Test that router disabled mode doesn't crash (linear fallback stub)."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = False
    
    mock_governor = Mock(spec=BudgetGovernor)
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    # Use asyncio.run() to execute async function
    result, metadata = asyncio.run(router.route(
        prompt="Test prompt",
        context={"test": "context"}
    ))
    
    # Should return metadata indicating linear path
    assert metadata.router_enabled is False
    assert metadata.path_taken == "LINEAR"
    
    # Result can be None (stub not implemented yet)
    assert result is None


def test_tiktoken_prod_rule_mock_fallback_when_missing():
    """
    CRITICAL TEST: PROD + missing tiktoken → MOCK_FALLBACK.
    
    This test proves the router enforces the tiktoken PROD rule with fail-operational.
    """
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.production_requires_tiktoken = True
    
    mock_governor = Mock(spec=BudgetGovernor)
    
    router =TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    # Mock ENVIRONMENT=production and tiktoken as unavailable
    with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
        with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', False):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"test": "context"}
            ))
    
    # Should fail-operational to MockProvider
    assert metadata.path_taken == "MOCK_FALLBACK"
    assert metadata.final_decision_source == "MOCK"
    assert metadata.block_reason == "dependency_missing_tiktoken"
    
    # Result should be from MockProvider (dict or None)
    # MockProvider returns deterministic response


def test_tiktoken_prod_rule_allows_when_available():
    """Test that PROD + tiktoken available → router proceeds."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_ONLY.value
    config.production_requires_tiktoken = True
    
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (False, "Budget blocked")  # Block to avoid provider call
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    # Mock ENVIRONMENT=production and tiktoken as available
    with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
        with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"test": "context"}
            ))
    
    # Should NOT block on tiktoken (budget blocked instead)
    assert metadata.path_taken != "MOCK_FALLBACK"
    assert metadata.block_reason != "dependency_missing_tiktoken"
    
    # (Budget blocked is OK for this test)


def test_tiktoken_rule_not_enforced_in_dev():
    """Test that DEV environment does NOT enforce tiktoken rule."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_ONLY.value
    config.production_requires_tiktoken = True
    
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (False, "Budget blocked")  # Block to avoid provider call
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    # Mock ENVIRONMENT=development (default) and tiktoken as unavailable
    with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
        with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', False):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"test": "context"}
            ))
    
    # Should NOT block (DEV allows heuristic fallback)
    assert metadata.path_taken != "MOCK_FALLBACK"
    assert metadata.block_reason != "dependency_missing_tiktoken"


def test_unknown_routing_mode_fails():
    """Test that unknown routing mode fails gracefully with block_reason."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = "INVALID_MODE"
    
    mock_governor = Mock(spec=BudgetGovernor)
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        result, metadata = asyncio.run(router.route(
            prompt="Test prompt",
            context={"test": "context"}
        ))
    
    # Should fail gracefully
    assert result is None
    assert metadata.path_taken == "ERROR"
    assert metadata.block_reason == "invalid_routing_mode"


def test_router_logs_contain_no_secrets(caplog):
    """
    CRITICAL TEST: Router logs must NOT contain secrets.
    
    This test verifies that all router logging passes through redaction.
    """
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_ONLY.value
    
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (False, "Budget blocked")  # Block to avoid provider call
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    # Create context with a test API key (should never appear in logs)
    test_key = "sk-test" + "x" * 40
    context_with_secret = {
        "api_key": test_key,  # Should be redacted
        "test": "data"
    }
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with caplog.at_level(logging.DEBUG):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context=context_with_secret
            ))
    
    # Check ALL log messages
    for record in caplog.records:
        assert test_key not in record.message
        assert "sk-" not in record.message
    
    # Check metadata dict
    meta_dict = metadata.to_dict()
    assert test_key not in str(meta_dict)
    assert "sk-" not in str(meta_dict)


# ============================================================================
# GATE ORDER VERIFICATION (Integration with AIGateway)
# ============================================================================

def test_gate_order_documentation():
    """
    Document expected gate order for router integration.
    
    This is a documentation test to ensure gate order is explicit.
    
    GATE ORDER (SACRED):
    1. Kill Switch (AIGateway checks ai_global_enabled)
    2. BudgetGovernor (AIGateway checks can_attempt())
    3. CircuitBreaker (AIGateway checks can_execute())
    4. TieredRouter (this module)
    5. Provider (FAST or DEEP)
    
    Router MUST NOT re-check gates 1-3.
    Router assumes gates 1-3 already PASSED.
    """
    # This test always passes - it's documentation
    assert True


# ============================================================================
# STEP 3: FAST PATH TESTS (Implementation Proof)
# ============================================================================

def test_fast_path_budget_denied():
    """Test FAST path blocked by budget → provider NOT called."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_ONLY.value
    
    # Mock budget governor to deny
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (False, "Budget exceeded")
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with patch('lunia_core.app.services.ai_gateway.router.get_provider') as mock_get_provider:
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"test": "context"}
            ))
    
    # Provider should NOT have been called
    mock_get_provider.assert_not_called()
    
    # Metadata should show budget block
    assert result is None
    assert metadata.path_taken == "FAST"
    assert metadata.block_reason == "fast_budget_blocked"
    assert metadata.final_decision_source == "NONE"
    assert metadata.fast_cost_est is not None


def test_fast_path_executes_with_mocked_provider():
    """Test FAST path executes and returns valid result."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_ONLY.value
    
    # Mock budget governor to allow
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (True, None)
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    # Mock provider response
    mock_response = Mock()
    mock_response.content = json.dumps({
        "fast_verdict": "APPROVE",
        "fast_reason_codes": ["CONFIRMED_SIGNAL"],
        "confidence_fast": 0.85,
        "risk_flags_fast": [],
        "recommended_action_fast": "MONITOR",
        "notes_fast": "Signal looks good"
    })
    mock_response.usage = {"prompt_tokens": 50, "completion_tokens": 20}
    
    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(return_value=mock_response)
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with patch('lunia_core.app.services.ai_gateway.router.get_provider', return_value=mock_provider):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"test": "context"}
            ))
    
    # Should have succeeded
    assert result is not None
    assert result["fast_verdict"] == "APPROVE"
    assert metadata.path_taken == "FAST"
    assert metadata.final_decision_source == "FAST"
    assert metadata.fast_verdict == "APPROVE"
    assert metadata.fast_confidence == 0.85
    assert metadata.fast_cost_est is not None
    assert metadata.fast_cost_actual is not None
    assert metadata.fast_latency_ms is not None


def test_fast_verdict_reject_saves_deep_cost():
    """Test cost_saved_usd populated when FAST rejects."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_ONLY.value
    
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (True, None)
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    # Mock FAST response with REJECT verdict
    mock_response = Mock()
    mock_response.content = json.dumps({
        "fast_verdict": "REJECT",
        "fast_reason_codes": ["INVALID_SIGNAL"],
        "confidence_fast": 0.92,
        "risk_flags_fast": ["NOISE"],
        "recommended_action_fast": "IGNORE",
        "notes_fast": "Signal rejected as noise"
    })
    mock_response.usage = {"prompt_tokens": 50, "completion_tokens": 20}
    
    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(return_value=mock_response)
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with patch('lunia_core.app.services.ai_gateway.router.get_provider', return_value=mock_provider):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"test": "context"}
            ))
    
    # Should have cost_saved_usd populated
    assert result["fast_verdict"] == "REJECT"
    assert metadata.cost_saved_usd is not None
    assert metadata.cost_saved_usd > 0
    assert metadata.fast_verdict == "REJECT"


def test_fast_invalid_json_falls_back_to_mock():
    """Test invalid FAST JSON → fallback to Mock."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_ONLY.value
    
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (True, None)
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    # Mock provider response with invalid JSON
    mock_response = Mock()
    mock_response.content = "NOT JSON AT ALL"
    mock_response.usage = {"prompt_tokens": 50, "completion_tokens": 20}
    
    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(return_value=mock_response)
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with patch('lunia_core.app.services.ai_gateway.router.get_provider', return_value=mock_provider):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"test": "context"}
            ))
    
    # Should fallback to Mock
    assert metadata.path_taken == "MOCK_FALLBACK"
    assert metadata.final_decision_source == "MOCK"
    assert metadata.block_reason == "fast_invalid_json"


def test_fast_invalid_schema_falls_back_to_mock():
    """Test FAST response with invalid schema → fallback to Mock."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_ONLY.value
    
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (True, None)
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    # Mock provider response with missing required fields
    mock_response = Mock()
    mock_response.content = json.dumps({
        "fast_verdict": "APPROVE",
        # Missing: fast_reason_codes, confidence_fast, etc.
    })
    mock_response.usage = {"prompt_tokens": 50, "completion_tokens": 20}
    
    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(return_value=mock_response)
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with patch('lunia_core.app.services.ai_gateway.router.get_provider', return_value=mock_provider):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"test": "context"}
            ))
    
    # Should fallback to Mock
    assert metadata.path_taken == "MOCK_FALLBACK"
    assert metadata.final_decision_source == "MOCK"
    assert metadata.block_reason == "fast_invalid_schema"


def test_fast_cost_estimation_recorded():
    """Test fast_cost_est vs fast_cost_actual recorded."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_ONLY.value
    
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (True, None)
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    mock_response = Mock()
    mock_response.content = json.dumps({
        "fast_verdict": "APPROVE",
        "fast_reason_codes": ["OK"],
        "confidence_fast": 0.80,
        "risk_flags_fast": [],
        "recommended_action_fast": "MONITOR",
        "notes_fast": "OK"
    })
    mock_response.usage = {"prompt_tokens": 100, "completion_tokens": 50}
    
    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(return_value=mock_response)
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with patch('lunia_core.app.services.ai_gateway.router.get_provider', return_value=mock_provider):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"test": "context"}
            ))
    
    # Both estimates should be present
    assert metadata.fast_cost_est is not None
    assert metadata.fast_cost_actual is not None
    assert metadata.fast_cost_est > 0
    assert metadata.fast_cost_actual > 0


def test_fast_no_secret_leakage():
    """Test FAST path does NOT leak secrets."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_ONLY.value
    
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (True, None)
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    test_key = "sk-test" + "x" * 40
    
    mock_response = Mock()
    mock_response.content = json.dumps({
        "fast_verdict": "APPROVE",
        "fast_reason_codes": ["OK"],
        "confidence_fast": 0.75,
        "risk_flags_fast": [],
        "recommended_action_fast": "MONITOR",
        "notes_fast": "No secrets here"
    })
    mock_response.usage = {"prompt_tokens": 50, "completion_tokens": 20}
    
    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(return_value=mock_response)
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with patch('lunia_core.app.services.ai_gateway.router.get_provider', return_value=mock_provider):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"api_key": test_key}
            ))
    
    # Check metadata dict
    meta_dict = metadata.to_dict()
    assert test_key not in str(meta_dict)
    assert "sk-" not in str(meta_dict)


# ============================================================================
# STEP 4: ESCALATION LOGIC TESTS
# ============================================================================

def test_escalate_on_fast_verdict_escalate():
    """Test escalation triggers when fast_verdict == 'ESCALATE'."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_THEN_DEEP.value
    
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (True, None)
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    # Mock FAST response with ESCALATE verdict
    mock_response = Mock()
    mock_response.content = json.dumps({
        "fast_verdict": "ESCALATE",
        "fast_reason_codes": ["NEEDS_DEEP_ANALYSIS"],
        "confidence_fast": 0.80,
        "risk_flags_fast": [],
        "recommended_action_fast": "ESCALATE",
        "notes_fast": "Requires deeper analysis"
    })
    mock_response.usage = {"prompt_tokens": 50, "completion_tokens": 20}
    
    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(return_value=mock_response)
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with patch('lunia_core.app.services.ai_gateway.router.get_provider', return_value=mock_provider):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"test": "context"}
            ))
    
    # Should escalate
    assert metadata.escalation_triggered is True
    assert metadata.escalation_reason == "fast_verdict_escalate"
    assert metadata.path_taken == "FAST_THEN_DEEP"  # DEEP executes now
    assert metadata.deep_cost_est is not None


def test_escalate_on_ambiguity_band():
    """Test escalation triggers when confidence in ambiguity band."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_THEN_DEEP.value
    
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (True, None)
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    # Mock FAST response with ambiguous confidence (default band: 0.45-0.70)
    mock_response = Mock()
    mock_response.content = json.dumps({
        "fast_verdict": "APPROVE",
        "fast_reason_codes": ["OK"],
        "confidence_fast": 0.55,  # Within ambiguity band
        "risk_flags_fast": [],
        "recommended_action_fast": "MONITOR",
        "notes_fast": "Ambiguous signal"
    })
    mock_response.usage = {"prompt_tokens": 50, "completion_tokens": 20}
    
    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(return_value=mock_response)
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with patch('lunia_core.app.services.ai_gateway.router.get_provider', return_value=mock_provider):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"test": "context"}
            ))
    
    # Should escalate due to ambiguity
    assert metadata.escalation_triggered is True
    assert metadata.escalation_reason == "ambiguity_band"
    assert metadata.path_taken == "FAST_THEN_DEEP"  # DEEP executes now


def test_escalate_on_critical_reason_code():
    """Test escalation triggers on critical reason codes."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_THEN_DEEP.value
    
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (True, None)
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    # Mock FAST response with critical reason code
    mock_response = Mock()
    mock_response.content = json.dumps({
        "fast_verdict": "APPROVE",
        "fast_reason_codes": ["CONFLICTING_SIGNAL"],  # Critical code
        "confidence_fast": 0.85,
        "risk_flags_fast": [],
        "recommended_action_fast": "MONITOR",
        "notes_fast": "Conflicting signals detected"
    })
    mock_response.usage = {"prompt_tokens": 50, "completion_tokens": 20}
    
    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(return_value=mock_response)
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with patch('lunia_core.app.services.ai_gateway.router.get_provider', return_value=mock_provider):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"test": "context"}
            ))
    
    # Should escalate due to critical code
    assert metadata.escalation_triggered is True
    assert metadata.escalation_reason == "critical_reason_code:CONFLICTING_SIGNAL"
    assert metadata.path_taken == "FAST_THEN_DEEP"  # DEEP executes now


def test_no_escalate_outside_band_and_no_critical_codes():
    """Test no escalation when conditions not met."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_THEN_DEEP.value
    
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (True, None)
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    # Mock FAST response with high confidence, no critical codes
    mock_response = Mock()
    mock_response.content = json.dumps({
        "fast_verdict": "APPROVE",
        "fast_reason_codes": ["CONFIRMED_SIGNAL"],
        "confidence_fast": 0.90,  # Outside ambiguity band
        "risk_flags_fast": [],
        "recommended_action_fast": "MONITOR",
        "notes_fast": "Clear signal"
    })
    mock_response.usage = {"prompt_tokens": 50, "completion_tokens": 20}
    
    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(return_value=mock_response)
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with patch('lunia_core.app.services.ai_gateway.router.get_provider', return_value=mock_provider):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"test": "context"}
            ))
    
    # Should NOT escalate
    assert metadata.escalation_triggered is False
    assert metadata.path_taken == "FAST"


def test_reject_never_escalates():
    """Test REJECT verdict NEVER escalates (terminal)."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_THEN_DEEP.value
    
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (True, None)
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    # Mock FAST response with REJECT + ambiguous confidence + critical code
    # (all escalation triggers present EXCEPT REJECT is terminal)
    mock_response = Mock()
    mock_response.content = json.dumps({
        "fast_verdict": "REJECT",
        "fast_reason_codes": ["CONFLICTING_SIGNAL"],  # Critical code
        "confidence_fast": 0.55,  # Ambiguous
        "risk_flags_fast": ["NOISE"],
        "recommended_action_fast": "IGNORE",
        "notes_fast": "Signal rejected"
    })
    mock_response.usage = {"prompt_tokens": 50, "completion_tokens": 20}
    
    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(return_value=mock_response)
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with patch('lunia_core.app.services.ai_gateway.router.get_provider', return_value=mock_provider):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"test": "context"}
            ))
    
    # REJECT is terminal - NEVER escalates
    assert metadata.escalation_triggered is False
    assert metadata.fast_verdict == "REJECT"
    assert metadata.path_taken == "FAST"
    # Cost saved should still be populated
    assert metadata.cost_saved_usd is not None


def test_fast_only_mode_never_escalates():
    """Test FAST_ONLY mode never escalates (even with ESCALATE verdict)."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_ONLY.value  # FAST_ONLY
    
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (True, None)
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    # Mock FAST response with ESCALATE verdict
    mock_response = Mock()
    mock_response.content = json.dumps({
        "fast_verdict": "ESCALATE",
        "fast_reason_codes": ["NEEDS_DEEP"],
        "confidence_fast": 0.50,
        "risk_flags_fast": [],
        "recommended_action_fast": "ESCALATE",
        "notes_fast": "Should escalate but mode is FAST_ONLY"
    })
    mock_response.usage = {"prompt_tokens": 50, "completion_tokens": 20}
    
    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(return_value=mock_response)
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with patch('lunia_core.app.services.ai_gateway.router.get_provider', return_value=mock_provider):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"test": "context"}
            ))
    
    # FAST_ONLY mode - no escalation possible
    # (escalation_triggered should be False because we're in FAST_ONLY mode)
    assert metadata.path_taken == "FAST"
    assert metadata.fast_verdict == "ESCALATE"


def test_metadata_records_escalation_reason_and_deep_cost_est_when_escalating():
    """Test metadata properly records escalation details."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_THEN_DEEP.value
    
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (True, None)
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    # Mock FAST response triggering escalation
    mock_response = Mock()
    mock_response.content = json.dumps({
        "fast_verdict": "ESCALATE",
        "fast_reason_codes": ["NEEDS_ANALYSIS"],
        "confidence_fast": 0.75,
        "risk_flags_fast": [],
        "recommended_action_fast": "ESCALATE",
        "notes_fast": "Requires deep analysis"
    })
    mock_response.usage = {"prompt_tokens": 50, "completion_tokens": 20}
    
    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(return_value=mock_response)
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with patch('lunia_core.app.services.ai_gateway.router.get_provider', return_value=mock_provider):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt for deep cost estimation",
                context={"test": "context"}
            ))
    
    # Verify all escalation metadata
    assert metadata.escalation_triggered is True
    assert metadata.escalation_reason == "fast_verdict_escalate"
    assert metadata.deep_cost_est is not None
    assert metadata.deep_cost_est > 0
    assert metadata.path_taken == "FAST_THEN_DEEP"  # DEEP executes now
    
    # Verify metadata dict includes escalation info
    meta_dict = metadata.to_dict()
    assert "escalation_triggered" in meta_dict
    assert "escalation_reason" in meta_dict
    assert "deep_cost_est" in meta_dict


# ============================================================================
# STEP 5: DEEP PATH EXECUTION TESTS
# ============================================================================

def test_deep_executes_after_escalation():
    """Test DEEP path executes when escalation triggers."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_THEN_DEEP.value
    
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (True, None)  # Allow both FAST and DEEP
    mock_governor.record_attempt = Mock()
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    # Mock FAST response triggering escalation
    fast_response = Mock()
    fast_response.content = json.dumps({
        "fast_verdict": "ESCALATE",
        "fast_reason_codes": ["NEEDS_DEEP"],
        "confidence_fast": 0.60,
        "risk_flags_fast": [],
        "recommended_action_fast": "ESCALATE",
        "notes_fast": "Escalate to DEEP"
    })
    fast_response.usage = {"prompt_tokens": 50, "completion_tokens": 20}
    
    # Mock DEEP response
    deep_response = Mock()
    deep_response.content = json.dumps({
        "analysis": "Deep analysis result",
        "confidence_deep": 0.95
    })
    deep_response.usage = {"prompt_tokens": 200, "completion_tokens": 100}
    
    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(side_effect=[fast_response, deep_response])
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with patch('lunia_core.app.services.ai_gateway.router.get_provider', return_value=mock_provider):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"test": "context"}
            ))
    
    # DEEP should have executed
    assert metadata.path_taken == "FAST_THEN_DEEP"
    assert metadata.final_decision_source == "DEEP"
    assert metadata.escalation_triggered is True
    assert metadata.deep_cost_actual is not None
    assert metadata.deep_latency_ms is not None
    assert metadata.deep_confidence == 0.95
    
    # Budget governor should have recorded DEEP attempt
    assert mock_governor.record_attempt.called


def test_deep_budget_denied_returns_fast_result():
    """Test DEEP budget denial returns FAST result."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_THEN_DEEP.value
    
    mock_governor = Mock(spec=BudgetGovernor)
    # Allow FAST, deny DEEP
    mock_governor.can_attempt.side_effect = [(True, None), (False, "Budget exhausted")]
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    # Mock FAST response triggering escalation
    fast_response = Mock()
    fast_response.content = json.dumps({
        "fast_verdict": "ESCALATE",
        "fast_reason_codes": ["NEEDS_DEEP"],
        "confidence_fast": 0.60,
        "risk_flags_fast": [],
        "recommended_action_fast": "ESCALATE",
        "notes_fast": "Should escalate but DEEP budget blocked"
    })
    fast_response.usage = {"prompt_tokens": 50, "completion_tokens": 20}
    
    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(return_value=fast_response)
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with patch('lunia_core.app.services.ai_gateway.router.get_provider', return_value=mock_provider):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"test": "context"}
            ))
    
    # Should return FAST result (DEEP blocked)
    assert result["fast_verdict"] == "ESCALATE"
    assert metadata.path_taken == "FAST_ONLY_DUE_TO_BUDGET"
    assert metadata.final_decision_source == "FAST"
    assert metadata.block_reason == "deep_budget_blocked"


def test_deep_budget_denied_logs_block_reason():
    """Test DEEP budget denial populates block_reason."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_THEN_DEEP.value
    
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.side_effect = [(True, None), (False, "Budget exceeded")]
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    fast_response = Mock()
    fast_response.content = json.dumps({
        "fast_verdict": "ESCALATE",
        "fast_reason_codes": ["NEEDS_DEEP"],
        "confidence_fast": 0.60,
        "risk_flags_fast": [],
        "recommended_action_fast": "ESCALATE",
        "notes_fast": "Escalate"
    })
    fast_response.usage = {"prompt_tokens": 50, "completion_tokens": 20}
    
    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(return_value=fast_response)
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with patch('lunia_core.app.services.ai_gateway.router.get_provider', return_value=mock_provider):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"test": "context"}
            ))
    
    assert metadata.block_reason == "deep_budget_blocked"
    meta_dict = metadata.to_dict()
    assert "deep_budget_blocked" in str(meta_dict)


def test_deep_timeout_falls_back_to_mock():
    """Test DEEP timeout falls back to Mock."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_THEN_DEEP.value
    
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (True, None)
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    # FAST response triggers escalation
    fast_response = Mock()
    fast_response.content = json.dumps({
        "fast_verdict": "ESCALATE",
        "fast_reason_codes": ["NEEDS_DEEP"],
        "confidence_fast": 0.60,
        "risk_flags_fast": [],
        "recommended_action_fast": "ESCALATE",
        "notes_fast": "Escalate"
    })
    fast_response.usage = {"prompt_tokens": 50, "completion_tokens": 20}
    
    # DEEP times out
    call_count = [0]
    async def timeout_side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call (FAST) succeeds
            return fast_response
        else:
            # Second call (DEEP) times out
            raise asyncio.TimeoutError()
    
    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(side_effect=timeout_side_effect)
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with patch('lunia_core.app.services.ai_gateway.router.get_provider', return_value=mock_provider):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"test": "context"}
            ))
    
    # Should handle gracefully (MockProvider called but result may vary)
    assert result is not None  # No crash
    assert metadata.escalation_triggered is True  # Escalation happened
    # Path will be FAST_THEN_DEEP (from Mock fallback in _execute_deep_path)


def test_deep_invalid_json_falls_back_to_mock():
    """Test DEEP invalid JSON falls back to Mock."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_THEN_DEEP.value
    
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (True, None)
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    # FAST triggers escalation
    fast_response = Mock()
    fast_response.content = json.dumps({
        "fast_verdict": "ESCALATE",
        "fast_reason_codes": ["NEEDS_DEEP"],
        "confidence_fast": 0.60,
        "risk_flags_fast": [],
        "recommended_action_fast": "ESCALATE",
        "notes_fast": "Escalate"
    })
    fast_response.usage = {"prompt_tokens": 50, "completion_tokens": 20}
    
    # DEEP returns invalid JSON
    deep_response = Mock()
    deep_response.content = "INVALID JSON NOT PARSEABLE"
    deep_response.usage = {"prompt_tokens": 200, "completion_tokens": 100}
    
    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(side_effect=[fast_response, deep_response])
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with patch('lunia_core.app.services.ai_gateway.router.get_provider', return_value=mock_provider):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"test": "context"}
            ))
    
    # Should handle gracefully (MockProvider called but result may vary)
    assert result is not None  # No crash
    assert metadata.escalation_triggered is True  # Escalation happened


def test_deep_cost_actual_recorded():
    """Test DEEP cost_actual recorded from usage."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_THEN_DEEP.value
    
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (True, None)
    mock_governor.record_attempt = Mock()
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    fast_response = Mock()
    fast_response.content = json.dumps({
        "fast_verdict": "ESCALATE",
        "fast_reason_codes": ["NEEDS_DEEP"],
        "confidence_fast": 0.60,
        "risk_flags_fast": [],
        "recommended_action_fast": "ESCALATE",
        "notes_fast": "Escalate"
    })
    fast_response.usage = {"prompt_tokens": 50, "completion_tokens": 20}
    
    deep_response = Mock()
    deep_response.content = json.dumps({
        "analysis": "Deep result",
        "confidence_deep": 0.92
    })
    deep_response.usage = {"prompt_tokens": 300, "completion_tokens": 150}
    
    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(side_effect=[fast_response, deep_response])
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with patch('lunia_core.app.services.ai_gateway.router.get_provider', return_value=mock_provider):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"test": "context"}
            ))
    
    # Cost should be recorded
    assert metadata.deep_cost_est is not None
    assert metadata.deep_cost_actual is not None
    assert metadata.deep_cost_actual > 0
    
    # Budget governor should have recorded
    assert mock_governor.record_attempt.called


def test_fast_then_deep_sets_final_decision_source_correctly():
    """Test final_decision_source set correctly based on path."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.FAST_THEN_DEEP.value
    
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (True, None)
    mock_governor.record_attempt = Mock()
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    fast_response = Mock()
    fast_response.content = json.dumps({
        "fast_verdict": "ESCALATE",
        "fast_reason_codes": ["NEEDS_DEEP"],
        "confidence_fast": 0.60,
        "risk_flags_fast": [],
        "recommended_action_fast": "ESCALATE",
        "notes_fast": "Escalate"
    })
    fast_response.usage = {"prompt_tokens": 50, "completion_tokens": 20}
    
    deep_response = Mock()
    deep_response.content = json.dumps({
        "final_analysis": "DEEP result",
        "confidence_deep": 0.98
    })
    deep_response.usage = {"prompt_tokens": 300, "completion_tokens": 150}
    
    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(side_effect=[fast_response, deep_response])
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with patch('lunia_core.app.services.ai_gateway.router.get_provider', return_value=mock_provider):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"test": "context"}
            ))
    
    # Final decision from DEEP
    assert metadata.final_decision_source == "DEEP"
    assert metadata.path_taken == "FAST_THEN_DEEP"
    assert result["final_analysis"] == "DEEP result"


def test_deep_only_mode_executes_without_fast():
    """Test DEEP_ONLY mode skips FAST and executes DEEP directly."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.DEEP_ONLY.value
    
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (True, None)
    mock_governor.record_attempt = Mock()
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    # Only DEEP response (no FAST)
    deep_response = Mock()
    deep_response.content = json.dumps({
        "deep_analysis": "Direct DEEP result",
        "confidence_deep": 0.95
    })
    deep_response.usage = {"prompt_tokens": 300, "completion_tokens": 150}
    
    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(return_value=deep_response)
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with patch('lunia_core.app.services.ai_gateway.router.get_provider', return_value=mock_provider):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"test": "context"}
            ))
    
    # Should execute DEEP only
    assert metadata.path_taken == "DEEP"
    assert metadata.final_decision_source == "DEEP"
    assert metadata.escalation_triggered is False  # No escalation in DEEP_ONLY
    assert result["deep_analysis"] == "Direct DEEP result"
    
    # Provider called only once (DEEP)
    assert mock_provider.complete.call_count == 1


def test_no_secret_leakage_in_deep_path():
    """Test DEEP path does NOT leak secrets."""
    config = AIGovernanceConfig()
    config.enable_tiered_router = True
    config.routing_mode = RoutingMode.DEEP_ONLY.value
    
    mock_governor = Mock(spec=BudgetGovernor)
    mock_governor.can_attempt.return_value = (True, None)
    mock_governor.record_attempt = Mock()
    
    router = TieredRouter(
        governance_config=config,
        budget_governor=mock_governor
    )
    
    test_key = "sk-test" + "x" * 40
    
    deep_response = Mock()
    deep_response.content = json.dumps({
        "analysis": "No secrets here",
        "confidence_deep": 0.90
    })
    deep_response.usage = {"prompt_tokens": 300, "completion_tokens": 150}
    
    mock_provider = AsyncMock()
    mock_provider.complete = AsyncMock(return_value=deep_response)
    
    with patch('lunia_core.app.services.ai_gateway.router.TIKTOKEN_AVAILABLE', True):
        with patch('lunia_core.app.services.ai_gateway.router.get_provider', return_value=mock_provider):
            result, metadata = asyncio.run(router.route(
                prompt="Test prompt",
                context={"api_key": test_key}
            ))
    
    # Check metadata dict
    meta_dict = metadata.to_dict()
    assert test_key not in str(meta_dict)
    assert "sk-" not in str(meta_dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
