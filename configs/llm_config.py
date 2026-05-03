"""
LLM Configuration.

Central configuration for LLM providers in the Harness Agentic Framework.
Loads configuration from environment variables or config files.
"""

import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict
from pydantic_settings import BaseSettings

from providers.base import ProviderType


class LLMProviderConfig(BaseModel):
    """Configuration for a single LLM provider."""
    name: str = Field(..., description="Unique name for this provider")
    provider: ProviderType = Field(..., description="Provider type")
    model: str = Field(..., description="Model identifier")
    api_key: Optional[str] = Field(default=None, description="API key")
    api_base_url: Optional[str] = Field(default=None, description="Custom API base URL")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=32000)
    timeout: float = Field(default=60.0, ge=1.0, le=300.0)
    is_default: bool = Field(default=False, description="Set as default provider")
    enabled: bool = Field(default=True, description="Whether this provider is enabled")


class LLMConfig(BaseSettings):
    """
    Global LLM configuration.
    
    Loads from:
    1. Environment variables (e.g., MISTRAL_API_KEY, OPENAI_API_KEY)
    2. .env file
    3. Default values
    
    Example .env file:
        MISTRAL_API_KEY=your_mistral_key
        OPENAI_API_KEY=your_openai_key
        DEFAULT_LLM_PROVIDER=mistral
    """
    
    # API Keys (can be loaded from env or set directly)
    mistral_api_key: Optional[str] = Field(default=None, alias="MISTRAL_API_KEY")
    openai_api_key: Optional[str] = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, alias="ANTHROPIC_API_KEY")
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    
    # Default provider
    default_provider: str = Field(default="mistral-large", alias="DEFAULT_LLM_PROVIDER")
    
    # Default model settings
    default_temperature: float = Field(default=0.7, alias="DEFAULT_LLM_TEMPERATURE")
    default_max_tokens: Optional[int] = Field(default=None, alias="DEFAULT_LLM_MAX_TOKENS")
    default_timeout: float = Field(default=60.0, alias="DEFAULT_LLM_TIMEOUT")
    
    # Ollama-specific settings
    ollama_base_url: Optional[str] = Field(default=None, alias="OLLAMA_BASE_URL")
    ollama_model: Optional[str] = Field(default=None, alias="OLLAMA_MODEL")
    
    # Custom provider configurations
    providers: List[LLMProviderConfig] = Field(
        default_factory=list,
        description="List of custom provider configurations"
    )
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    def get_provider_config(self, name: str) -> Optional[LLMProviderConfig]:
        """Get configuration for a specific provider by name."""
        for provider in self.providers:
            if provider.name == name:
                return provider
        return None
    
    def get_api_key(self, provider: ProviderType) -> Optional[str]:
        """Get API key for a provider type."""
        key_mapping = {
            ProviderType.OPENAI: self.openai_api_key,
            ProviderType.MISTRAL: self.mistral_api_key,
            ProviderType.ANTHROPIC: self.anthropic_api_key,
            ProviderType.GOOGLE: self.google_api_key,
        }
        return key_mapping.get(provider)
    
    def to_provider_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for provider creation."""
        return {
            "default_provider": self.default_provider,
            "default_temperature": self.default_temperature,
            "default_max_tokens": self.default_max_tokens,
            "default_timeout": self.default_timeout,
        }


# Global configuration instance
_llm_config: Optional[LLMConfig] = None


def get_llm_config() -> LLMConfig:
    """Get the global LLM configuration (cached)."""
    global _llm_config
    if _llm_config is None:
        _llm_config = LLMConfig()
    return _llm_config


def reload_llm_config() -> LLMConfig:
    """Reload the LLM configuration from environment."""
    global _llm_config
    _llm_config = LLMConfig()
    return _llm_config


def configure_llm(
    provider: str = "mistral-large",
    api_key: Optional[str] = None,
    **kwargs
) -> None:
    """
    Configure LLM settings programmatically.
    
    Args:
        provider: Default provider name or model
        api_key: API key (optional, can use env var)
        **kwargs: Additional configuration
    """
    config = get_llm_config()
    
    # Update config
    if api_key:
        if "mistral" in provider.lower():
            config.mistral_api_key = api_key
        elif "openai" in provider.lower() or "gpt" in provider.lower():
            config.openai_api_key = api_key
        elif "anthropic" in provider.lower() or "claude" in provider.lower():
            config.anthropic_api_key = api_key
    
    config.default_provider = provider
    
    # Update any other settings
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
