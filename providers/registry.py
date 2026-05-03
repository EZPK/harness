"""
Provider Registry.

Central registry for managing and accessing LLM providers.
Allows dynamic registration and retrieval of providers by name.
"""

from typing import Dict, Optional, Type, Union

from .base import LLMConfig, LLMProvider, ProviderType
from .lite_llm import LiteLLMProvider
from .openai_compatible import OpenAICompatibleProvider, OpenAIProvider, MistralProvider, AnthropicProvider


class ProviderRegistry:
    """
    Registry for LLM providers.
    
    Allows registration of custom providers and retrieval by name or type.
    
    Example:
        registry = ProviderRegistry()
        
        # Register a provider
        registry.register("mistral-large", MistralProvider(
            model="mistral-large",
            api_key="your_key"
        ))
        
        # Get a provider
        provider = registry.get("mistral-large")
        
        # Or get by type
        mistral_providers = registry.get_by_type(ProviderType.MISTRAL)
    """
    
    # Default provider classes
    PROVIDER_CLASSES: Dict[ProviderType, Type[LLMProvider]] = {
        ProviderType.OPENAI: OpenAIProvider,
        ProviderType.MISTRAL: MistralProvider,
        ProviderType.ANTHROPIC: AnthropicProvider,
        ProviderType.LITELLML: LiteLLMProvider,
        ProviderType.LOCAL: OpenAICompatibleProvider,
        ProviderType.CUSTOM: OpenAICompatibleProvider,
        ProviderType.GOOGLE: LiteLLMProvider,  # Google via LiteLLM or custom implementation
    }
    
    def __init__(self):
        """Initialize the provider registry."""
        self._providers: Dict[str, LLMProvider] = {}
        self._default_provider: Optional[str] = None
    
    def register(
        self,
        name: str,
        provider: LLMProvider,
        as_default: bool = False
    ) -> None:
        """
        Register a provider with a name.
        
        Args:
            name: Unique identifier for the provider
            provider: Provider instance
            as_default: Set this provider as the default
        """
        self._providers[name] = provider
        if as_default:
            self._default_provider = name
    
    def unregister(self, name: str) -> bool:
        """
        Unregister a provider.
        
        Args:
            name: Provider name to remove
            
        Returns:
            True if provider was removed, False otherwise
        """
        if name in self._providers:
            del self._providers[name]
            if self._default_provider == name:
                self._default_provider = None
            return True
        return False
    
    def get(self, name: str) -> Optional[LLMProvider]:
        """
        Get a provider by name.
        
        Args:
            name: Provider name
            
        Returns:
            Provider instance or None if not found
        """
        return self._providers.get(name)
    
    def get_default(self) -> Optional[LLMProvider]:
        """Get the default provider."""
        if self._default_provider:
            return self._providers.get(self._default_provider)
        # Return first registered provider if no default set
        if self._providers:
            return next(iter(self._providers.values()))
        return None
    
    def get_by_type(self, provider_type: ProviderType) -> Dict[str, LLMProvider]:
        """
        Get all providers of a specific type.
        
        Args:
            provider_type: Provider type to filter by
            
        Returns:
            Dictionary of provider names to instances
        """
        return {
            name: provider
            for name, provider in self._providers.items()
            if provider.provider_type == provider_type
        }
    
    def list_providers(self) -> Dict[str, LLMProvider]:
        """List all registered providers."""
        return self._providers.copy()
    
    def create_from_config(
        self,
        config: LLMConfig,
        name: Optional[str] = None
    ) -> LLMProvider:
        """
        Create a provider from configuration.
        
        Args:
            config: Provider configuration
            name: Optional name for the provider
            
        Returns:
            Configured provider instance
        """
        provider_class = self.PROVIDER_CLASSES.get(config.provider)
        if provider_class is None:
            # Fall back to LiteLLM for unknown providers
            provider_class = LiteLLMProvider
        
        # Create provider from config
        provider_kwargs = {
            "model": config.model,
            "api_key": config.api_key,
            "api_base_url": config.api_base_url,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "timeout": config.timeout,
        }
        # Add any extra config (excluding 'provider' which is handled by the provider class itself)
        if hasattr(config, "__dict__"):
            for key, value in config.__dict__.items():
                if key not in provider_kwargs and key != "provider" and value is not None:
                    provider_kwargs[key] = value
        
        provider = provider_class(**provider_kwargs)
        
        # Register if name provided
        if name:
            self.register(name, provider)
        
        return provider
    
    def set_default(self, name: str) -> bool:
        """
        Set the default provider.
        
        Args:
            name: Provider name to set as default
            
        Returns:
            True if provider exists and was set as default
        """
        if name in self._providers:
            self._default_provider = name
            return True
        return False
    
    def clear(self) -> None:
        """Clear all registered providers."""
        self._providers.clear()
        self._default_provider = None
    
    def __len__(self) -> int:
        return len(self._providers)
    
    def __contains__(self, name: str) -> bool:
        return name in self._providers


# Global provider registry instance
_provider_registry = ProviderRegistry()


def get_registry() -> ProviderRegistry:
    """Get the global provider registry."""
    return _provider_registry


def get_provider(name: str) -> Optional[LLMProvider]:
    """
    Get a provider from the global registry by name.
    
    Args:
        name: Provider name
        
    Returns:
        Provider instance or None
    """
    return _provider_registry.get(name)


def register_provider(
    name: str,
    provider: LLMProvider,
    as_default: bool = False
) -> None:
    """
    Register a provider in the global registry.
    
    Args:
        name: Provider name
        provider: Provider instance
        as_default: Set as default provider
    """
    _provider_registry.register(name, provider, as_default)


def create_provider(
    config: LLMConfig,
    name: Optional[str] = None
) -> LLMProvider:
    """
    Create and optionally register a provider from configuration.
    
    Args:
        config: Provider configuration
        name: Optional name for registration
        
    Returns:
        Created provider instance
    """
    return _provider_registry.create_from_config(config, name)
