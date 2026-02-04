"""
Phase 8.1A: Dependency Verification Tests

Verifies that all required dependencies for Phase 8.0 + 8.1A are installed
and can be imported successfully.

This test ensures:
1. jsonschema (Phase 8.0 schema validation)
2. openai SDK (Phase 8.1A provider)
3. tiktoken (Phase 8.1A token estimation)
4. pytest-asyncio (test framework)

Running this test ensures the environment is ready for 7/7 GREEN tests.
"""

import pytest
import sys


def test_jsonschema_available():
    """Test that jsonschema is installed (required for Phase 8.0)."""
    try:
        import jsonschema
        
        # Check version
        version = getattr(jsonschema, '__version__', 'unknown')
        print(f"✅ jsonschema {version} available")
        
        # Verify basic functionality
        schema = {"type": "object", "properties": {"test": {"type": "string"}}}
        instance = {"test": "value"}
        jsonschema.validate(instance, schema)
        
        assert True
    except ImportError as e:
        pytest.fail(
            f"jsonschema not installed: {e}\n"
            "Install with: pip3 install jsonschema>=4.17.0"
        )


def test_openai_sdk_available():
    """Test that OpenAI SDK is installed (required for Phase 8.1A)."""
    try:
        import openai
        
        # Check version
        version = getattr(openai, '__version__', 'unknown')
        print(f"✅ openai {version} available")
        
        # Verify basic imports
        from openai import OpenAI, AsyncOpenAI
        assert OpenAI is not None
        assert AsyncOpenAI is not None
        
    except ImportError as e:
        pytest.fail(
            f"openai SDK not installed: {e}\n"
            "Install with: pip3 install openai>=1.0.0"
        )


def test_tiktoken_available():
    """Test that tiktoken is installed (required for Phase 8.1A)."""
    try:
        import tiktoken
        
        # Check version
        version = getattr(tiktoken, '__version__', 'unknown')
        print(f"✅ tiktoken {version} available")
        
        # Verify basic functionality
        encoding = tiktoken.get_encoding("cl100k_base")
        tokens = encoding.encode("Hello world")
        assert len(tokens) > 0
        
    except ImportError as e:
        pytest.fail(
            f"tiktoken not installed: {e}\n"
            "Install with: pip3 install tiktoken>=0.5.0\n"
            "WARNING: Without tiktoken, token estimation falls back to heuristic (less accurate)"
        )


def test_pytest_asyncio_available():
    """Test that pytest-asyncio is installed (required for async tests)."""
    try:
        import pytest_asyncio
        
        # Check version
        version = getattr(pytest_asyncio, '__version__', 'unknown')
        print(f"✅ pytest-asyncio {version} available")
        
    except ImportError as e:
        pytest.fail(
            f"pytest-asyncio not installed: {e}\n"
            "Install with: pip3 install pytest-asyncio>=0.21.0"
        )


def test_phase8_modules_import():
    """Test that Phase 8.0 + 8.1A modules import successfully."""
    try:
        # Phase 8.0
        from lunia_core.app.services.ai_gateway.governance import AIGovernanceConfig
        from lunia_core.app.services.ai_gateway.budget import BudgetGovernor
        from lunia_core.app.services.execution_journal.budget_model import AIBudgetUsage
        
        print("✅ Phase 8.0 modules imported")
        
        # Phase 8.1A
        from lunia_core.app.services.ai_gateway.secrets import (
            get_openai_api_key,
            validate_openai_env,
            redact_sensitive
        )
        from lunia_core.app.services.ai_gateway.tokenization import (
            estimate_tokens,
            estimate_prompt_and_completion
        )
        from lunia_core.app.services.ai_gateway.cost import (
            get_model_pricing,
            estimate_cost
        )
        from lunia_core.app.services.ai_gateway.providers import (
            get_provider,
            MockProvider,
            OPENAI_AVAILABLE
        )
        from lunia_core.app.services.ai_gateway.metrics import (
            get_ai_budget_usage_today,
            get_ai_budget_spend_today_usd
        )
        
        print("✅ Phase 8.1A modules imported")
        print(f"OpenAI provider available: {OPENAI_AVAILABLE}")
        
        assert True
        
    except ImportError as e:
        pytest.fail(f"Phase 8 modules import failed: {e}")


def test_python_version():
    """Test that Python version is supported."""
    major, minor = sys.version_info[:2]
    
    print(f"Python version: {major}.{minor}")
    
    if major < 3 or (major == 3 and minor < 10):
        pytest.fail(
            f"Python {major}.{minor} not supported. "
            "Requires Python 3.10+"
        )
    
    print(f"✅ Python {major}.{minor} supported")


def test_environment_summary():
    """Print environment summary."""
    import sys
    
    print("\n" + "="*60)
    print("PHASE 8.1A ENVIRONMENT SUMMARY")
    print("="*60)
    
    print(f"Python: {sys.version}")
    
    # Check each dependency
    deps = [
        ("jsonschema", "jsonschema"),
        ("openai", "openai"),
        ("tiktoken", "tiktoken"),
        ("pytest", "pytest"),
        ("pytest-asyncio", "pytest_asyncio"),
    ]
    
    for name, module in deps:
        try:
            mod = __import__(module)
            version = getattr(mod, '__version__', 'unknown')
            print(f"  {name:20} {version}")
        except ImportError:
            print(f"  {name:20} ❌ NOT INSTALLED")
    
    print("="*60)
    print("✅ Environment verification complete")
    print("="*60 + "\n")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
