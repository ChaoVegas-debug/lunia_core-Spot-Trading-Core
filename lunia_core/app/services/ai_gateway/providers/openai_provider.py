"""
AI Gateway Provider: OpenAI

Real OpenAI LLM provider with:
- Retry logic (429, 5xx) with exponential backoff
- Strict timeout enforcement
- Token/cost estimation and accounting
- Privacy scrubbing
- Fail-closed error handling

CRITICAL: This provider OBEYS Phase 8.0 governance (kill switch, budget caps).
"""

import asyncio
import json
import logging
import time
import random
from typing import Dict, Optional

from . import AbstractProvider, LLMResponse
from ..secrets import get_openai_api_key, validate_openai_env, get_openai_config
from ..tokenization import estimate_prompt_and_completion
from ..cost import estimate_cost as calc_cost
from ..privacy import scrub_pii

logger = logging.getLogger(__name__)

# Try to import OpenAI SDK
OPENAI_SDK_AVAILABLE = False
try:
    import openai
    from openai import OpenAI, AsyncOpenAI
    OPENAI_SDK_AVAILABLE = True
    logger.info("OpenAI SDK available")
except ImportError:
    logger.error(
        "OpenAI SDK not installed. Install with: pip install openai. "
        "OpenAIProvider will fail to initialize."
    )


class ProviderError(Exception):
    """Base exception for provider errors."""
    pass


class ProviderTimeoutError(ProviderError):
    """Provider call exceeded timeout."""
    pass


class ProviderRateLimitError(ProviderError):
    """Provider rate limit (429) hit."""
    pass


class ProviderAuthError(ProviderError):
    """Provider authentication failed."""
    pass


class ProviderConnectionError(ProviderError):
    """Provider connection failed."""
    pass


