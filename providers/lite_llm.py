"""
LiteLLM Provider.

Multi-provider LLM support using LiteLLM.
Supports OpenAI, Mistral, Anthropic, Google, Local models, and more.

Installation:
    pip install litellm

Usage:
    from providers import LiteLLMProvider
    
    provider = LiteLLMProvider(
        model="mistral/mistral-large",
        api_key="your_api_key"
    )
    
    response = await provider.complete("Hello, how are you?")
"""

from typing import Any, Dict, List, Optional

from .base import LLMConfig, LLMMessage, LLMProvider, LLMResponse, MessageRole, ProviderType


# Default models for each provider
DEFAULT_MODELS = {
    ProviderType.OPENAI: "gpt-3.5-turbo",
    ProviderType.MISTRAL: "mistral/mistral-small",
    ProviderType.ANTHROPIC: "anthropic/claude-3-sonnet-20240229",
    ProviderType.GOOGLE: "gemini/gemini-pro",
    ProviderType.LITELLML: "mistral/mistral-large",
}


class LiteLLMProvider(LLMProvider):
    """
    LLM Provider using LiteLLM for multi-provider support.
    
    LiteLLM provides a unified interface for 100+ LLM providers including:
    - OpenAI (GPT-4, GPT-3.5)
    - Mistral (mistral-large, mistral-small, mixtral)
    - Anthropic (Claude 3, Claude 2)
    - Google (Gemini Pro, Gemini Ultra)
    - Local models (via Ollama, vLLM, etc.)
    - And many more...
    
    See: https://docs.litellm.ai/docs/providers
    """
    
    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        api_base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: float = 60.0,
        **kwargs
    ):
        """
        Initialize the LiteLLM provider.
        
        Args:
            model: Model identifier (e.g., "mistral/mistral-large", "gpt-4")
            api_key: API key for the provider
            api_base_url: Custom API base URL
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds
            **kwargs: Additional LiteLLM configuration
        """
        # Detect provider from model name
        provider = self._detect_provider(model)
        
        config = LLMConfig(
            provider=provider,
            model=model,
            api_key=api_key,
            api_base_url=api_base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            **kwargs
        )
        
        super().__init__(config)
        self._kwargs = kwargs
    
    def _detect_provider(self, model: str) -> ProviderType:
        """Detect provider type from model name."""
        model_lower = model.lower()
        
        if any(x in model_lower for x in ["gpt-", "openai", "azure"]):
            return ProviderType.OPENAI
        elif any(x in model_lower for x in ["mistral", "mixtral"]):
            return ProviderType.MISTRAL
        elif any(x in model_lower for x in ["claude", "anthropic"]):
            return ProviderType.ANTHROPIC
        elif any(x in model_lower for x in ["gemini", "google"]):
            return ProviderType.GOOGLE
        elif any(x in model_lower for x in ["llama", "phi", "vicuna", "hosted_vllm"]):
            return ProviderType.LOCAL
        else:
            return ProviderType.LITELLML
    
    async def complete(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        messages: Optional[List[LLMMessage]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a completion using LiteLLM.
        """
        try:
            import litellm
        except ImportError:
            raise RuntimeError(
                "LiteLLM is not installed. Please install it with: pip install litellm"
            )
        
        # Build messages list
        chat_messages = []
        
        if system_message:
            chat_messages.append({"role": "system", "content": system_message})
        
        if messages:
            chat_messages.extend([m.to_dict() for m in messages])
        else:
            # Simple completion mode
            chat_messages.append({"role": "user", "content": prompt})
        
        # Call LiteLLM
        response = await litellm.acompletion(
            model=self.config.model,
            messages=chat_messages,
            temperature=temperature or self.config.temperature,
            max_tokens=max_tokens or self.config.max_tokens,
            timeout=self.config.timeout,
            api_key=self.config.api_key,
            **kwargs
        )
        
        # Extract response
        content = response.choices[0].message.content if response.choices else ""
        
        return LLMResponse(
            content=content,
            model=self.config.model,
            provider=self.config.provider.value,
            finish_reason=response.choices[0].finish_reason if response.choices else None,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            } if response.usage else None,
            raw_response=response.model_dump() if hasattr(response, "model_dump") else dict(response)
        )
    
    async def chat(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a chat completion using LiteLLM.
        """
        return await self.complete(
            prompt="",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
    
    async def check_availability(self) -> bool:
        """Check if LiteLLM and the provider are available."""
        try:
            import litellm
            self._is_available = True
            return True
        except ImportError:
            self._is_available = False
            return False
