"""
Agents Module.

Contains all agent implementations for the Harness Agentic Framework.
This includes:
- God Agent (orchestrator)
- Specialist Agents (planner, coder, reviewer, tester, debugger, researcher, documenter)
- Base classes and utilities
"""

from .base import (
    BaseAgent,
    BaseWorkflow,
    HybridAgent,
    AgentID,
    TaskID,
    AgentState,
    CapabilityLevel,
    TaskPriority,
    TaskStatus,
    AgentStatus,
    AgentCapabilityInfo,
    AgentRuntimeConfig,
    TaskContext,
    TaskResult,
    AgentError,
    TaskError,
    InitializationError,
    ConfigurationError,
    AgentClass,
    AgentFactory,
)

from .god import (
    GodAgent,
    RoutingStrategy,
    DecompositionStrategy,
    TaskType,
    WorkflowStep,
    WorkflowDefinition,
    TaskAssignment,
    AgentRegistry,
    TaskRouter,
    TaskDecomposer,
    ResultAggregator,
)

# Specialist agents will be imported lazily to avoid circular dependencies
# from .specialists import PlannerAgent, CoderAgent, ReviewerAgent, ...

__all__ = [
    # Base classes
    "BaseAgent",
    "BaseWorkflow",
    "HybridAgent",
    # God Agent
    "GodAgent",
    # Type definitions
    "AgentID",
    "TaskID",
    # Enums
    "AgentState",
    "CapabilityLevel",
    "TaskPriority",
    "TaskStatus",
    "RoutingStrategy",
    "DecompositionStrategy",
    "TaskType",
    # Data classes
    "AgentStatus",
    "AgentCapabilityInfo",
    "AgentRuntimeConfig",
    "TaskContext",
    "TaskResult",
    "WorkflowStep",
    "WorkflowDefinition",
    "TaskAssignment",
    # Internal components
    "AgentRegistry",
    "TaskRouter",
    "TaskDecomposer",
    "ResultAggregator",
    # Exceptions
    "AgentError",
    "TaskError",
    "InitializationError",
    "ConfigurationError",
    # Type aliases
    "AgentClass",
    "AgentFactory",
]
