"""
LLM Agent - Specialist agent for LLM interactions.

This agent uses a configured LLM provider to generate responses,
reason about problems, and assist with various tasks.
"""

from typing import Any, Dict, List, Optional

from agents.base import BaseAgent, TaskContext, TaskResult
from configs.schemas import AgentConfig, AgentCapability
from providers import LLMProvider, LLMMessage, MessageRole


class LLMAgent(BaseAgent):
    """
    Specialist agent for LLM-based reasoning and text generation.
    
    This agent wraps an LLM provider and exposes its capabilities
    through the standard agent interface.
    
    Example:
        from providers import MistralProvider, register_provider
        from agents.specialists.llm_agent import LLMAgent
        
        # Create and register provider
        provider = MistralProvider(
            model="mistral-large",
            api_key="your_api_key"
        )
        register_provider("mistral-large", provider)
        
        # Create agent with provider
        llm_agent = LLMAgent(
            name="LLMAgent",
            provider=provider,
            capabilities=["llm", "reasoning", "text_generation", "analysis"]
        )
        
        # Use it
        result = await llm_agent.execute_task(
            {"prompt": "Explain quantum computing in simple terms"}
        )
    """
    
    def __init__(
        self,
        name: str = "LLMAgent",
        provider: Optional[LLMProvider] = None,
        provider_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        config: Optional[AgentConfig] = None,
        **kwargs
    ):
        """
        Initialize the LLM Agent.
        
        Args:
            name: Agent name
            provider: LLM provider instance
            provider_name: Name of registered provider to use
            system_prompt: System prompt for the LLM
            config: Agent configuration
            **kwargs: Additional agent configuration
        """
        # Default capabilities
        default_capabilities = [
            AgentCapability(
                name="llm",
                description="LLM-based text generation and reasoning",
                level="expert"
            ),
            AgentCapability(
                name="reasoning",
                description="Logical reasoning and problem solving",
                level="expert"
            ),
            AgentCapability(
                name="text_generation",
                description="Generating human-like text",
                level="expert"
            ),
            AgentCapability(
                name="analysis",
                description="Analyzing text and data",
                level="high"
            ),
            AgentCapability(
                name="summarization",
                description="Summarizing text content",
                level="high"
            ),
        ]
        
        # Create config if not provided
        if config is None:
            config = AgentConfig(
                name=name,
                description="LLM Agent for reasoning and text generation",
                capabilities=default_capabilities,
                **kwargs
            )
        
        super().__init__(name, config)
        
        # Get provider
        if provider:
            self._provider = provider
        elif provider_name:
            from providers import get_provider
            self._provider = get_provider(provider_name)
            if self._provider is None:
                raise ValueError(f"Provider '{provider_name}' not found in registry")
        else:
            # Try to get default provider
            from providers import get_registry
            registry = get_registry()
            self._provider = registry.get_default()
            if self._provider is None:
                raise ValueError(
                    "No LLM provider configured. "
                    "Please register a provider or pass one explicitly."
                )
        
        # System prompt
        self._system_prompt = system_prompt or """
        You are a helpful AI assistant. You provide accurate, helpful, and concise responses.
        You can reason about problems, generate code, explain concepts, and assist with various tasks.
        Always respond in French if the user writes in French, otherwise respond in English.
        """
        
        # Conversation history
        self._conversation_history: List[LLMMessage] = []
    
    @property
    def provider(self) -> LLMProvider:
        """Get the LLM provider."""
        return self._provider
    
    @property
    def system_prompt(self) -> str:
        """Get the system prompt."""
        return self._system_prompt
    
    @system_prompt.setter
    def system_prompt(self, value: str) -> None:
        """Set the system prompt."""
        self._system_prompt = value
    
    def set_provider(self, provider: LLMProvider) -> None:
        """Set the LLM provider."""
        self._provider = provider
    
    def clear_conversation(self) -> None:
        """Clear the conversation history."""
        self._conversation_history = []
    
    def add_to_conversation(self, role: MessageRole, content: str) -> None:
        """Add a message to the conversation history."""
        self._conversation_history.append(LLMMessage(role=role, content=content))
    
    async def _do_initialize(self) -> None:
        """Initialize the LLM agent."""
        # Check if provider is available
        if self._provider:
            is_available = await self._provider.check_availability()
            if not is_available:
                raise RuntimeError(f"LLM provider {self._provider.model} is not available")
    
    async def _do_shutdown(self) -> None:
        """Shutdown the LLM agent."""
        # Close provider connections if needed
        if hasattr(self._provider, 'close'):
            await self._provider.close()
    
    async def _execute_task(
        self,
        task: Dict[str, Any],
        context: Optional[TaskContext] = None
    ) -> Any:
        """
        Execute a task using the LLM.
        
        Args:
            task: Task dictionary with 'prompt' or 'input' key
            context: Optional task context
            
        Returns:
            Result from the LLM
        """
        from agents.base import TaskResult
        
        # Extract prompt
        prompt = task.get("prompt") or task.get("input") or task.get("query", "")
        
        if not prompt:
            raise ValueError("No prompt provided in task")
        
        # Build messages
        messages = [LLMMessage(role=MessageRole.SYSTEM, content=self._system_prompt)]
        messages.extend(self._conversation_history)
        messages.append(LLMMessage(role=MessageRole.USER, content=prompt))
        
        # Call LLM
        response = await self._provider.chat(
            messages=messages,
            temperature=task.get("temperature", self._provider.config.temperature),
            max_tokens=task.get("max_tokens", self._provider.config.max_tokens),
        )
        
        # Add to conversation history
        self.add_to_conversation(MessageRole.USER, prompt)
        self.add_to_conversation(MessageRole.ASSISTANT, response.content)
        
        # Return response
        return response.content
    
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate a completion from the LLM (convenience method).
        
        Args:
            prompt: User prompt
            system_prompt: Override system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text
        """
        messages = []
        
        current_system = system_prompt or self._system_prompt
        if current_system:
            messages.append(LLMMessage(role=MessageRole.SYSTEM, content=current_system))
        
        messages.extend(self._conversation_history)
        messages.append(LLMMessage(role=MessageRole.USER, content=prompt))
        
        response = await self._provider.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Add to conversation
        self.add_to_conversation(MessageRole.USER, prompt)
        self.add_to_conversation(MessageRole.ASSISTANT, response.content)
        
        return response.content
    
    def __repr__(self) -> str:
        return f"LLMAgent(name={self.name}, provider={self._provider})"
