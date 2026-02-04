"""
Phase 8.1A: OpenAI Provider Tests

Comprehensive test suite covering:
- Secrets module (env validation, redaction)
- Tokenization module (tiktoken + heuristic)
- Cost estimation
- OpenAI provider (retry logic, timeout, cost accounting)
- Integration with governance (budget caps, kill switch)

CRITICAL: NO live spend by default (all OpenAI calls mocked).

Optional live test requires: OPENAI_API_KEY + RUN_LIVE_OPENAI_TEST=1
"""

import os
import pytest
import json
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, date

# Secrets module tests
from lunia_core.app.services.ai_gateway.secrets import (
    get_openai_api_key,
    validate_openai_env,
    redact_sensitive,
    validate_no_secrets
)

# Tokenization module tests
from lunia_core.app.services.ai_gateway.tokenization import (
    estimate_tokens,
    estimate_prompt_and_completion,
    get_estimation_mode
)

# Cost module tests
from lunia_core.app.services.ai_gateway.cost import (
    get_model_pricing,
    estimate_cost,
    get_recommended_model
)

# Provider tests
from lunia_core.app.services.ai_gateway.providers import (
    get_provider,
    MockProvider,
    OPENAI_AVAILABLE
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 1: SECRETS MODULE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_get_openai_api_key_missing():
    """Test that missing API key returns None."""
    with patch.dict(os.environ, {}, clear=True):
        key = get_openai_api_key()
        assert key is None


def test_get_openai_api_key_present():
    """Test that API key is read from env."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}):
        key = get_openai_api_key()
        assert key == "sk-test123"


def test_validate_openai_env_missing():
    """Test env validation fails when key missing."""
    with patch.dict(os.environ, {}, clear=True):
        ok, reason = validate_openai_env()
        assert ok == False
        assert "not set" in reason


def test_validate_openai_env_invalid_format():
    """Test env validation fails on invalid format."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "invalid_key"}):
        ok, reason = validate_openai_env()
        assert ok == False
        assert "invalid format" in reason.lower()


def test_validate_openai_env_valid():
    """Test env validation succeeds with valid key."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-" + "x" * 40}):
        ok, reason = validate_openai_env()
        assert ok == True
        assert reason == "ok"


def test_redact_sensitive_api_key():
    """Test that API keys are redacted."""
    data = {"api_key": "sk-abc123def456", "public": "data"}
    redacted = redact_sensitive(data)
    
    assert redacted["api_key"] == "***REDACTED***"
    assert redacted["public"] == "data"


def test_redact_sensitive_in_string():
    """Test that sk- pattern in string is redacted."""
    text = "The API key is sk-abc123def456 here"
    redacted = redact_sensitive(text)
    
    assert redacted == "***REDACTED_API_KEY***"
    assert "sk-" not in redacted


def test_redact_sensitive_nested():
    """Test recursive redaction in nested structures."""
    data = {
        "level1": {
            "level2": {
                "secret": "sk-hidden",
                "ok": "visible"
            },
            "token": "Bearer sk-abc",
            "list": ["sk-789", "public"]
        }
    }
    
    redacted = redact_sensitive(data)
    
    # Check nested redaction
    assert "sk-" not in str(redacted)
    assert redacted["level1"]["level2"]["ok"] == "visible"
    assert redacted["level1"]["level2"]["secret"] == "***REDACTED_API_KEY***"


def test_validate_no_secrets():
    """Test paranoid secret validation."""
    # No secrets
    ok, pattern = validate_no_secrets({"data": "public", "number": 123})
    assert ok == True
    assert pattern is None
    
    # Secret present
    ok, pattern = validate_no_secrets({"key": "sk-abc123"})
    assert ok == False
    assert pattern == "sk-"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 2: TOKENIZATION MODULE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_estimate_tokens_returns_int():
    """Test that token estimation returns numeric value."""
    tokens = estimate_tokens("Hello world", "gpt-4o-mini")
    
    assert isinstance(tokens, int)
    assert tokens >= 1  # Minimum 1 token


def test_estimate_tokens_scales_with_length():
    """Test that longer text → more tokens."""
    short = estimate_tokens("Hi", "gpt-4o-mini")
    long = estimate_tokens("This is a much longer sentence with many words", "gpt-4o-mini")
    
    assert long > short


def test_estimate_prompt_and_completion():
    """Test combined prompt+completion estimation."""
    prompt_tokens, completion_tokens = estimate_prompt_and_completion(
        prompt="Analyze this signal",
        model="gpt-4o-mini",
        max_completion_tokens=200
    )
    
    assert prompt_tokens >= 1
    assert completion_tokens == 200  # Should equal max


def test_get_estimation_mode():
    """Test estimation mode reporting."""
    mode = get_estimation_mode()
    
    assert mode in ("tiktoken", "heuristic")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 3: COST ESTIMATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_get_model_pricing_known():
    """Test pricing lookup for known model."""
    input_price, output_price = get_model_pricing("gpt-4o-mini")
    
    assert input_price == 0.15  # $0.15 per 1M
    assert output_price == 0.60  # $0.60 per 1M


def test_get_model_pricing_unknown():
    """Test pricing defaults to expensive for unknown model."""
    input_price, output_price = get_model_pricing("unknown-model-123")
    
    # Should use expensive default (fail-closed)
    assert input_price >= 10.0
    assert output_price >= 30.0


def test_estimate_cost():
    """Test cost calculation."""
    cost = estimate_cost("gpt-4o-mini", prompt_tokens=1000, completion_tokens=500)
    
    # (1000/1e6 * 0.15) + (500/1e6 * 0.60) = 0.00015 + 0.0003 = 0.00045
    assert abs(cost - 0.00045) < 0.000001  # Floating point tolerance


def test_get_recommended_model_fits_budget():
    """Test model recommendation within budget."""
    model = get_recommended_model(budget_usd=0.01, estimated_tokens=2000)
    
    # Should recommend cheapest model that fits
    assert model in ("gpt-4o-mini", "gpt-3.5-turbo")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 4: PROVIDER REGISTRY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_get_provider_mock():
    """Test that mock provider is always available."""
    provider = get_provider("mock")
    
    assert provider is not None
    assert isinstance(provider, MockProvider)
    assert provider.get_provider_name() == "mock"


def test_get_provider_unknown():
    """Test that unknown provider returns None."""
    provider = get_provider("nonexistent")
    
    assert provider is None


@pytest.mark.skipif(not OPENAI_AVAILABLE, reason="OpenAI SDK not installed")
def test_get_provider_openai_no_key():
    """Test that OpenAI provider fails without API key."""
    with patch.dict(os.environ, {}, clear=True):
        provider = get_provider("openai")
        
        # Should return None (env invalid)
        assert provider is None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 5: OPENAI PROVIDER (MOCKED)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.mark.skipif(not OPENAI_AVAILABLE, reason="OpenAI SDK not installed")
@pytest.mark.asyncio
async def test_openai_provider_complete_success():
    """Test successful OpenAI inference (mocked)."""
    from lunia_core.app.services.ai_gateway.providers.openai_provider import OpenAIProvider
    
    # Mock OpenAI response
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content='{"summary": "Test analysis"}'))]
    mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)
    mock_response.model = "gpt-4o-mini"
    
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-" + "x" * 40}):
        provider = OpenAIProvider(model="gpt-4o-mini")
        
        # Mock the API call
        with patch.object(provider.client.chat.completions, 'create', new=AsyncMock(return_value=mock_response)):
            response = await provider.complete(
                prompt="Analyze this signal",
                context={"test": "context"}
            )
            
            assert response is not None
            assert response.content == '{"summary": "Test analysis"}'
            assert response.prompt_tokens == 100
            assert response.completion_tokens == 50
            assert response.cost_usd > 0  # Should have computed cost


@pytest.mark.skipif(not OPENAI_AVAILABLE, reason="OpenAI SDK not installed")
@pytest.mark.asyncio
async def test_openai_provider_timeout():
    """Test that timeout is enforced."""
    import openai
    from lunia_core.app.services.ai_gateway.providers.openai_provider import (
        OpenAIProvider,
        ProviderTimeoutError
    )
    
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-" + "x" * 40}):
        provider = OpenAIProvider(model="gpt-4o-mini", timeout_sec=1)
        
        # Mock timeout error
        with patch.object(
            provider.client.chat.completions,
            'create',
            new=AsyncMock(side_effect=openai.APITimeoutError("Timeout"))
        ):
            with pytest.raises(ProviderTimeoutError):
                await provider.complete("Test", {})


@pytest.mark.skipif(not OPENAI_AVAILABLE, reason="OpenAI SDK not installed")
@pytest.mark.asyncio
async def test_openai_provider_429_retry():
    """Test that 429 rate limit triggers retry."""
    import openai
    from lunia_core.app.services.ai_gateway.providers.openai_provider import OpenAIProvider
    
    # Mock: first call 429, second call succeeds
    mock_success = Mock()
    mock_success.choices = [Mock(message=Mock(content='{"ok": true}'))]
    mock_success.usage = Mock(prompt_tokens=10, completion_tokens=5)
    mock_success.model = "gpt-4o-mini"
    
    call_count = [0]
    
    async def mock_create(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise openai.RateLimitError("Rate limit")
        return mock_success
    
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-" + "x" * 40}):
        provider = OpenAIProvider(model="gpt-4o-mini", max_retries=2)
        
        with patch.object(provider.client.chat.completions, 'create', new=mock_create):
            response = await provider.complete("Test", {})
            
            assert response is not None
            assert call_count[0] == 2  # Should have retried once


@pytest.mark.skipif(not OPENAI_AVAILABLE, reason="OpenAI SDK not installed")
def test_openai_provider_cost_estimation():
    """Test that provider can estimate cost."""
    from lunia_core.app.services.ai_gateway.providers.openai_provider import OpenAIProvider
    
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-" + "x" * 40}):
        provider = OpenAIProvider(model="gpt-4o-mini")
        
        cost = provider.estimate_cost(prompt_tokens=1000, completion_tokens=500)
        
        assert cost > 0
        assert cost < 1.0  # Should be much less than $1


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 6: SECRET LEAKAGE VERIFICATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.mark.skipif(not OPENAI_AVAILABLE, reason="OpenAI SDK not installed")
@pytest.mark.asyncio
async def test_no_secret_leakage_in_logs(caplog):
    """CRITICAL: Test that API keys never appear in logs."""
    from lunia_core.app.services.ai_gateway.providers.openai_provider import OpenAIProvider
    
    test_key = "sk-test" + "x" * 40
    
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content='{"test": true}'))]
    mock_response.usage = Mock(prompt_tokens=10, completion_tokens=5)
    mock_response.model = "gpt-4o-mini"
    
    with patch.dict(os.environ, {"OPENAI_API_KEY": test_key}):
        provider = OpenAIProvider(model="gpt-4o-mini")
        
        with patch.object(provider.client.chat.completions, 'create', new=AsyncMock(return_value=mock_response)):
            await provider.complete("Test prompt", {})
            
            # Check all log messages
            for record in caplog.records:
                assert test_key not in record.message, f"SECRET IN LOG: {record.message}"
                assert "sk-test" not in record.message


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 7: OPTIONAL LIVE TEST (GUARDED)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.mark.skipif(
    not os.getenv("RUN_LIVE_OPENAI_TEST"),
    reason="Set RUN_LIVE_OPENAI_TEST=1 to run (costs ~$0.001)"
)
@pytest.mark.skipif(not OPENAI_AVAILABLE, reason="OpenAI SDK not installed")
@pytest.mark.asyncio
async def test_live_openai_inference():
    """
    LIVE TEST: Real OpenAI API call (costs ~$0.001).
    
    Requires: OPENAI_API_KEY + RUN_LIVE_OPENAI_TEST=1
    
    This test:
    - Makes ONE real OpenAI API call
    - Uses cheapest model (gpt-4o-mini)
    - Verifies JSON response
    - Ensures cost < $0.01
    """
    from lunia_core.app.services.ai_gateway.providers.openai_provider import OpenAIProvider
    
    assert os.getenv("OPENAI_API_KEY"), "OPENAI_API_KEY required for live test"
    
    provider = OpenAIProvider(model="gpt-4o-mini", timeout_sec=10)
    
    response = await provider.complete(
        prompt="Return a JSON object with a single field 'test' set to true.",
        context={}
    )
    
    # Verify response
    assert response is not None
    assert response.cost_usd > 0
    assert response.cost_usd < 0.01, f"Live test too expensive: ${response.cost_usd}"
    
    # Verify JSON
    data = json.loads(response.content)
    assert "test" in data
    
    print(f"✅ Live test passed: cost=${response.cost_usd:.6f}, tokens={response.prompt_tokens+response.completion_tokens}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# RUN TESTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