class OpenAIProvider(AbstractProvider):
    """
    OpenAI LLM provider with retry logic and governance integration.
    
    Features:
    - Retry on 429 (rate limit) and transient 5xx
    - Exponential backoff with jitter
    - Strict timeout enforcement
    - Token/cost estimation before call
    - Actual token/cost accounting after call
    - Privacy scrubbing (PII removed before sending)
    - Fail-closed on all errors
    
    Environment Variables:
    - OPENAI_API_KEY (required)
    - OPENAI_MODEL (default: gpt-4o-mini)
    - OPENAI_BASE_URL (optional)
    - OPENAI_TIMEOUT_SEC (default: 30)
    - OPENAI_MAX_RETRIES (default: 2)
    - OPENAI_ORG (optional)
    - OPENAI_PROJECT (optional)
    """
    
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_sec: Optional[float] = None,
        max_retries: Optional[int] = None
    ):
        """
        Initialize OpenAI provider.
        
        Args:
            model: Model name (default: from env or "gpt-4o-mini")
            api_key: API key (default: from env OPENAI_API_KEY)
            timeout_sec: Timeout in seconds (default: from env or 30)
            max_retries: Max retry attempts (default: from env or 2)
        
        Raises:
            ProviderError: If SDK not available or env invalid
        """
        # Check SDK availability
        if not OPENAI_SDK_AVAILABLE:
            raise ProviderError("OpenAI SDK not installed")
        
        # Load config from env
        config = get_openai_config()
        
        # Override with provided args
        self.api_key = api_key or config["api_key"]
        self.model_name = model or config["model"]
        self.timeout_sec = timeout_sec if timeout_sec is not None else config["timeout_sec"]
        self.max_retries = max_retries if max_retries is not None else config["max_retries"]
        self.base_url = config["base_url"]
        self.org = config["org"]
        self.project = config["project"]
        
        # Validate API key
        if not self.api_key:
            raise ProviderAuthError("OPENAI_API_KEY not set")
        
        ok, reason = validate_openai_env()
        if not ok:
            raise ProviderAuthError(f"OpenAI env invalid: {reason}")
        
        # Initialize client
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout_sec,
            max_retries=0,  # We handle retries manually
            organization=self.org,
            default_headers={"OpenAI-Project": self.project} if self.project else None
        )
        
        # Call parent init
        super().__init__(model=self.model_name, api_key=self.api_key)
        
        logger.info(
            f"OpenAIProvider initialized: model={self.model_name}, "
            f"timeout={self.timeout_sec}s, max_retries={self.max_retries}"
        )
    
    async def complete(self, prompt: str, context: Dict) -> LLMResponse:
        """
        Execute inference with retry logic.
        
        Flow:
        1. Privacy scrub (remove PII from prompt)
        2. Estimate tokens/cost (for logging)
        3. Call OpenAI API with retry on 429/5xx
        4. Parse JSON response
        5. Compute actual cost
        6. Return LLMResponse
        
        Args:
            prompt: Full prompt (system + user)
            context: Context dict (for logging, not sent to API)
        
        Returns:
            LLMResponse with content and metadata
        
        Raises:
            ProviderTimeoutError: If inference exceeds timeout
            ProviderRateLimitError: If 429 persists after retries
            Provider Error: On other API errors
        """
        start_time = time.time()
        
        # Step 1: Privacy scrub
        scrubbed_prompt = scrub_pii(prompt)
        
        # Step 2: Estimate tokens/cost (for pre-call logging)
        prompt_tokens_est, completion_tokens_est = estimate_prompt_and_completion(
            scrubbed_prompt,
            self.model_name,
            max_completion_tokens=400  # Conservative estimate
        )
        cost_est = calc_cost(self.model_name, prompt_tokens_est, completion_tokens_est)
        
        logger.debug(
            f"OpenAI inference starting: model={self.model_name}, "
            f"est_tokens={prompt_tokens_est+completion_tokens_est}, "
            f"est_cost=${cost_est:.6f}"
        )
        
        # Step 3: Call API with retry logic
        response_data = await self._call_with_retry(scrubbed_prompt)
        
        # Step 4: Parse response
        try:
            content = response_data.choices[0].message.content
            
            # Parse JSON (we request JSON mode)
            try:
                json.loads(content)  # Validate JSON
            except json.JSONDecodeError as e:
                logger.error(f"OpenAI returned invalid JSON: {e}")
                raise ProviderError(f"Invalid JSON response: {e}")
            
            # Get actual token usage
            usage = response_data.usage
            if usage:
                prompt_tokens = usage.prompt_tokens
                completion_tokens = usage.completion_tokens
            else:
                # Fallback to estimates if usage missing
                logger.warning("OpenAI response missing usage data, using estimates")
                prompt_tokens = prompt_tokens_est
                completion_tokens = completion_tokens_est
            
            # Step 5: Compute actual cost
            cost_usd = calc_cost(self.model_name, prompt_tokens, completion_tokens)
            
            # Compute latency
            latency_ms = int((time.time() - start_time) * 1000)
            
            logger.info(
                f"OpenAI inference complete: model={response_data.model}, "
                f"tokens={prompt_tokens+completion_tokens}, "
                f"cost=${cost_usd:.6f}, latency={latency_ms}ms"
            )
            
            # Step 6: Return response
            return LLMResponse(
                content=content,
                model=response_data.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                cost_usd=cost_usd
            )
        
        except (IndexError, AttributeError) as e:
            logger.error(f"OpenAI response parsing failed: {e}")
            raise ProviderError(f"Response parsing failed: {e}")
    
    async def _call_with_retry(self, prompt: str) -> any:
        """
        Call OpenAI API with exponential backoff retry.
        
        Retry logic:
        - 429 (rate limit): retry with backoff
        - 5xx (server error): retry with backoff
        - 4xx (client error, except 429): fail immediately
        - Timeout: fail immediately
        
        Backoff:
        - Base: 0.5s
        - Multiplier: 2x
        - Jitter: ±20%
        - Max: timeout_sec / 2 (leave room for final attempt)
        
        Args:
            prompt: Scrubbed prompt
        
        Returns:
            OpenAI response object
        
        Raises:
            ProviderTimeoutError, ProviderRateLimitError, ProviderError
        """
        attempt = 0
        backoff_sec = 0.5  # Initial backoff
        
        while attempt <= self.max_retries:
            attempt += 1
            
            try:
                # Make API call
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You are a financial signal analysis AI. Return only valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},  # Force JSON mode
                    max_tokens=400,
                    temperature=0.7,
                    timeout=self.timeout_sec
                )
                
                # Success
                return response
            
            except openai.APITimeoutError as e:
                logger.error(f"OpenAI timeout (attempt {attempt}/{self.max_retries+1}): {e}")
                raise ProviderTimeoutError(f"API timeout after {self.timeout_sec}s")
            
            except openai.RateLimitError as e:
                logger.warning(f"OpenAI rate limit (429) (attempt {attempt}/{self.max_retries+1}): {e}")
                
                if attempt > self.max_retries:
                    raise ProviderRateLimitError(f"Rate limit persisted after {self.max_retries} retries")
                
                # Exponential backoff with jitter
                jitter = random.uniform(0.8, 1.2)  # ±20%
                sleep_sec = min(backoff_sec * jitter, self.timeout_sec / 2)
                
                logger .info(f"Retrying after {sleep_sec:.2f}s backoff")
                await asyncio.sleep(sleep_sec)
                
                backoff_sec *= 2  # Double for next attempt
            
            except (openai.APIConnectionError, openai.InternalServerError) as e:
                logger.warning(f"OpenAI server error (attempt {attempt}/{self.max_retries+1}): {e}")
                
                if attempt > self.max_retries:
                    raise ProviderConnectionError(f"Server error persisted after {self.max_retries} retries: {e}")
                
                # Retry with backoff
                jitter = random.uniform(0.8, 1.2)
                sleep_sec = min(backoff_sec * jitter, self.timeout_sec / 2)
                
                logger.info(f"Retrying after {sleep_sec:.2f}s backoff")
                await asyncio.sleep(sleep_sec)
                
                backoff_sec *= 2
            
            except openai.AuthenticationError as e:
                logger.error(f"OpenAI authentication error: {e}")
                raise ProviderAuthError(f"Authentication failed: {e}")
            
            except openai.BadRequestError as e:
                logger.error(f"OpenAI bad request: {e}")
                raise ProviderError(f"Bad request: {e}")
            
            except Exception as e:
                logger.error(f"OpenAI unexpected error: {e}")
                raise ProviderError(f"Unexpected error: {e}")
        
        # Should not reach here
        raise ProviderError("Retry loop exhausted")
    
    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Estimate cost in USD.
        
        Args:
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
        
        Returns:
            Estimated cost in USD
        """
        return calc_cost(self.model_name, prompt_tokens, completion_tokens)
