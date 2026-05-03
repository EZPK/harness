"""
Base classes for LLM Providers.

Defines the interface that all LLM providers must implement.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class ProviderType(str, Enum):
    """Supported LLM provider types."""
    OPENAI = "openai"
    MISTRAL = "mistral"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    LOCAL = "local"
    LITELLML = "litellm"
    CUSTOM = "custom"


class MessageRole(str, Enum):
    """Message roles in a conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"


@dataclass
class LLMMessage:
    """A single message in an LLM conversation."""
    role: MessageRole
    content: str
    name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls."""
        result = {"role": self.role.value, "content": self.content}
        if self.name:
            result["name"] = self.name
        return result


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str
    model: str
    provider: str
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    raw_response: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def __str__(self) -> str:
        return self.content


class LLMConfig(BaseModel):
    """Configuration for an LLM provider."""
    provider: ProviderType = Field(..., description="LLM provider type")
    model: str = Field(..., description="Model identifier")
    api_key: Optional[str] = Field(default=None, description="API key (if required)")
    api_base_url: Optional[str] = Field(default=None, description="Custom API base URL")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: Optional[int] = Field(default=None, ge=1, le=32000, description="Maximum tokens to generate")
    timeout: float = Field(default=60.0, ge=1.0, le=300.0, description="Request timeout in seconds")
    
    class Config:
        env_file = ".env"
        extra = "allow"


class LLMProvider:
    """
    Abstract base class for LLM providers.
    
    All LLM providers must implement this interface to be compatible
    with the Harness Agentic Framework.
    
    Example:
        class MyProvider(LLMProvider):
            async def complete(self, prompt: str, **kwargs) -> LLMResponse:
                # Call your LLM API
                return LLMResponse(content="Hello!", model="my-model", provider="my_provider")
    """
    
    def __init__(self, config: Optional[LLMConfig] = None):
        """
        Initialize the LLM provider.
        
        Args:
            config: Provider configuration
        """
        self.config = config or LLMConfig(
            provider=ProviderType.CUSTOM,
            model="unknown"
        )
        self._is_available: bool = True
    
    @property
    def provider_type(self) -> ProviderType:
        """Get the provider type."""
        return self.config.provider
    
    @property
    def model(self) -> str:
        """Get the model identifier."""
        return self.config.model
    
    @property
    def is_available(self) -> bool:
        """Check if the provider is available."""
        return self._is_available
    
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
        Generate a completion from the LLM.
        
        Args:
            prompt: The user prompt
            system_message: Optional system message
            messages: Optional conversation history
            temperature: Sampling temperature (overrides config)
            max_tokens: Maximum tokens to generate (overrides config)
            **kwargs: Additional provider-specific arguments
            
        Returns:
            LLMResponse with the generated content
            
        Raises:
            ValueError: If prompt is empty
            RuntimeError: If provider is not available
        """
        if not prompt:
            raise ValueError("Prompt cannot be empty")
        
        if not self._is_available:
            raise RuntimeError(f"Provider {self.config.provider.value} is not available")
        
        raise NotImplementedError("Subclasses must implement complete()")
    
    async def chat(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a chat completion from the LLM.
        
        Args:
            messages: Conversation history
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific arguments
            
        Returns:
            LLMResponse with the generated content
        """
        raise NotImplementedError("Subclasses must implement chat()")
    
    async def check_availability(self) -> bool:
        """Check if the provider API is reachable."""
        self._is_available = True
        return True
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model}, provider={self.provider_type.value})"
