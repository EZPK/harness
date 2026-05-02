"""
God Agent Module.

The God Agent is the central orchestrator in the Harness Agentic Framework.
It delegates tasks to specialist agents based on pertinence and capability.
This is the heart of the Orchestrator-Workers pattern.
"""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Callable, Awaitable

from pydantic import BaseModel, Field

from agents.base import (
    HybridAgent,
    BaseAgent,
    AgentState,
    AgentRuntimeConfig,
    TaskContext,
    TaskResult,
    TaskStatus,
    AgentError,
    TaskError,
)
from core.aci.interface import ACIInterface, InMemoryACI, MessageMetadata
from core.aci.commands import Command, TaskAssignmentCommand, TaskResultCommand
from core.aci.responses import Response, TaskAssignmentResponse
from core.sandbox.executor import SandboxExecutor
from configs.schemas import GodAgentConfig, AgentConfig
from configs.settings import get_agent_config, get_config

from core.monitoring import (
    get_metrics_collector,
    get_tracer,
    start_span,
    increment_metric,
    AlertSeverity,
    raise_alert,
)


# =============================================================================
# Type Definitions
# =============================================================================

TaskID = str
WorkflowID = str


# =============================================================================
# Routing Strategies
# =============================================================================

class RoutingStrategy(str, Enum):
    """Strategies for routing tasks to specialist agents."""
    
    KEYWORD = "keyword"           # Match task keywords to agent capabilities
    CAPABILITY = "capability"     # Match based on declared capabilities
    HYBRID = "hybrid"             # Combine keyword and capability matching
    ROUND_ROBIN = "round_robin"   # Distribute evenly among capable agents
    PRIORITY = "priority"         # Route to highest-priority capable agent
    LEARNED = "learned"           # Use learned routing from past performance


class DecompositionStrategy(str, Enum):
    """Strategies for decomposing complex tasks."""
    
    TEMPLATE = "template"         # Use predefined templates for known task types
    SEMANTIC = "semantic"         # Use semantic analysis to decompose
    HYBRID = "hybrid"             # Combine template and semantic approaches
    RECURSIVE = "recursive"       # Recursively decompose until atomic tasks


# =============================================================================
# Task Types
# =============================================================================

class TaskType(str, Enum):
    """Types of tasks that the God Agent can handle."""
    
    # Development tasks
    IMPLEMENT_FEATURE = "implement_feature"
    FIX_BUG = "fix_bug"
    REFACTOR_CODE = "refactor_code"
    OPTIMIZE = "optimize"
    
    # Review tasks
    CODE_REVIEW = "code_review"
    ARCHITECTURE_REVIEW = "architecture_review"
    SECURITY_AUDIT = "security_audit"
    
    # Testing tasks
    WRITE_TESTS = "write_tests"
    RUN_TESTS = "run_tests"
    DEBUG_TEST = "debug_test"
    
    # Documentation tasks
    WRITE_DOCS = "write_docs"
    UPDATE_DOCS = "update_docs"
    GENERATE_API_DOCS = "generate_api_docs"
    
    # Research tasks
    RESEARCH = "research"
    ANALYZE = "analyze"
    INVESTIGATE = "investigate"
    
    # Composite tasks
    WORKFLOW = "workflow"
    MULTI_AGENT = "multi_agent"
    COORDINATE = "coordinate"


# =============================================================================
# Task Priority
# =============================================================================

@dataclass
class TaskPriority:
    """Priority level with numeric value for sorting."""
    
    level: str  # "critical", "high", "medium", "low"
    value: int  # Numeric value (higher = more important)
    
    @classmethod
    def from_str(cls, level: str) -> 'TaskPriority':
        """Create from string level."""
        level = level.lower()
        value_map = {
            "critical": 4,
            "high": 3,
            "medium": 2,
            "low": 1,
        }
        return cls(level=level, value=value_map.get(level, 1))
    
    def __lt__(self, other: 'TaskPriority') -> bool:
        return self.value < other.value
    
    def __gt__(self, other: 'TaskPriority') -> bool:
        return self.value > other.value


# =============================================================================
# Workflow Step
# =============================================================================

@dataclass
class WorkflowStep:
    """A single step in a workflow."""
    
    step_id: str
    name: str
    description: str = ""
    agent_name: str = ""  # Name of the agent to execute this step
    task_type: str = ""  # Type of task
    input_data: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)  # IDs of steps this depends on
    timeout: Optional[float] = None
    priority: str = "medium"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Runtime fields
    status: str = "pending"  # pending, running, completed, failed, skipped
    result: Any = None
    error: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    @property
    def is_complete(self) -> bool:
        """Check if step is complete."""
        return self.status in ["completed", "failed", "skipped"]
    
    @property
    def is_successful(self) -> bool:
        """Check if step completed successfully."""
        return self.status == "completed"


# =============================================================================
# Workflow Definition
# =============================================================================

