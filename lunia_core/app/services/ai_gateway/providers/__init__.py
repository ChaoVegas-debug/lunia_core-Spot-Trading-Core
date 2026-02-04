"""
AI Gateway: Abstract Provider Interface

Base class for LLM providers (OpenAI, Anthropic, Local).
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional
from dataclasses import dataclass


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
