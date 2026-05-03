"""
LLM Providers Module.

Provides LLM provider integrations for the Harness Agentic Framework.
Supports multiple providers: OpenAI, Mistral, Anthropic, Google, Local, etc.

Usage:
    from providers import get_provider, LLMProvider, LiteLLMProvider
    
    # Get a provider instance
    provider = get_provider("mistral", api_key="your_key")
    
    # Or use LiteLLM for multi-provider support
    provider = LiteLLMProvider(model="mistral/mistral-large")
    
    # Call the LLM
    response = await provider.complete("Hello, how are you?")
"""

from .base import (
    LLMProvider,
    LLMConfig,
    LLMResponse,
    LLMMessage,
    MessageRole,
    ProviderType,
)
from .lite_llm import LiteLLMProvider
from .openai_compatible import OpenAIProvider, MistralProvider, AnthropicProvider
from .registry import (
    ProviderRegistry,
    get_provider,
    register_provider,
    get_registry,
    create_provider,
)

__all__ = [
    # Base classes
    "LLMProvider",
    "LLMConfig",
    "LLMResponse",
    "LLMMessage",
    "MessageRole",
    "ProviderType",
    # Providers
    "LiteLLMProvider",
    "OpenAIProvider",
    "MistralProvider",
    "AnthropicProvider",
    # Registry
    "ProviderRegistry",
    "get_provider",
    "register_provider",
    "get_registry",
    "create_provider",
]
