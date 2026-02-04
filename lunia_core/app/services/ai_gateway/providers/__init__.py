"""
AI Gateway: Abstract Provider Interface

Base class for LLM providers (OpenAI, Anthropic, Local, Mock).

Phase 8.1A: Added OpenAI provider with retry logic and governance integration.
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Standardized LLM response."""
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    cost_usd: float


class AbstractProvider(ABC):
    """
    Abstract LLM provider interface.
    
    All providers must implement:
    - complete(): Send prompt, get response
    - estimate_cost(): Calculate cost before inference
    """
    
    def __init__(self, model: str, api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key
    
    @abstractmethod
    async def complete(self, prompt: str, context: Dict) -> LLMResponse:
        """
        Send prompt to LLM and get response.
        
        Args:
            prompt: System prompt + user prompt
            context: Structured context dictionary
        
        Returns:
            LLMResponse with content and metadata
        
        Raises:
            TimeoutError: If inference exceeds timeout
            Exception: On API errors
        """
        pass
    
    @abstractmethod
    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Estimate cost in USD.
        
        Args:
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
        
        Returns:
            Estimated cost in USD
        """
        pass
    
    def get_provider_name(self) -> str:
        """Get provider name (for logging)."""
        return self.__class__.__name__.replace("Provider", "").lower()


# Import providers
from .mock import MockProvider

# Try to import OpenAI provider (may fail if SDK not installed)
try:
    from .openai_provider import OpenAIProvider, ProviderError
    OPENAI_AVAILABLE = True
except ImportError as e:
    logger.warning(f"OpenAI provider not available: {e}")
    OpenAIProvider = None
    ProviderError = Exception
    OPENAI_AVAILABLE = False


def get_provider(
    provider_name: str,
    model: Optional[str] = None,
    **kwargs
) -> Optional[AbstractProvider]:
    """
    Get provider instance by name.
    
    Args:
        provider_name: "openai", "mock", etc.
        model: Model name (optional, uses default for provider)
        **kwargs: Additional provider-specific config
    
    Returns:
        Provider instance, or None if unavailable
    
    Example:
        >>> provider = get_provider("openai", model="gpt-4o-mini")
        >>> provider = get_provider("mock")
    """
    provider_name = provider_name.lower()
    
    if provider_name == "mock":
        return MockProvider(model=model or "mock-v1")
    
    elif provider_name == "openai":
        if not OPENAI_AVAILABLE:
            logger.error("OpenAI provider requested but not available")
            return None
        
        try:
            return OpenAIProvider(model=model, **kwargs)
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI provider: {e}")
            return None
    
    else:
        logger.error(f"Unknown provider: {provider_name}")
        return None


# Export public API
__all__ = [
    "AbstractProvider",
    "LLMResponse",
    "MockProvider",
    "OpenAIProvider",
    "get_provider",
    "OPENAI_AVAILABLE",
]