@dataclass
class WorkflowDefinition:
    """Definition of a workflow."""
    
    workflow_id: WorkflowID
    name: str
    description: str = ""
    steps: List[WorkflowStep] = field(default_factory=list)
    parallel_steps: bool = False  # Allow parallel execution of independent steps
    timeout: Optional[float] = None  # Total workflow timeout
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Runtime fields
    status: str = "pending"  # pending, running, completed, failed, cancelled
    current_step: Optional[str] = None  # ID of current step
    completed_steps: List[str] = field(default_factory=list)
    failed_steps: List[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    results: Dict[str, Any] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)
    
    @property
    def is_complete(self) -> bool:
        """Check if workflow is complete."""
        return self.status in ["completed", "failed", "cancelled"]
    
    @property
    def is_successful(self) -> bool:
        """Check if workflow completed successfully."""
        return self.status == "completed"
    
    @property
    def progress(self) -> float:
        """Calculate workflow progress (0.0 to 1.0)."""
        total_steps = len(self.steps)
        if total_steps == 0:
            return 1.0
        completed = len(self.completed_steps) + len(self.failed_steps)
        return completed / total_steps


# =============================================================================
# Task Assignment
# =============================================================================

@dataclass
class TaskAssignment:
    """Assignment of a task to an agent."""
    
    assignment_id: str
    task_id: TaskID
    agent_name: str
    task: Dict[str, Any]
    context: TaskContext
    priority: TaskPriority = field(default_factory=lambda: TaskPriority.from_str("medium"))
    timeout: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    assigned_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Result
    status: str = "pending"  # pending, assigned, running, completed, failed
    result: Any = None
    error: Optional[str] = None
    retry_count: int = 0
    
    @property
    def is_complete(self) -> bool:
        """Check if assignment is complete."""
        return self.status in ["completed", "failed"]


# =============================================================================
# Agent Registry (for God Agent to track specialists)
# =============================================================================

class AgentRegistry:
    """
    Registry of specialist agents managed by the God Agent.
    
    This tracks all available specialist agents and their capabilities.
    """
    
    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
        self._capabilities: Dict[str, Set[str]] = {}  # capability -> set of agent names
        self._agent_capabilities: Dict[str, Set[str]] = {}  # agent_name -> set of capabilities
        self._agent_states: Dict[str, AgentState] = {}
        self._lock = asyncio.Lock()
    
    async def register(self, agent: BaseAgent) -> None:
        """Register a specialist agent."""
        async with self._lock:
            self._agents[agent.name] = agent
            
            # Index by capabilities
            caps = set()
            for cap in agent.capabilities:
                cap_name = cap.name.lower()
                caps.add(cap_name)
                if cap_name not in self._capabilities:
                    self._capabilities[cap_name] = set()
                self._capabilities[cap_name].add(agent.name)
            
            self._agent_capabilities[agent.name] = caps
            self._agent_states[agent.name] = agent.state
            
            increment_metric("god.agents_registered", labels={"agent": agent.name})
    
    async def unregister(self, agent_name: str) -> bool:
        """Unregister a specialist agent."""
        async with self._lock:
            if agent_name not in self._agents:
                return False
            
            agent = self._agents.pop(agent_name)
            
            # Remove from capability index
            if agent_name in self._agent_capabilities:
                for cap in self._agent_capabilities[agent_name]:
                    self._capabilities.get(cap, set()).discard(agent_name)
                del self._agent_capabilities[agent_name]
            
            self._agent_states.pop(agent_name, None)
            
            increment_metric("god.agents_unregistered", labels={"agent": agent_name})
            return True
    
    def get(self, agent_name: str) -> Optional[BaseAgent]:
        """Get a registered agent."""
        return self._agents.get(agent_name)
    
    def get_agent_names(self) -> List[str]:
        """Get list of all registered agent names."""
        return list(self._agents.keys())
    
    def get_by_capability(self, capability: str) -> List[BaseAgent]:
        """Get agents with a specific capability."""
        capability = capability.lower()
        agent_names = self._capabilities.get(capability, set())
        return [self._agents[name] for name in agent_names if name in self._agents]
    
    def get_available_agents(self) -> List[BaseAgent]:
        """Get all available (idle) agents."""
        return [agent for agent in self._agents.values() if agent.is_available]
    
    def get_agent_capabilities(self, agent_name: str) -> Set[str]:
        """Get capabilities of a specific agent."""
        return self._agent_capabilities.get(agent_name, set())
    
    def has_capability(self, capability: str) -> bool:
        """Check if any agent has a capability."""
        capability = capability.lower()
        return capability in self._capabilities and len(self._capabilities[capability]) > 0
    
    def get_state(self, agent_name: str) -> Optional[AgentState]:
        """Get the state of a specific agent."""
        return self._agent_states.get(agent_name)


# =============================================================================
# Task Router
# =============================================================================

