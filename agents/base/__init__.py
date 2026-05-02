"""
Base Agent Module.

Exports the foundational classes for all agents in the Harness Agentic Framework.
"""

from .agent import (
    # Base classes
    BaseAgent,
    BaseWorkflow,
    HybridAgent,
    
    # Type definitions
    AgentID,
    TaskID,
    
    # Enums
    AgentState,
    CapabilityLevel,
    TaskPriority,
    TaskStatus,
    
    # Data classes
    AgentStatus,
    AgentCapabilityInfo,
    AgentRuntimeConfig,
    TaskContext,
    TaskResult,
    
    # Exceptions
    AgentError,
    TaskError,
    InitializationError,
    ConfigurationError,
    
    # Type aliases
    AgentClass,
    AgentFactory,
)

__all__ = [
    # Base classes
    "BaseAgent",
    "BaseWorkflow",
    "HybridAgent",
    # Type definitions
    "AgentID",
    "TaskID",
    # Enums
    "AgentState",
    "CapabilityLevel",
    "TaskPriority",
    "TaskStatus",
    # Data classes
    "AgentStatus",
    "AgentCapabilityInfo",
    "AgentRuntimeConfig",
    "TaskContext",
    "TaskResult",
    # Exceptions
    "AgentError",
    "TaskError",
    "InitializationError",
    "ConfigurationError",
    # Type aliases
    "AgentClass",
    "AgentFactory",
]
