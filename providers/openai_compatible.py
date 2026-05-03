"""
OpenAI-compatible LLM Providers.

Direct API implementations for OpenAI, Mistral, Anthropic, and other
OpenAI-compatible providers.

No external dependencies required (uses httpx for HTTP requests).
"""

import json
from typing import Any, Dict, List, Optional

import httpx

from .base import LLMConfig, LLMMessage, LLMProvider, LLMResponse, MessageRole, ProviderType


class OpenAICompatibleProvider(LLMProvider):
    """
    Base class for OpenAI-compatible API providers.
    
    Supports any provider that implements the OpenAI API specification.
    """
    
    # Default API base URLs for each provider
    BASE_URLS = {
        ProviderType.OPENAI: "https://api.openai.com/v1",
        ProviderType.MISTRAL: "https://api.mistral.ai/v1",
        ProviderType.ANTHROPIC: "https://api.anthropic.com/v1",
    }
    
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
        Initialize the OpenAI-compatible provider.
        
        Args:
            model: Model identifier
            api_key: API key for authentication
            api_base_url: Custom API base URL
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds
            **kwargs: Additional configuration
        """
        # Remove 'provider' from kwargs if present (it will be auto-detected)
        kwargs.pop('provider', None)
        
        # Detect provider from model or base URL
        provider = self._detect_provider(model, api_base_url)
        
        config = LLMConfig(
            provider=provider,
            model=model,
            api_key=api_key,
            api_base_url=api_base_url or self.BASE_URLS.get(provider, "https://api.openai.com/v1"),
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            **kwargs
        )
        
        super().__init__(config)
        self._client = None
    
    def _detect_provider(self, model: str, api_base_url: Optional[str]) -> ProviderType:
        """Detect provider type from model or API URL."""
        if api_base_url:
            api_lower = api_base_url.lower()
            if "mistral" in api_lower:
                return ProviderType.MISTRAL
            elif "anthropic" in api_lower:
                return ProviderType.ANTHROPIC
            elif "openai" in api_lower:
                return ProviderType.OPENAI
            elif "ollama" in api_lower or "localhost" in api_lower or api_lower.startswith("http://") or api_lower.startswith("https://"):
                # Check if it's a local/ollama instance
                if ":11434" in api_lower or "ollama" in api_lower:
                    return ProviderType.LOCAL
                # For custom OpenAI-compatible endpoints, default to OPENAI type
                # but we'll use the custom base_url
        
        model_lower = model.lower()
        if any(x in model_lower for x in ["mistral", "mixtral"]):
            return ProviderType.MISTRAL
        elif any(x in model_lower for x in ["claude", "anthropic"]):
            return ProviderType.ANTHROPIC
        elif "ollama" in model_lower:
            return ProviderType.LOCAL
        else:
            return ProviderType.OPENAI
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.config.timeout)
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        # Add authorization header
        if self.config.api_key:
            if self.config.provider == ProviderType.ANTHROPIC:
                headers["x-api-key"] = self.config.api_key
                headers["anthropic-version"] = "2023-06-01"
            else:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
        
        return headers
    
    def _format_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format messages for the specific provider."""
        # OpenAI and Mistral use the same format
        if self.config.provider == ProviderType.ANTHROPIC:
            # Anthropic uses a different format
            formatted = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                # Map roles
                if role == "system":
                    formatted.append({"role": "system", "content": content})
                elif role == "user":
                    formatted.append({"role": "user", "content": content})
                elif role == "assistant":
                    formatted.append({"role": "assistant", "content": content})
            return formatted
        else:
            # OpenAI/Mistral format
            return messages

    def _get_api_endpoint(self) -> str:
        """Get the appropriate API endpoint based on provider type."""
        # For Ollama, ensure the endpoint is correct
        if self.config.provider == ProviderType.LOCAL:
            base = self.config.api_base_url.rstrip("/")
            # Ollama OpenAI-compatible API uses /v1/chat/completions
            if not base.endswith("/v1"):
                return f"{base}/v1/chat/completions"
            return f"{base}/chat/completions"
        # For standard OpenAI-compatible providers
        return f"{self.config.api_base_url.rstrip('/')}/chat/completions"
    
    async def complete(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        messages: Optional[List[LLMMessage]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate a completion using OpenAI-compatible API."""
        client = await self._get_client()
        
        # Build messages
        chat_messages = []
        if system_message:
            chat_messages.append({"role": "system", "content": system_message})
        
        if messages:
            chat_messages.extend([m.to_dict() for m in messages])
        else:
            chat_messages.append({"role": "user", "content": prompt})
        
        # Format for provider
        chat_messages = self._format_messages(chat_messages)
        
        endpoint = self._get_api_endpoint()
        
        try:
            response = await client.post(
                endpoint,
                headers=self._get_headers(),
                json={
                    "model": self.config.model,
                    "messages": chat_messages,
                    "temperature": temperature or self.config.temperature,
                    "max_tokens": max_tokens or self.config.max_tokens,
                    **kwargs
                }
            )
            response.raise_for_status()
            data = response.json()
            
            choice = data["choices"][0]
            return LLMResponse(
                content=choice["message"]["content"],
                model=data.get("model", self.config.model),
                provider=self.config.provider.value,
                finish_reason=choice.get("finish_reason"),
                usage=data.get("usage"),
                raw_response=data
            )
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"OpenAI API error: {e.response.status_code} - {e.response.text}")
    
    async def chat(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate a chat completion using OpenAI-compatible API."""
        client = await self._get_client()
        
        # Convert messages to dict format
        chat_messages = [m.to_dict() for m in messages]
        
        # Format for provider
        chat_messages = self._format_messages(chat_messages)
        
        endpoint = self._get_api_endpoint()
        
        try:
            response = await client.post(
                endpoint,
                headers=self._get_headers(),
                json={
                    "model": self.config.model,
                    "messages": chat_messages,
                    "temperature": temperature or self.config.temperature,
                    "max_tokens": max_tokens or self.config.max_tokens,
                    **kwargs
                }
            )
            response.raise_for_status()
            data = response.json()
            
            choice = data["choices"][0]
            return LLMResponse(
                content=choice["message"]["content"],
                model=data.get("model", self.config.model),
                provider=self.config.provider.value,
                finish_reason=choice.get("finish_reason"),
                usage=data.get("usage"),
                raw_response=data
            )
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"OpenAI API error: {e.response.status_code} - {e.response.text}")


class OpenAIProvider(OpenAICompatibleProvider):
    """
    OpenAI API provider.
    
    Supports: GPT-4, GPT-3.5, GPT-3, etc.
    
    Example:
        provider = OpenAIProvider(
            model="gpt-4",
            api_key="sk-..."
        )
        response = await provider.complete("Hello!")
    """
    
    def __init__(
        self,
        model: str = "gpt-3.5-turbo",
        api_key: Optional[str] = None,
        api_base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: float = 60.0,
        **kwargs
    ):
        # Call parent init which will create the config
        super().__init__(model, api_key, api_base_url, temperature, max_tokens, timeout, **kwargs)
        # Override the provider type to OPENAI
        self.config.provider = ProviderType.OPENAI


class MistralProvider(OpenAICompatibleProvider):
    """
    Mistral AI API provider.
    
    Supports: mistral-large, mistral-small, mixtral-8x7b, etc.
    
    Example:
        provider = MistralProvider(
            model="mistral-large",
            api_key="your_mistral_key"
        )
        response = await provider.complete("Hello!")
    """
    
    def __init__(
        self,
        model: str = "mistral-small",
        api_key: Optional[str] = None,
        api_base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: float = 60.0,
        **kwargs
    ):
        # Call parent init which will create the config
        super().__init__(model, api_key, api_base_url, temperature, max_tokens, timeout, **kwargs)
        # Override the provider type to MISTRAL
        self.config.provider = ProviderType.MISTRAL


class AnthropicProvider(OpenAICompatibleProvider):
    """
    Anthropic API provider.
    
    Supports: Claude 3, Claude 2, Claude Instant, etc.
    
    Example:
        provider = AnthropicProvider(
            model="claude-3-sonnet-20240229",
            api_key="your_anthropic_key"
        )
        response = await provider.complete("Hello!")
    """
    
    def __init__(
        self,
        model: str = "claude-3-sonnet-20240229",
        api_key: Optional[str] = None,
        api_base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: float = 60.0,
        **kwargs
    ):
        # Call parent init which will create the config
        super().__init__(model, api_key, api_base_url, temperature, max_tokens, timeout, **kwargs)
        # Override the provider type to ANTHROPIC
        self.config.provider = ProviderType.ANTHROPIC