class TaskRouter:
    """
    Routes tasks to appropriate specialist agents.
    
    Uses various strategies to determine the best agent for a task.
    """
    
    def __init__(self, agent_registry: AgentRegistry):
        self._agent_registry = agent_registry
        self._strategy: RoutingStrategy = RoutingStrategy.HYBRID
    
    @property
    def strategy(self) -> RoutingStrategy:
        """Get the current routing strategy."""
        return self._strategy
    
    @strategy.setter
    def strategy(self, value: RoutingStrategy) -> None:
        """Set the routing strategy."""
        self._strategy = value
    
    def route(self, task: Dict[str, Any], context: Optional[TaskContext] = None) -> Optional[str]:
        """
        Route a task to the most appropriate agent.
        
        Args:
            task: The task to route
            context: Optional task context
            
        Returns:
            Name of the agent to handle the task, or None if no agent found
        """
        # Extract task type and keywords
        task_type = task.get("type", "").lower()
        task_action = task.get("action", "").lower()
        description = task.get("description", "").lower()
        
        # Try different strategies based on configuration
        if self._strategy == RoutingStrategy.KEYWORD:
            agent_name = self._route_by_keyword(task, task_type, task_action, description)
        elif self._strategy == RoutingStrategy.CAPABILITY:
            agent_name = self._route_by_capability(task)
        elif self._strategy == RoutingStrategy.HYBRID:
            # Try capability first, then keyword
            agent_name = self._route_by_capability(task)
            if agent_name is None:
                agent_name = self._route_by_keyword(task, task_type, task_action, description)
        elif self._strategy == RoutingStrategy.ROUND_ROBIN:
            agent_name = self._route_round_robin()
        elif self._strategy == RoutingStrategy.PRIORITY:
            agent_name = self._route_by_priority(task)
        else:
            agent_name = self._route_by_capability(task)
        
        return agent_name
    
    def _route_by_keyword(
        self,
        task: Dict[str, Any],
        task_type: str,
        task_action: str,
        description: str
    ) -> Optional[str]:
        """Route based on keyword matching."""
        # Define keyword mappings
        keyword_map = {
            # Planner keywords
            "plan": "PlannerAgent",
            "design": "PlannerAgent",
            "architecture": "PlannerAgent",
            "roadmap": "PlannerAgent",
            "specification": "PlannerAgent",
            
            # Coder keywords
            "code": "CoderAgent",
            "implement": "CoderAgent",
            "write": "CoderAgent",
            "create": "CoderAgent",
            "function": "CoderAgent",
            "class": "CoderAgent",
            "module": "CoderAgent",
            "script": "CoderAgent",
            "fix": "CoderAgent",
            "bug": "CoderAgent",
            
            # Reviewer keywords
            "review": "ReviewerAgent",
            "check": "ReviewerAgent",
            "validate": "ReviewerAgent",
            "verify": "ReviewerAgent",
            "audit": "ReviewerAgent",
            "quality": "ReviewerAgent",
            "style": "ReviewerAgent",
            "lint": "ReviewerAgent",
            
            # Tester keywords
            "test": "TesterAgent",
            "testing": "TesterAgent",
            "unit": "TesterAgent",
            "integration": "TesterAgent",
            "e2e": "TesterAgent",
            "mock": "TesterAgent",
            "coverage": "TesterAgent",
            
            # Debugger keywords
            "debug": "DebuggerAgent",
            "issue": "DebuggerAgent",
            "problem": "DebuggerAgent",
            "error": "DebuggerAgent",
            "exception": "DebuggerAgent",
            "traceback": "DebuggerAgent",
            "log": "DebuggerAgent",
            
            # Researcher keywords
            "research": "ResearcherAgent",
            "investigate": "ResearcherAgent",
            "analyze": "ResearcherAgent",
            "explore": "ResearcherAgent",
            "documentation": "ResearcherAgent",
            "doc": "ResearcherAgent",
            "search": "ResearcherAgent",
            "find": "ResearcherAgent",
            
            # Documenter keywords
            "document": "DocumenterAgent",
            "docstring": "DocumenterAgent",
            "readme": "DocumenterAgent",
            "api": "DocumenterAgent",
            "tutorial": "DocumenterAgent",
            "guide": "DocumenterAgent",
        }
        
        # Try to match task type
        for keyword, agent_name in keyword_map.items():
            if keyword in task_type:
                if self._agent_registry.get(agent_name) is not None:
                    return agent_name
        
        # Try to match task action
        for keyword, agent_name in keyword_map.items():
            if keyword in task_action:
                if self._agent_registry.get(agent_name) is not None:
                    return agent_name
        
        # Try to match description
        combined = f"{task_type} {task_action} {description}"
        for keyword, agent_name in keyword_map.items():
            if keyword in combined:
                if self._agent_registry.get(agent_name) is not None:
                    return agent_name
        
        return None
    
    def _route_by_capability(self, task: Dict[str, Any]) -> Optional[str]:
        """Route based on capability matching."""
        # Extract required capabilities from task
        required_caps = set()
        
        # Check for explicit capability requirements
        if "capabilities" in task:
            if isinstance(task["capabilities"], list):
                required_caps.update(cap.lower() for cap in task["capabilities"])
            elif isinstance(task["capabilities"], str):
                required_caps.add(task["capabilities"].lower())
        
        # Check for required tools
        if "tools" in task:
            if isinstance(task["tools"], list):
                for tool in task["tools"]:
                    required_caps.add(f"tool:{tool.lower()}")
        
        # Find agents with all required capabilities
        matching_agents = []
        for agent_name in self._agent_registry.get_agent_names():
            agent_caps = self._agent_registry.get_agent_capabilities(agent_name)
            if required_caps.issubset(agent_caps):
                matching_agents.append(agent_name)
        
        # If we have matches, return the first available one
        for agent_name in matching_agents:
            agent = self._agent_registry.get(agent_name)
            if agent is not None and agent.is_available:
                return agent_name
        
        # If no exact match, try partial match
        for agent_name in matching_agents:
            agent = self._agent_registry.get(agent_name)
            if agent is not None:
                return agent_name
        
        return None
    
    def _route_round_robin(self) -> Optional[str]:
        """Route using round-robin."""
        available = self._agent_registry.get_available_agents()
        if not available:
            # Fall back to any agent
            agents = self._agent_registry.get_agent_names()
            if not agents:
                return None
            return agents[0]
        
        # Simple round-robin: just pick the first available
        # In a real implementation, we'd track the last used agent
        return available[0].name
    
    def _route_by_priority(self, task: Dict[str, Any]) -> Optional[str]:
        """Route to highest-priority capable agent."""
        # For now, just use capability-based routing
        return self._route_by_capability(task)


# =============================================================================
# Task Decomposer
# =============================================================================

class TaskDecomposer:
    """
    Decomposes complex tasks into smaller subtasks.
    
    Uses various strategies to break down tasks into manageable pieces.
    """
    
    def __init__(self, agent_registry: AgentRegistry):
        self._agent_registry = agent_registry
        self._strategy: DecompositionStrategy = DecompositionStrategy.TEMPLATE
        self._templates: Dict[str, List[Dict[str, Any]]] = {}
    
    @property
    def strategy(self) -> DecompositionStrategy:
        """Get the current decomposition strategy."""
        return self._strategy
    
    @strategy.setter
    def strategy(self, value: DecompositionStrategy) -> None:
        """Set the decomposition strategy."""
        self._strategy = value
    
    async def decompose(self, task: Dict[str, Any], context: Optional[TaskContext] = None) -> List[Dict[str, Any]]:
        """
        Decompose a complex task into subtasks.
        
        Args:
            task: The task to decompose
            context: Optional task context
            
        Returns:
            List of subtasks
        """
        task_type = task.get("type", "").lower()
        
        if self._strategy == DecompositionStrategy.TEMPLATE:
            subtasks = await self._decompose_by_template(task, task_type)
        elif self._strategy == DecompositionStrategy.SEMANTIC:
            subtasks = await self._decompose_semantic(task)
        elif self._strategy == DecompositionStrategy.HYBRID:
            subtasks = await self._decompose_by_template(task, task_type)
            if not subtasks or len(subtasks) == 1:
                subtasks = await self._decompose_semantic(task)
        elif self._strategy == DecompositionStrategy.RECURSIVE:
            subtasks = await self._decompose_recursive(task)
        else:
            subtasks = [task]  # No decomposition
        
        return subtasks
    
    async def _decompose_by_template(self, task: Dict[str, Any], task_type: str) -> List[Dict[str, Any]]:
        """Decompose using predefined templates."""
        # Define templates for known task types
        templates = {
            "implement_feature": [
                {"type": "plan", "action": "create_plan", "description": "Create implementation plan"},
                {"type": "code", "action": "implement", "description": "Implement the feature"},
                {"type": "test", "action": "write_tests", "description": "Write unit tests"},
                {"type": "review", "action": "review_code", "description": "Review the implementation"},
            ],
            "fix_bug": [
                {"type": "debug", "action": "reproduce", "description": "Reproduce the bug"},
                {"type": "debug", "action": "analyze", "description": "Analyze the root cause"},
                {"type": "code", "action": "fix", "description": "Implement the fix"},
                {"type": "test", "action": "verify_fix", "description": "Verify the fix works"},
            ],
            "code_review": [
                {"type": "review", "action": "static_analysis", "description": "Run static analysis"},
                {"type": "review", "action": "style_check", "description": "Check code style"},
                {"type": "review", "action": "security_check", "description": "Check for security issues"},
                {"type": "test", "action": "run_tests", "description": "Run existing tests"},
            ],
            "write_documentation": [
                {"type": "research", "action": "gather_info", "description": "Gather information about the topic"},
                {"type": "document", "action": "write_docs", "description": "Write the documentation"},
                {"type": "review", "action": "review_docs", "description": "Review the documentation"},
            ],
        }
        
        # Check if we have a template for this task type
        if task_type in templates:
            subtasks = []
            for i, template in enumerate(templates[task_type]):
                subtask = {
                    **template,
                    "task_id": f"{task.get('task_id', 'unknown')}-{i}",
                    "parent_task_id": task.get("task_id"),
                    "workflow_id": task.get("workflow_id"),
                    "correlation_id": task.get("correlation_id"),
                }
                subtasks.append(subtask)
            return subtasks
        
        # No template found - return as single task
        return [task]
    
    async def _decompose_semantic(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Decompose using semantic analysis."""
        # This is a placeholder for semantic decomposition
        # In a real implementation, this would use NLP or other AI techniques
        
        description = task.get("description", "")
        task_type = task.get("type", "")
        
        # Simple heuristic: if description contains "and" or "," split it
        if " and " in description.lower():
            parts = description.split(" and ")
            return [
                {**task, "description": part, "task_id": f"{task.get('task_id', 'unknown')}-{i}"}
                for i, part in enumerate(parts)
            ]
        
        return [task]
    
    async def _decompose_recursive(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Decompose recursively until atomic tasks."""
        # For now, just use template-based decomposition
        return await self._decompose_by_template(task, task.get("type", ""))


# =============================================================================
# Result Aggregator
# =============================================================================

class ResultAggregator:
    """
    Aggregates results from multiple agents/subtasks.
    
    Combines and synthesizes results into a coherent final output.
    """
    
    def __init__(self):
        pass
    
    async def aggregate(
        self,
        task_id: TaskID,
        results: Dict[str, TaskResult],
        errors: Dict[str, str],
    ) -> Any:
        """
        Aggregate results from multiple subtasks.
        
        Args:
            task_id: The parent task ID
            results: Dictionary of subtask ID -> TaskResult
            errors: Dictionary of subtask ID -> error message
            
        Returns:
            Aggregated result
        """
        # Check if all subtasks completed successfully
        all_success = len(errors) == 0 and all(r.status == TaskStatus.COMPLETED for r in results.values())
        
        if all_success:
            # Combine all outputs
            combined = {}
            for step_id, result in results.items():
                combined[step_id] = result.output
            return {
                "status": "success",
                "task_id": task_id,
                "results": combined,
                "summary": self._generate_summary(results),
            }
        else:
            # Some subtasks failed
            return {
                "status": "partial",
                "task_id": task_id,
                "results": {k: v.output for k, v in results.items()},
                "errors": errors,
                "completed": len(results),
                "failed": len(errors),
            }
    
    def _generate_summary(self, results: Dict[str, TaskResult]) -> str:
        """Generate a summary of the results."""
        summaries = []
        for step_id, result in results.items():
            if result.output:
                if isinstance(result.output, str):
                    summaries.append(result.output[:200])  # Truncate long outputs
                elif isinstance(result.output, dict):
                    summaries.append(str(result.output.get("summary", result.output.get("result", "")))[:200])
                else:
                    summaries.append(str(result.output)[:200])
        
        return " | ".join(summaries)


# =============================================================================
# God Agent
# =============================================================================

class GodAgent(HybridAgent):
    """
    God Agent - The central orchestrator of the Harness Agentic Framework.
    
    The God Agent:
    - Receives high-level tasks from users
    - Decomposes complex tasks into subtasks
    - Routes subtasks to appropriate specialist agents
    - Aggregates and validates results
    - Manages workflow execution
    - Handles errors and retries
    
    This implements the Orchestrator-Workers pattern with:
    - God Agent as the orchestrator
    - Specialist Agents as the workers
    
    Example:
        >>> god = GodAgent()
        >>> await god.initialize()
        >>> result = await god.execute({"type": "implement_feature", "description": "Add user authentication"})
    """
    
    def __init__(
        self,
        name: str = "GodAgent",
        config: Optional[GodAgentConfig] = None,
        aci: Optional[ACIInterface] = None,
        sandbox: Optional[SandboxExecutor] = None,
        runtime_config: Optional[AgentRuntimeConfig] = None,
    ):
        """
        Initialize the God Agent.
        
        Args:
            name: Agent name (defaults to "GodAgent")
            config: God Agent configuration
            aci: ACI interface for communication
            sandbox: Sandbox executor
            runtime_config: Runtime configuration
        """
        # Load default config if not provided
        if config is None:
            try:
                config = get_agent_config("god")
                if not isinstance(config, GodAgentConfig):
                    from configs.schemas import GodAgentConfig
                    config = GodAgentConfig()
            except Exception:
                from configs.schemas import GodAgentConfig
                config = GodAgentConfig()
        
        # Initialize HybridAgent (which initializes both BaseAgent and BaseWorkflow)
        super().__init__(name, config, aci, sandbox, runtime_config)
        
        # Initialize components
        self._agent_registry = AgentRegistry()
        self._task_router = TaskRouter(self._agent_registry)
        self._task_decomposer = TaskDecomposer(self._agent_registry)
        self._result_aggregator = ResultAggregator()
        
        # Workflow tracking
        self._workflows: Dict[WorkflowID, WorkflowDefinition] = {}
        self._active_assignments: Dict[TaskID, TaskAssignment] = {}
        self._task_queue: asyncio.Queue = asyncio.Queue()
        
        # Configuration from GodAgentConfig
        self._max_concurrent_tasks = config.max_concurrent_tasks
        self._decomposition_strategy = DecompositionStrategy(config.decomposition_strategy)
        self._routing_strategy = RoutingStrategy(config.routing_strategy)
        
        # Update router and decomposer strategies
        self._task_router.strategy = self._routing_strategy
        self._task_decomposer.strategy = self._decomposition_strategy
        
        # Monitoring
        increment_metric("god.initialized", labels={"agent": self.name})
    
    # =========================================================================
    # Properties
    # =========================================================================
    
    @property
    def agent_registry(self) -> AgentRegistry:
        """Get the agent registry."""
        return self._agent_registry
    
    @property
    def task_router(self) -> TaskRouter:
        """Get the task router."""
        return self._task_router
    
    @property
    def task_decomposer(self) -> TaskDecomposer:
        """Get the task decomposer."""
        return self._task_decomposer
    
    @property
    def result_aggregator(self) -> ResultAggregator:
        """Get the result aggregator."""
        return self._result_aggregator
    
    @property
    def workflows(self) -> Dict[WorkflowID, WorkflowDefinition]:
        """Get all workflows."""
        return self._workflows.copy()
    
    @property
    def active_assignments(self) -> Dict[TaskID, TaskAssignment]:
        """Get all active assignments."""
        return self._active_assignments.copy()
    
    # =========================================================================
    # Lifecycle Methods
    # =========================================================================
    
    async def _do_initialize(self) -> None:
        """Initialize the God Agent."""
        # Initialize ACI for inter-agent communication
        await self._initialize_god_aci()
        
        # Initialize default tools
        await self._initialize_default_tools()
        
        # Initialize specialist agents (if configured)
        await self._initialize_specialists()
        
        self.log("God Agent initialized", "INFO")
    
    async def _do_shutdown(self) -> None:
        """Shutdown the God Agent."""
        # Shutdown all specialist agents
        await self._shutdown_specialists()
        
        # Clean up workflows
        self._workflows.clear()
        self._active_assignments.clear()
        
        self.log("God Agent shut down", "INFO")
    
    async def _initialize_god_aci(self) -> None:
        """Initialize God-specific ACI handlers."""
        # Register handlers for receiving results from specialists
        self._aci.register_handler("TaskResultCommand", self._handle_specialist_result)
        self._aci.register_handler("TaskErrorCommand", self._handle_specialist_error)
    
    async def _initialize_default_tools(self) -> None:
        """Initialize default tools for the God Agent."""
        # The God Agent doesn't typically use tools directly,
        # but it can have tools for managing workflows
        pass
    
    async def _initialize_specialists(self) -> None:
        """Initialize specialist agents."""
        # In a real implementation, this would create and initialize
        # all the specialist agents (Planner, Coder, Reviewer, etc.)
        # For now, we just log that this would happen
        self.log("Specialist agents would be initialized here", "DEBUG")
    
    async def _shutdown_specialists(self) -> None:
        """Shutdown all specialist agents."""
        # Shutdown all registered agents
        for agent_name in list(self._agent_registry.get_agent_names()):
            agent = self._agent_registry.get(agent_name)
            if agent is not None:
                try:
                    await agent.shutdown()
                except Exception as e:
                    self.log(f"Error shutting down {agent_name}: {e}", "ERROR")
    
    # =========================================================================
    # Agent Management
    # =========================================================================
    
    async def register_agent(self, agent: BaseAgent) -> None:
        """
        Register a specialist agent with the God Agent.
        
        Args:
            agent: The specialist agent to register
        """
        await self._agent_registry.register(agent)
        self.log(f"Agent registered: {agent.name}", "INFO")
    
    async def unregister_agent(self, agent_name: str) -> bool:
        """
        Unregister a specialist agent.
        
        Args:
            agent_name: Name of the agent to unregister
            
        Returns:
            True if agent was unregistered, False otherwise
        """
        result = await self._agent_registry.unregister(agent_name)
        if result:
            self.log(f"Agent unregistered: {agent_name}", "INFO")
        return result
    
    def get_agent(self, agent_name: str) -> Optional[BaseAgent]:
        """
        Get a registered specialist agent.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            The agent instance, or None if not found
        """
        return self._agent_registry.get(agent_name)
    
    def list_agents(self) -> List[str]:
        """Get list of all registered agent names."""
        return self._agent_registry.get_agent_names()
    
    # =========================================================================
    # Task Execution
    # =========================================================================
    
    async def _execute_task(self, task: Dict[str, Any], context: TaskContext) -> Any:
        """
        Execute a task as the God Agent.
        
        This is the main entry point for task execution. It:
        1. Decomposes the task if needed
        2. Routes subtasks to appropriate agents
        3. Executes and monitors subtasks
        4. Aggregates results
        5. Returns the final result
        
        Args:
            task: The task to execute
            context: Task context
            
        Returns:
            The result of the task execution
        """
        task_id = context.task_id
        
        # Check if this is a workflow
        if task.get("type") == "workflow" or "steps" in task:
            return await self._execute_workflow(task, context)
        
        # Decompose the task
        subtasks = await self._task_decomposer.decompose(task, context)
        
        if len(subtasks) == 1 and subtasks[0] == task:
            # Task doesn't need decomposition - route directly
            return await self._execute_single_task(task, context)
        else:
            # Execute as a workflow of subtasks
            return await self._execute_subtasks(subtasks, context)
    
    async def _execute_single_task(self, task: Dict[str, Any], context: TaskContext) -> Any:
        """Execute a single task by routing to a specialist."""
        # Route the task to the appropriate agent
        agent_name = self._task_router.route(task, context)
        
        if agent_name is None:
            raise TaskError(
                f"No agent found to handle task: {task.get('type', 'unknown')}",
                task_id=context.task_id
            )
        
        # Get the agent
        agent = self._agent_registry.get(agent_name)
        if agent is None:
            raise TaskError(
                f"Agent '{agent_name}' not available",
                task_id=context.task_id
            )
        
        # Create assignment
        assignment = TaskAssignment(
            assignment_id=str(uuid.uuid4()),
            task_id=context.task_id,
            agent_name=agent_name,
            task=task,
            context=context,
        )
        self._active_assignments[context.task_id] = assignment
        
        try:
            # Execute via the agent
            result = await agent.execute(task, **context.__dict__)
            
            # Mark assignment as complete
            assignment.status = "completed"
            assignment.result = result
            assignment.completed_at = datetime.utcnow()
            
            increment_metric("god.tasks_completed", labels={"agent": agent_name})
            
            return result
        
        except Exception as e:
            assignment.status = "failed"
            assignment.error = str(e)
            assignment.completed_at = datetime.utcnow()
            
            increment_metric("god.tasks_failed", labels={"agent": agent_name})
            
            raise TaskError(
                f"Task failed on agent {agent_name}: {e}",
                task_id=context.task_id
            ) from e
        
        finally:
            self._active_assignments.pop(context.task_id, None)
    
    async def _execute_subtasks(self, subtasks: List[Dict[str, Any]], context: TaskContext) -> Any:
        """Execute multiple subtasks."""
        results = {}
        errors = {}
        
        # Execute subtasks
        for i, subtask in enumerate(subtasks):
            subtask_context = TaskContext(
                task_id=subtask.get("task_id", f"{context.task_id}-{i}"),
                parent_task_id=context.task_id,
                workflow_id=context.workflow_id,
                correlation_id=context.correlation_id,
                user_request=context.user_request,
                metadata={**context.metadata, "subtask_index": i},
            )
            
            try:
                result = await self._execute_single_task(subtask, subtask_context)
                results[subtask_context.task_id] = TaskResult(
                    task_id=subtask_context.task_id,
                    status=TaskStatus.COMPLETED,
                    output=result,
                )
            except Exception as e:
                errors[subtask_context.task_id] = str(e)
                results[subtask_context.task_id] = TaskResult(
                    task_id=subtask_context.task_id,
                    status=TaskStatus.FAILED,
                    error=str(e),
                )
        
        # Aggregate results
        aggregated = await self._result_aggregator.aggregate(
            context.task_id, results, errors
        )
        
        return aggregated
    
    async def _execute_workflow(self, workflow_def: Dict[str, Any], context: TaskContext) -> Any:
        """Execute a predefined workflow."""
        # Create workflow definition
        workflow_id = workflow_def.get("workflow_id") or context.task_id
        steps_data = workflow_def.get("steps", [])
        
        workflow = WorkflowDefinition(
            workflow_id=workflow_id,
            name=workflow_def.get("name", "workflow"),
            description=workflow_def.get("description", ""),
        )
        
        # Convert step data to WorkflowStep objects
        for i, step_data in enumerate(steps_data):
            step = WorkflowStep(
                step_id=step_data.get("step_id", f"{workflow_id}-{i}"),
                name=step_data.get("name", f"Step {i}"),
                description=step_data.get("description", ""),
                agent_name=step_data.get("agent", ""),
                task_type=step_data.get("type", ""),
                input_data=step_data.get("input", {}),
                depends_on=step_data.get("depends_on", []),
                timeout=step_data.get("timeout"),
                priority=step_data.get("priority", "medium"),
            )
            workflow.steps.append(step)
        
        # Execute the workflow
        return await self._execute_workflow_definition(workflow, context)
    
    async def _execute_workflow_definition(
        self,
        workflow: WorkflowDefinition,
        context: TaskContext,
    ) -> Any:
        """Execute a workflow definition."""
        workflow_id = workflow.workflow_id
        self._workflows[workflow_id] = workflow
        
        try:
            # Mark workflow as running
            workflow.status = "running"
            workflow.start_time = datetime.utcnow()
            
            # Execute steps
            for step in workflow.steps:
                # Check dependencies
                if step.depends_on:
                    all_dependency_complete = all(
                        dep in workflow.completed_steps
                        for dep in step.depends_on
                    )
                    if not all_dependency_complete:
                        # Skip this step (will be retried later)
                        continue
                
                # Execute the step
                workflow.current_step = step.step_id
                step.start_time = datetime.utcnow()
                step.status = "running"
                
                try:
                    # Create task for this step
                    task = {
                        "type": step.task_type,
                        "action": step.name,
                        "description": step.description,
                        **step.input_data,
                    }
                    
                    step_context = TaskContext(
                        task_id=step.step_id,
                        parent_task_id=context.task_id,
                        workflow_id=workflow_id,
                        correlation_id=context.correlation_id,
                        user_request=context.user_request,
                        metadata=context.metadata,
                    )
                    
                    # Execute
                    result = await self._execute_single_task(task, step_context)
                    
                    # Update step
                    step.status = "completed"
                    step.end_time = datetime.utcnow()
                    step.result = result
                    workflow.completed_steps.append(step.step_id)
                    workflow.results[step.step_id] = result
                    
                except Exception as e:
                    step.status = "failed"
                    step.end_time = datetime.utcnow()
                    step.error = str(e)
                    workflow.failed_steps.append(step.step_id)
                    workflow.errors[step.step_id] = str(e)
                
                workflow.current_step = None
            
            # Check if workflow completed
            if len(workflow.failed_steps) > 0:
                workflow.status = "failed"
            elif len(workflow.completed_steps) == len(workflow.steps):
                workflow.status = "completed"
            else:
                workflow.status = "partial"
            
            workflow.end_time = datetime.utcnow()
            
            # Return aggregated results
            return {
                "status": workflow.status,
                "workflow_id": workflow_id,
                "results": workflow.results,
                "errors": workflow.errors,
                "completed_steps": len(workflow.completed_steps),
                "failed_steps": len(workflow.failed_steps),
                "duration_seconds": (workflow.end_time - workflow.start_time).total_seconds(),
            }
        
        finally:
            self._workflows.pop(workflow_id, None)
    
    # =========================================================================
    # ACI Handlers
    # =========================================================================
    
    async def _handle_specialist_result(self, message: Command) -> Response:
        """Handle result from a specialist agent."""
        if not isinstance(message, TaskResultCommand):
            return TaskResultResponse(
                task_id="",
                success=False,
                message="Invalid message type"
            )
        
        task_id = message.task_id
        assignment = self._active_assignments.get(task_id)
        
        if assignment is None:
            return TaskResultResponse(
                task_id=task_id,
                success=False,
                message=f"No active assignment for task {task_id}"
            )
        
        # Update assignment
        assignment.status = "completed"
        assignment.result = message.result
        assignment.completed_at = datetime.utcnow()
        
        return TaskResultResponse(
            task_id=task_id,
            success=True,
            message="Result received",
            result=message.result
        )
    
    async def _handle_specialist_error(self, message: Command) -> Response:
        """Handle error from a specialist agent."""
        task_id = getattr(message, 'task_id', 'unknown')
        error = getattr(message, 'error', 'Unknown error')
        
        assignment = self._active_assignments.get(task_id)
        if assignment is not None:
            assignment.status = "failed"
            assignment.error = error
            assignment.completed_at = datetime.utcnow()
        
        raise_alert(
            "Specialist agent error",
            f"Task {task_id} failed: {error}",
            severity=AlertSeverity.HIGH,
            context={"task_id": task_id, "error": error}
        )
        
        return TaskResultResponse(
            task_id=task_id,
            success=False,
            message="Error received"
        )
    
    # =========================================================================
    # Workflow Management
    # =========================================================================
    
    async def create_workflow(self, workflow_def: WorkflowDefinition) -> WorkflowDefinition:
        """Create a new workflow."""
        self._workflows[workflow_def.workflow_id] = workflow_def
        return workflow_def
    
    def get_workflow(self, workflow_id: WorkflowID) -> Optional[WorkflowDefinition]:
        """Get a workflow by ID."""
        return self._workflows.get(workflow_id)
    
    async def cancel_workflow(self, workflow_id: WorkflowID) -> bool:
        """Cancel a running workflow."""
        workflow = self._workflows.get(workflow_id)
        if workflow is None:
            return False
        
        workflow.status = "cancelled"
        workflow.end_time = datetime.utcnow()
        
        # Cancel all active assignments for this workflow
        for assignment_id, assignment in list(self._active_assignments.items()):
            if assignment.context.workflow_id == workflow_id:
                assignment.status = "cancelled"
                assignment.completed_at = datetime.utcnow()
                del self._active_assignments[assignment_id]
        
        return True
    
    # =========================================================================
    # Configuration Management
    # =========================================================================
    
    @property
    def max_concurrent_tasks(self) -> int:
        """Get max concurrent tasks."""
        return self._max_concurrent_tasks
    
    @max_concurrent_tasks.setter
    def max_concurrent_tasks(self, value: int) -> None:
        """Set max concurrent tasks."""
        self._max_concurrent_tasks = value
    
    @property
    def decomposition_strategy(self) -> DecompositionStrategy:
        """Get decomposition strategy."""
        return self._decomposition_strategy
    
    @decomposition_strategy.setter
    def decomposition_strategy(self, value: DecompositionStrategy) -> None:
        """Set decomposition strategy."""
        self._decomposition_strategy = value
        self._task_decomposer.strategy = value
    
    @property
    def routing_strategy(self) -> RoutingStrategy:
        """Get routing strategy."""
        return self._routing_strategy
    
    @routing_strategy.setter
    def routing_strategy(self, value: RoutingStrategy) -> None:
        """Set routing strategy."""
        self._routing_strategy = value
        self._task_router.strategy = value
    
    # =========================================================================
    # Status and Monitoring
    # =========================================================================
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the God Agent."""
        return {
            "name": self.name,
            "state": self.state.value,
            "registered_agents": len(self._agent_registry.get_agent_names()),
            "active_assignments": len(self._active_assignments),
            "active_workflows": len(self._workflows),
            "decomposition_strategy": self._decomposition_strategy.value,
            "routing_strategy": self._routing_strategy.value,
            "max_concurrent_tasks": self._max_concurrent_tasks,
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all God Agent activity."""
        return {
            **self.get_status(),
            "agent_names": self._agent_registry.get_agent_names(),
            "workflow_ids": list(self._workflows.keys()),
            "assignment_ids": list(self._active_assignments.keys()),
        }
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    async def broadcast(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Broadcast a message to all registered agents.
        
        Args:
            message: The message to broadcast
            
        Returns:
            Dictionary of agent_name -> response
        """
        responses = {}
        
        for agent_name in self._agent_registry.get_agent_names():
            agent = self._agent_registry.get(agent_name)
            if agent is not None:
                try:
                    response = await agent.aci.send(message)
                    responses[agent_name] = response
                except Exception as e:
                    responses[agent_name] = {"error": str(e)}
        
        return responses
    
    def __repr__(self) -> str:
        return f"GodAgent(name={self.name!r}, state={self.state.value!r}, agents={len(self._agent_registry.get_agent_names())})"
