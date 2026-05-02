"""
Base Agent Module.

Defines the foundational BaseAgent class that all other agents inherit from.
This is the core of the agent hierarchy (1.6% agent logic, 98.4% harness infrastructure).
"""

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic, Callable, Awaitable, Set

from pydantic import BaseModel, Field, field_validator

from core.aci.interface import ACIInterface, InMemoryACI, ACIError, MessageMetadata
from core.aci.commands import Command, TaskAssignmentCommand, TaskProgressCommand, TaskResultCommand, TaskErrorCommand
from core.aci.responses import Response, TaskAssignmentResponse, TaskResultResponse
from core.sandbox.executor import SandboxExecutor
from core.sandbox.permissions import PermissionSystem, get_permission_system
from configs.schemas import AgentConfig, AgentCapability
from configs import get_agent_config, get_config

from core.monitoring import (
    get_metrics_collector,
    get_tracer,
    start_span,
    increment_metric,
    record_metric,
    AlertSeverity,
    raise_alert,
)


# =============================================================================
# Type Definitions
# =============================================================================

T = TypeVar('T')

AgentID = str
TaskID = str


# =============================================================================
# Agent State
# =============================================================================

class AgentState(str, Enum):
    """Lifecycle states for an agent."""
    
    UNINITIALIZED = "uninitialized"  # Agent has been created but not initialized
    INITIALIZING = "initializing"    # Agent is being initialized
    IDLE = "idle"                    # Agent is ready and waiting for tasks
    BUSY = "busy"                    # Agent is currently executing a task
    PAUSED = "paused"                # Agent execution is paused
    ERROR = "error"                  # Agent encountered an error
    SHUTDOWN = "shutdown"            # Agent has been shut down
    CHECKPOINTING = "checkpointing"  # Agent is saving state
    RESTORING = "restoring"          # Agent is restoring from checkpoint


class AgentStatus(BaseModel):
    """Current status of an agent."""
    
    state: AgentState = Field(..., description="Current agent state")
    message: str = Field(default="", description="Status message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Last state change")
    task_count: int = Field(default=0, description="Total tasks processed")
    error_count: int = Field(default=0, description="Total errors encountered")
    active_tasks: int = Field(default=0, description="Currently active tasks")


# =============================================================================
# Agent Capabilities
# =============================================================================

class CapabilityLevel(str, Enum):
    """Proficiency level for a capability."""
    
    BASIC = "basic"       # Can perform simple, straightforward tasks
    STANDARD = "standard" # Can handle typical tasks with some complexity
    ADVANCED = "advanced" # Can handle complex tasks and edge cases
    EXPERT = "expert"     # Can handle all tasks, including creative problem-solving


@dataclass
class AgentCapabilityInfo:
    """Information about an agent's capability."""
    
    name: str
    description: str
    level: CapabilityLevel = CapabilityLevel.STANDARD
    version: str = "1.0"
    depends_on: List[str] = field(default_factory=list)
    tool_requirements: List[str] = field(default_factory=list)


# =============================================================================
# Tool Interface (Forward Reference)
# =============================================================================

class BaseTool(ABC):
    """Abstract base class for tools. Defined in tools/base/tool.py"""
    
    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        pass


# =============================================================================
# Agent Configuration
# =============================================================================

class AgentRuntimeConfig(BaseModel):
    """Runtime configuration for an agent (extends the static AgentConfig)."""
    
    agent_id: AgentID = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique agent instance ID")
    name: str = Field(..., description="Agent name")
    version: str = Field(default="1.0", description="Agent version")
    
    # Execution settings
    max_concurrent_tasks: int = Field(default=1, ge=1, le=10, description="Max concurrent tasks")
    task_timeout: float = Field(default=300.0, ge=1.0, le=3600.0, description="Default task timeout in seconds")
    retry_attempts: int = Field(default=3, ge=0, le=10, description="Max retry attempts")
    retry_delay: float = Field(default=1.0, ge=0.1, le=60.0, description="Delay between retries")
    
    # Resource limits
    max_memory_mb: int = Field(default=1024, ge=64, le=8192, description="Max memory in MB")
    max_cpu: float = Field(default=1.0, ge=0.1, le=8.0, description="Max CPU cores")
    
    # Security
    sandbox_enabled: bool = Field(default=True, description="Enable sandboxing for code execution")
    permission_level: str = Field(default="standard", description="Permission level for this agent")
    
    # Monitoring
    metrics_enabled: bool = Field(default=True, description="Enable metrics collection")
    tracing_enabled: bool = Field(default=True, description="Enable tracing")
    
    # Checkpointing
    checkpoint_interval: int = Field(default=0, ge=0, description="Auto-checkpoint interval in seconds (0 = manual)")
    
    # Derived from AgentConfig
    description: str = Field(default="", description="Agent description")
    capabilities: List[AgentCapability] = Field(default_factory=list, description="Agent capabilities")


# =============================================================================
# Task Definitions
# =============================================================================

class TaskPriority(str, Enum):
    """Priority levels for tasks."""
    
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(str, Enum):
    """Status of a task."""
    
    PENDING = "pending"       # Task has been queued
    RUNNING = "running"       # Task is being executed
    COMPLETED = "completed"   # Task completed successfully
    FAILED = "failed"         # Task failed
    CANCELLED = "cancelled"   # Task was cancelled
    RETRYING = "retrying"     # Task is being retried
    TIMEOUT = "timeout"       # Task timed out


@dataclass
class TaskContext:
    """Context for a task execution."""
    
    task_id: TaskID
    parent_task_id: Optional[TaskID] = None
    workflow_id: Optional[str] = None
    correlation_id: Optional[str] = None
    user_request: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    """Result of a task execution."""
    
    task_id: TaskID
    status: TaskStatus
    output: Any = None
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0
    retry_count: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)


# =============================================================================
# Base Agent Class
# =============================================================================

class BaseAgent(ABC, Generic[T]):
    """
    Abstract base class for all agents in the Harness Agentic Framework.
    
    This class provides the foundation for all agents with:
    - ACI (Agent-Computer Interface) integration
    - Async task execution
    - Tool management
    - State management
    - Checkpointing
    - Monitoring and observability
    - Error handling and Poka-Yoke
    
    All agents (God Agent and Specialist Agents) inherit from this class.
    
    Example:
        >>> class MyAgent(BaseAgent):
        ...     async def execute_task(self, task: dict) -> Any:
        ...         return "Hello, World!"
        ...
        >>> agent = MyAgent(name="MyAgent", config=config)
        >>> await agent.initialize()
        >>> result = await agent.execute(task={"action": "greet"})
    """
    
    # Class-level defaults
    DEFAULT_TIMEOUT = 300.0  # 5 minutes
    DEFAULT_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1.0
    
    def __init__(
        self,
        name: str,
        config: Optional[AgentConfig] = None,
        aci: Optional[ACIInterface] = None,
        sandbox: Optional[SandboxExecutor] = None,
        runtime_config: Optional[AgentRuntimeConfig] = None,
    ):
        """
        Initialize the base agent.
        
        Args:
            name: Agent name (must be unique)
            config: Agent configuration (from configs.schemas)
            aci: ACI interface for communication (defaults to InMemoryACI)
            sandbox: Sandbox executor for safe code execution
            runtime_config: Runtime configuration overrides
        """
        # Unique identifiers
        self._agent_id: AgentID = str(uuid.uuid4())
        self._name: str = name
        
        # Configuration
        if config is None:
            try:
                config = get_agent_config(name.lower())
            except (ValueError, Exception):
                # Fallback to default
                from configs.schemas import AgentConfig
                config = AgentConfig(name=name, description=f"Agent: {name}")
        self._config: AgentConfig = config
        
        # Runtime configuration (extends static config)
        if runtime_config is None:
            runtime_config = AgentRuntimeConfig(
                name=name,
                description=config.description or f"Agent: {name}",
                capabilities=config.capabilities or [],
            )
        self._runtime_config: AgentRuntimeConfig = runtime_config
        
        # ACI Interface
        if aci is None:
            aci = InMemoryACI(name=f"{name}-ACI")
        self._aci: ACIInterface = aci
        
        # Sandbox
        if sandbox is None:
            from core.sandbox.executor import SandboxExecutor
            sandbox = SandboxExecutor()
        self._sandbox: SandboxExecutor = sandbox
        
        # Permission system
        self._permissions = get_permission_system()
        
        # State management
        self._state: AgentState = AgentState.UNINITIALIZED
        self._status: AgentStatus = AgentStatus(
            state=AgentState.UNINITIALIZED,
            message="Agent created, not yet initialized"
        )
        
        # Task management
        self._active_tasks: Dict[TaskID, TaskContext] = {}
        self._pending_tasks: asyncio.Queue = asyncio.Queue()
        self._task_counter: int = 0
        self._task_semaphore: Optional[asyncio.Semaphore] = None
        
        # Tool management
        self._tools: Dict[str, BaseTool] = {}
        self._tool_lock: asyncio.Lock = asyncio.Lock()
        
        # Monitoring
        self._metrics_collector = get_metrics_collector()
        self._tracer = get_tracer()
        
        # Checkpointing
        self._checkpoint_data: Dict[str, Any] = {}
        self._last_checkpoint: Optional[datetime] = None
        
        # Event handlers
        self._on_initialize: List[Callable[[BaseAgent], Awaitable[None]]] = []
        self._on_shutdown: List[Callable[[BaseAgent], Awaitable[None]]] = []
        self._on_task_start: List[Callable[[BaseAgent, TaskContext], Awaitable[None]]] = []
        self._on_task_complete: List[Callable[[BaseAgent, TaskContext, TaskResult], Awaitable[None]]] = []
        self._on_error: List[Callable[[BaseAgent, Exception], Awaitable[None]]] = []
        
        # Initialize metrics
        self._init_metrics()
        
        # Record creation
        increment_metric("agents.created", labels={"agent": name})
    
    # =========================================================================
    # Properties
    # =========================================================================
    
    @property
    def agent_id(self) -> AgentID:
        """Get the unique agent identifier."""
        return self._agent_id
    
    @property
    def name(self) -> str:
        """Get the agent name."""
        return self._name
    
    @property
    def description(self) -> str:
        """Get the agent description."""
        return self._runtime_config.description or self._config.description or f"Agent: {self._name}"
    
    @property
    def config(self) -> AgentConfig:
        """Get the agent configuration."""
        return self._config
    
    @property
    def runtime_config(self) -> AgentRuntimeConfig:
        """Get the runtime configuration."""
        return self._runtime_config
    
    @property
    def state(self) -> AgentState:
        """Get the current agent state."""
        return self._state
    
    @property
    def status(self) -> AgentStatus:
        """Get the current agent status."""
        return self._status
    
    @property
    def aci(self) -> ACIInterface:
        """Get the ACI interface."""
        return self._aci
    
    @property
    def sandbox(self) -> SandboxExecutor:
        """Get the sandbox executor."""
        return self._sandbox
    
    @property
    def capabilities(self) -> List[AgentCapability]:
        """Get the agent's capabilities."""
        return self._runtime_config.capabilities
    
    @property
    def capabilities_str(self) -> List[str]:
        """Get list of capability names as strings."""
        return [cap.name for cap in self._runtime_config.capabilities]
    
    @property
    def active_tasks(self) -> Dict[TaskID, TaskContext]:
        """Get currently active tasks."""
        return self._active_tasks.copy()
    
    @property
    def tools(self) -> Dict[str, BaseTool]:
        """Get registered tools."""
        return self._tools.copy()
    
    @property
    def tool_names(self) -> List[str]:
        """Get list of registered tool names."""
        return list(self._tools.keys())
    
    @property
    def is_initialized(self) -> bool:
        """Check if agent is initialized."""
        return self._state in [AgentState.IDLE, AgentState.BUSY, AgentState.PAUSED]
    
    @property
    def is_available(self) -> bool:
        """Check if agent is available for new tasks."""
        return self._state == AgentState.IDLE
    
    @property
    def is_busy(self) -> bool:
        """Check if agent is currently busy."""
        return self._state == AgentState.BUSY
    
    # =========================================================================
    # Lifecycle Methods
    # =========================================================================
    
    async def initialize(self) -> None:
        """
        Initialize the agent.
        
        This method should be called before the agent can process any tasks.
        It sets up the agent's resources, registers handlers, and transitions
        to the IDLE state.
        
        Raises:
            AgentError: If initialization fails
        """
        if self._state != AgentState.UNINITIALIZED:
            raise AgentError(f"Cannot initialize agent in state: {self._state}")
        
        self._set_state(AgentState.INITIALIZING, "Initializing agent...")
        
        try:
            # Initialize task semaphore
            max_concurrent = self._runtime_config.max_concurrent_tasks
            self._task_semaphore = asyncio.Semaphore(max_concurrent)
            
            # Initialize ACI handlers
            await self._initialize_aci()
            
            # Initialize tools (to be overridden by subclasses)
            await self._initialize_tools()
            
            # Initialize monitoring
            await self._initialize_monitoring()
            
            # Call the abstract initialization method
            await self._do_initialize()
            
            # Transition to IDLE
            self._set_state(AgentState.IDLE, "Agent initialized and ready")
            
            # Trigger event handlers
            for handler in self._on_initialize:
                await handler(self)
            
            increment_metric("agents.initialized", labels={"agent": self.name})
            
        except Exception as e:
            self._set_state(AgentState.ERROR, f"Initialization failed: {e}")
            raise AgentError(f"Failed to initialize agent {self.name}: {e}") from e
    
    async def shutdown(self) -> None:
        """
        Shutdown the agent gracefully.
        
        This method cleans up resources, saves checkpoint, and transitions
        to the SHUTDOWN state.
        
        Raises:
            AgentError: If shutdown fails
        """
        if self._state == AgentState.SHUTDOWN:
            return  # Already shut down
        
        self._set_state(AgentState.SHUTDOWN, "Shutting down agent...")
        
        try:
            # Wait for active tasks to complete
            await self._wait_for_active_tasks()
            
            # Call the abstract shutdown method
            await self._do_shutdown()
            
            # Shutdown ACI
            await self._shutdown_aci()
            
            # Trigger event handlers
            for handler in self._on_shutdown:
                await handler(self)
            
            increment_metric("agents.shutdown", labels={"agent": self.name})
            
        except Exception as e:
            raise AgentError(f"Failed to shutdown agent {self.name}: {e}") from e
    
    async def restart(self) -> None:
        """
        Restart the agent.
        
        This is equivalent to shutdown followed by initialize.
        """
        await self.shutdown()
        await self.initialize()
    
    # =========================================================================
    # Abstract Lifecycle Methods (to be implemented by subclasses)
    # =========================================================================
    
    @abstractmethod
    async def _do_initialize(self) -> None:
        """
        Perform agent-specific initialization.
        
        Subclasses should override this method to perform custom initialization.
        Called during initialize() after basic setup is complete.
        """
        pass
    
    @abstractmethod
    async def _do_shutdown(self) -> None:
        """
        Perform agent-specific shutdown.
        
        Subclasses should override this method to perform custom cleanup.
        Called during shutdown() before ACI shutdown.
        """
        pass
    
    @abstractmethod
    async def _execute_task(self, task: Dict[str, Any], context: TaskContext) -> Any:
        """
        Execute a task.
        
        This is the main method that subclasses must implement.
        It contains the agent-specific logic for processing tasks.
        
        Args:
            task: The task to execute
            context: Task context (ID, parent, workflow, etc.)
            
        Returns:
            The result of the task execution
            
        Raises:
            TaskError: If the task cannot be completed
        """
        pass
    
    # =========================================================================
    # Task Execution Methods
    # =========================================================================
    
    async def execute(self, task: Dict[str, Any], **kwargs) -> Any:
        """
        Execute a task asynchronously.
        
        This is the primary entry point for task execution.
        It handles task queuing, execution, retries, and error handling.
        
        Args:
            task: The task to execute
            **kwargs: Additional task parameters
            
        Returns:
            The result of the task execution
            
        Raises:
            AgentError: If the agent cannot process the task
            TaskError: If the task fails after all retries
        """
        if not self.is_initialized:
            raise AgentError(f"Agent {self.name} is not initialized")
        
        # Generate task ID
        task_id = kwargs.get('task_id') or str(uuid.uuid4())
        
        # Create task context
        context = TaskContext(
            task_id=task_id,
            parent_task_id=kwargs.get('parent_task_id'),
            workflow_id=kwargs.get('workflow_id'),
            correlation_id=kwargs.get('correlation_id'),
            user_request=kwargs.get('user_request'),
            metadata=kwargs.get('metadata', {}),
        )
        
        # Queue the task
        await self._queue_task(context, task)
        
        # Execute with retries
        return await self._execute_with_retries(context, task)
    
    async def execute_batch(self, tasks: List[Dict[str, Any]], **kwargs) -> List[Any]:
        """
        Execute multiple tasks.
        
        Args:
            tasks: List of tasks to execute
            **kwargs: Common parameters for all tasks
            
        Returns:
            List of results (in same order as tasks)
        """
        if not self.is_initialized:
            raise AgentError(f"Agent {self.name} is not initialized")
        
        results = []
        for task in tasks:
            result = await self.execute(task, **kwargs)
            results.append(result)
        return results
    
    async def execute_parallel(
        self,
        tasks: List[Dict[str, Any]],
        max_concurrent: Optional[int] = None,
        **kwargs
    ) -> List[Any]:
        """
        Execute multiple tasks in parallel.
        
        Args:
            tasks: List of tasks to execute
            max_concurrent: Maximum concurrent tasks (defaults to agent's max)
            **kwargs: Common parameters for all tasks
            
        Returns:
            List of results (in same order as tasks)
        """
        if not self.is_initialized:
            raise AgentError(f"Agent {self.name} is not initialized")
        
        max_concurrent = max_concurrent or self._runtime_config.max_concurrent_tasks
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def execute_single(task):
            async with semaphore:
                return await self.execute(task, **kwargs)
        
        # Execute all tasks concurrently
        coros = [execute_single(task) for task in tasks]
        return await asyncio.gather(*coros, return_exceptions=True)
    
    async def cancel_task(self, task_id: TaskID) -> bool:
        """
        Cancel a running task.
        
        Args:
            task_id: The task ID to cancel
            
        Returns:
            True if task was cancelled, False if not found or already complete
        """
        if task_id in self._active_tasks:
            context = self._active_tasks[task_id]
            # Mark as cancelled
            context.metadata["cancelled"] = True
            del self._active_tasks[task_id]
            increment_metric("tasks.cancelled", labels={"agent": self.name})
            return True
        return False
    
    async def cancel_all_tasks(self) -> int:
        """
        Cancel all active tasks.
        
        Returns:
            Number of tasks cancelled
        """
        count = 0
        for task_id in list(self._active_tasks.keys()):
            if await self.cancel_task(task_id):
                count += 1
        return count
    
    # =========================================================================
    # Internal Task Execution
    # =========================================================================
    
    async def _queue_task(self, context: TaskContext, task: Dict[str, Any]) -> None:
        """Queue a task for execution."""
        await self._pending_tasks.put((context, task))
        increment_metric("tasks.queued", labels={"agent": self.name})
    
    async def _execute_with_retries(
        self,
        context: TaskContext,
        task: Dict[str, Any],
        retry_count: int = 0
    ) -> Any:
        """Execute a task with retry logic."""
        max_retries = self._runtime_config.retry_attempts
        retry_delay = self._runtime_config.retry_delay
        
        try:
            # Acquire semaphore (wait if at max concurrent)
            async with self._task_semaphore:
                # Update state
                self._active_tasks[context.task_id] = context
                self._set_state(AgentState.BUSY, f"Executing task {context.task_id}")
                
                # Trigger task start handlers
                for handler in self._on_task_start:
                    await handler(self, context)
                
                # Execute with timeout
                timeout = self._runtime_config.task_timeout
                
                try:
                    result = await asyncio.wait_for(
                        self._do_execute(context, task),
                        timeout=timeout
                    )
                    
                    # Task completed successfully
                    task_result = TaskResult(
                        task_id=context.task_id,
                        status=TaskStatus.COMPLETED,
                        output=result,
                        duration_seconds=0.0,  # Will be set below
                        retry_count=retry_count,
                    )
                    
                    # Trigger task complete handlers
                    for handler in self._on_task_complete:
                        await handler(self, context, task_result)
                    
                    increment_metric("tasks.completed", labels={"agent": self.name})
                    return result
                    
                except asyncio.TimeoutError:
                    task_result = TaskResult(
                        task_id=context.task_id,
                        status=TaskStatus.TIMEOUT,
                        error=f"Task timed out after {timeout}s",
                        retry_count=retry_count,
                    )
                    increment_metric("tasks.timeout", labels={"agent": self.name})
                    raise TaskError(f"Task timed out: {context.task_id}") from None
                
                except TaskError as e:
                    # Task failed, check if we should retry
                    if retry_count < max_retries:
                        self._set_state(
                            AgentState.BUSY,
                            f"Retrying task {context.task_id} (attempt {retry_count + 1}/{max_retries})"
                        )
                        await asyncio.sleep(retry_delay)
                        return await self._execute_with_retries(context, task, retry_count + 1)
                    else:
                        task_result = TaskResult(
                            task_id=context.task_id,
                            status=TaskStatus.FAILED,
                            error=str(e),
                            retry_count=retry_count,
                        )
                        increment_metric("tasks.failed", labels={"agent": self.name})
                        raise
                
                except Exception as e:
                    task_result = TaskResult(
                        task_id=context.task_id,
                        status=TaskStatus.FAILED,
                        error=str(e),
                        retry_count=retry_count,
                    )
                    increment_metric("tasks.failed", labels={"agent": self.name})
                    raise TaskError(f"Task failed: {e}") from e
                
                finally:
                    # Clean up
                    self._active_tasks.pop(context.task_id, None)
                    self._update_state_after_task()
        
        except Exception:
            # This shouldn't happen, but just in case
            self._active_tasks.pop(context.task_id, None)
            self._update_state_after_task()
            raise
    
    async def _do_execute(self, context: TaskContext, task: Dict[str, Any]) -> Any:
        """Internal execute with tracing and monitoring."""
        task_type = task.get("type") or task.get("action") or "unknown"
        
        async with start_span(
            f"{self.name}.execute",
            {"task_id": context.task_id, "task_type": task_type}
        ):
            try:
                return await self._execute_task(task, context)
            except Exception as e:
                raise_alert(
                    f"Agent {self.name} task failed",
                    f"Task {context.task_id} of type {task_type} failed: {e}",
                    severity=AlertSeverity.HIGH,
                    context={"agent": self.name, "task_id": context.task_id, "task_type": task_type}
                )
                raise
    
    def _update_state_after_task(self) -> None:
        """Update agent state after a task completes."""
        if len(self._active_tasks) == 0:
            self._set_state(AgentState.IDLE, "Ready for new tasks")
    
    async def _wait_for_active_tasks(self) -> None:
        """Wait for all active tasks to complete."""
        while len(self._active_tasks) > 0:
            await asyncio.sleep(0.1)
    
    # =========================================================================
    # Tool Management
    # =========================================================================
    
    async def _initialize_tools(self) -> None:
        """
        Initialize agent tools.
        
        Subclasses can override this to register default tools.
        """
        pass
    
    async def add_tool(self, name: str, tool: BaseTool) -> None:
        """
        Add a tool to the agent.
        
        Args:
            name: Unique name for the tool
            tool: The tool instance
            
        Raises:
            AgentError: If a tool with the same name already exists
        """
        async with self._tool_lock:
            if name in self._tools:
                raise AgentError(f"Tool '{name}' already registered")
            
            self._tools[name] = tool
            increment_metric("tools.registered", labels={"agent": self.name, "tool": name})
    
    async def remove_tool(self, name: str) -> bool:
        """
        Remove a tool from the agent.
        
        Args:
            name: Name of the tool to remove
            
        Returns:
            True if the tool was removed, False if not found
        """
        async with self._tool_lock:
            if name in self._tools:
                del self._tools[name]
                increment_metric("tools.unregistered", labels={"agent": self.name, "tool": name})
                return True
            return False
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """
        Get a tool by name.
        
        Args:
            name: Name of the tool
            
        Returns:
            The tool instance, or None if not found
        """
        return self._tools.get(name)
    
    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools
    
    async def use_tool(
        self,
        name: str,
        *args,
        **kwargs
    ) -> Any:
        """
        Use a registered tool.
        
        Args:
            name: Name of the tool to use
            *args: Arguments to pass to the tool
            **kwargs: Keyword arguments to pass to the tool
            
        Returns:
            The result of the tool execution
            
        Raises:
            AgentError: If the tool is not found or execution fails
        """
        tool = self.get_tool(name)
        if tool is None:
            raise AgentError(f"Tool '{name}' not found")
        
        # Check permissions
        if not self._check_tool_permission(name):
            raise AgentError(f"Agent {self.name} does not have permission to use tool '{name}'")
        
        try:
            async with start_span(f"{self.name}.use_tool", {"tool": name}):
                result = await tool.execute(*args, **kwargs)
                increment_metric("tools.executed", labels={"agent": self.name, "tool": name, "status": "success"})
                return result
        except Exception as e:
            increment_metric("tools.executed", labels={"agent": self.name, "tool": name, "status": "failed"})
            raise AgentError(f"Tool '{name}' execution failed: {e}") from e
    
    def _check_tool_permission(self, tool_name: str) -> bool:
        """Check if the agent has permission to use a tool."""
        # By default, allow all tools
        # Subclasses can override this for stricter control
        return True
    
    # =========================================================================
    # ACI Integration
    # =========================================================================
    
    async def _initialize_aci(self) -> None:
        """Initialize ACI handlers."""
        # Register default handlers
        self._aci.register_handler("TaskAssignmentCommand", self._handle_task_assignment)
        self._aci.register_handler("TaskProgressCommand", self._handle_task_progress)
        self._aci.register_handler("TaskResultCommand", self._handle_task_result)
        self._aci.register_handler("TaskErrorCommand", self._handle_task_error)
    
    async def _shutdown_aci(self) -> None:
        """Shutdown ACI handlers."""
        pass  # Cleanup if needed
    
    async def _handle_task_assignment(self, message: Command) -> Response:
        """Handle task assignment command via ACI."""
        if isinstance(message, TaskAssignmentCommand):
            task = message.task
            context = TaskContext(
                task_id=message.task_id,
                parent_task_id=message.parent_task_id,
                workflow_id=message.workflow_id,
                correlation_id=message.correlation_id,
            )
            
            try:
                result = await self.execute(task, **context.__dict__)
                return TaskAssignmentResponse(
                    task_id=message.task_id,
                    accepted=True,
                    message="Task accepted",
                    result=result
                )
            except Exception as e:
                return TaskAssignmentResponse(
                    task_id=message.task_id,
                    accepted=False,
                    message=f"Task failed: {e}",
                    error=str(e)
                )
        
        return TaskResultResponse(
            task_id="",
            success=False,
            message="Invalid message type"
        )
    
    async def _handle_task_progress(self, message: Command) -> Response:
        """Handle task progress command via ACI."""
        return TaskResultResponse(
            task_id=getattr(message, 'task_id', ''),
            success=True,
            message="Progress acknowledged"
        )
    
    async def _handle_task_result(self, message: Command) -> Response:
        """Handle task result command via ACI."""
        return TaskResultResponse(
            task_id=getattr(message, 'task_id', ''),
            success=True,
            message="Result acknowledged"
        )
    
    async def _handle_task_error(self, message: Command) -> Response:
        """Handle task error command via ACI."""
        # Log the error
        error_msg = getattr(message, 'error', 'Unknown error')
        raise_alert(
            f"Task error received by {self.name}",
            error_msg,
            severity=AlertSeverity.HIGH,
            context={"agent": self.name, "message_id": getattr(message, 'message_id', 'unknown')}
        )
        return TaskResultResponse(
            task_id=getattr(message, 'task_id', ''),
            success=False,
            message="Error acknowledged"
        )
    
    # =========================================================================
    # Checkpointing
    # =========================================================================
    
    async def checkpoint(self, checkpoint_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Save the agent's state to a checkpoint.
        
        Args:
            checkpoint_id: Optional identifier for the checkpoint
            
        Returns:
            The checkpoint data
        """
        if checkpoint_id is None:
            checkpoint_id = f"{self.name}-{datetime.utcnow().isoformat()}-{self._checkpoint_counter}"
            self._checkpoint_counter += 1
        
        checkpoint_data = {
            "agent_id": self._agent_id,
            "name": self._name,
            "state": self._state.value,
            "status": self._status.model_dump(),
            "active_tasks": {tid: ctx.__dict__ for tid, ctx in self._active_tasks.items()},
            "task_counter": self._task_counter,
            "checkpoint_data": self._checkpoint_data,
            "timestamp": datetime.utcnow().isoformat(),
            "checkpoint_id": checkpoint_id,
        }
        
        self._last_checkpoint = datetime.utcnow()
        self._checkpoint_data = checkpoint_data
        
        increment_metric("checkpoints.created", labels={"agent": self.name})
        return checkpoint_data
    
    async def restore(self, checkpoint_data: Dict[str, Any]) -> None:
        """
        Restore the agent's state from a checkpoint.
        
        Args:
            checkpoint_data: The checkpoint data to restore from
            
        Raises:
            AgentError: If restoration fails
        """
        self._set_state(AgentState.RESTORING, "Restoring from checkpoint...")
        
        try:
            self._agent_id = checkpoint_data.get("agent_id", self._agent_id)
            self._name = checkpoint_data.get("name", self._name)
            self._state = AgentState(checkpoint_data.get("state", self._state.value))
            
            status_data = checkpoint_data.get("status", {})
            if status_data:
                self._status = AgentStatus(**status_data)
            
            # Restore active tasks (as pending since we're restoring)
            active_tasks_data = checkpoint_data.get("active_tasks", {})
            for tid, ctx_data in active_tasks_data.items():
                ctx = TaskContext(**ctx_data)
                self._active_tasks[tid] = ctx
            
            self._task_counter = checkpoint_data.get("task_counter", self._task_counter)
            self._checkpoint_data = checkpoint_data.get("checkpoint_data", {})
            
            self._last_checkpoint = datetime.utcnow()
            self._set_state(AgentState.IDLE, f"Restored from checkpoint {checkpoint_data.get('checkpoint_id', 'unknown')}")
            
            increment_metric("checkpoints.restored", labels={"agent": self.name})
        
        except Exception as e:
            self._set_state(AgentState.ERROR, f"Restore failed: {e}")
            raise AgentError(f"Failed to restore from checkpoint: {e}") from e
    
    # =========================================================================
    # Monitoring
    # =========================================================================
    
    async def _initialize_monitoring(self) -> None:
        """Initialize monitoring for the agent."""
        # Register agent-specific metrics
        pass
    
    def _init_metrics(self) -> None:
        """Initialize agent-specific metrics."""
        # These are registered with the global metrics collector
        pass
    
    # =========================================================================
    # State Management
    # =========================================================================
    
    def _set_state(self, state: AgentState, message: str = "") -> None:
        """Update the agent state."""
        old_state = self._state
        self._state = state
        self._status = AgentStatus(
            state=state,
            message=message,
            timestamp=datetime.utcnow(),
            task_count=self._status.task_count,
            error_count=self._status.error_count,
            active_tasks=len(self._active_tasks),
        )
        
        # Update metrics
        if old_state != state:
            increment_metric("agents.state_changes", labels={
                "agent": self.name,
                "from": old_state.value,
                "to": state.value
            })
    
    # =========================================================================
    # Event Handlers
    # =========================================================================
    
    def on_initialize(self, handler: Callable[[BaseAgent], Awaitable[None]]) -> None:
        """Register an initialize event handler."""
        self._on_initialize.append(handler)
    
    def on_shutdown(self, handler: Callable[[BaseAgent], Awaitable[None]]) -> None:
        """Register a shutdown event handler."""
        self._on_shutdown.append(handler)
    
    def on_task_start(self, handler: Callable[[BaseAgent, TaskContext], Awaitable[None]]) -> None:
        """Register a task start event handler."""
        self._on_task_start.append(handler)
    
    def on_task_complete(
        self,
        handler: Callable[[BaseAgent, TaskContext, TaskResult], Awaitable[None]]
    ) -> None:
        """Register a task complete event handler."""
        self._on_task_complete.append(handler)
    
    def on_error(self, handler: Callable[[BaseAgent, Exception], Awaitable[None]]) -> None:
        """Register an error event handler."""
        self._on_error.append(handler)
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def log(self, message: str, level: str = "INFO") -> None:
        """Log a message with agent context."""
        import logging
        logger = logging.getLogger(f"harness.agents.{self.name}")
        getattr(logger, level.lower(), logger.info)(f"[{self.state.value}] {message}")
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, state={self.state.value!r})"


# =============================================================================
# BaseWorkflow Class
# =============================================================================

class BaseWorkflow(ABC):
    """
    Abstract base class for workflow execution.
    
    Workflows orchestrate multiple agents to complete complex tasks.
    This is separate from the agent hierarchy but tightly integrated.
    """
    
    def __init__(
        self,
        name: str,
        agents: Optional[Dict[str, BaseAgent]] = None,
    ):
        self.name = name
        self._agents = agents or {}
        self._steps = []
    
    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the workflow."""
        pass
    
    @abstractmethod
    async def add_step(self, step_definition: Dict[str, Any]) -> None:
        """Add a step to the workflow."""
        pass


# =============================================================================
# HybridAgent Class (Agent + Workflow capabilities)
# =============================================================================

class HybridAgent(BaseAgent, BaseWorkflow):
    """
    Hybrid agent that can act as both an agent and a workflow orchestrator.
    
    This is useful for agents that need to both perform tasks directly
    and coordinate other agents (like the God Agent).
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[AgentConfig] = None,
        aci: Optional[ACIInterface] = None,
        sandbox: Optional[SandboxExecutor] = None,
        runtime_config: Optional[AgentRuntimeConfig] = None,
    ):
        # Initialize both parent classes
        BaseAgent.__init__(self, name, config, aci, sandbox, runtime_config)
        BaseWorkflow.__init__(self, name)
    
    async def _do_initialize(self) -> None:
        """Initialize the hybrid agent."""
        pass
    
    async def _do_shutdown(self) -> None:
        """Shutdown the hybrid agent."""
        pass
    
    async def _execute_task(self, task: Dict[str, Any], context: TaskContext) -> Any:
        """Execute a task (to be implemented by subclasses)."""
        pass
    
    async def execute(self, task: Dict[str, Any], **kwargs) -> Any:
        """
        Execute a task or workflow.
        
        For hybrid agents, this can either execute a task directly
        or orchestrate a workflow based on the task type.
        """
        # Check if this is a workflow task
        task_type = task.get("type") or task.get("action")
        
        if task_type == "workflow":
            # Execute as workflow
            return await BaseWorkflow.execute(self, task)
        else:
            # Execute as regular task
            return await BaseAgent.execute(self, task, **kwargs)


# =============================================================================
# Exceptions
# =============================================================================

class AgentError(Exception):
    """Base exception for agent-related errors."""
    
    def __init__(self, message: str, code: Optional[str] = None, details: Optional[Dict] = None):
        super().__init__(message)
        self.message = message
        self.code = code or "AGENT_ERROR"
        self.details = details or {}


class TaskError(AgentError):
    """Exception for task execution errors."""
    
    def __init__(self, message: str, task_id: Optional[str] = None, details: Optional[Dict] = None):
        super().__init__(message, code="TASK_ERROR", details=details)
        self.task_id = task_id


class InitializationError(AgentError):
    """Exception for agent initialization errors."""
    
    def __init__(self, message: str, agent_name: Optional[str] = None, details: Optional[Dict] = None):
        super().__init__(message, code="INITIALIZATION_ERROR", details=details)
        self.agent_name = agent_name


class ConfigurationError(AgentError):
    """Exception for configuration errors."""
    
    def __init__(self, message: str, config_section: Optional[str] = None, details: Optional[Dict] = None):
        super().__init__(message, code="CONFIGURATION_ERROR", details=details)
        self.config_section = config_section


# =============================================================================
# Type Aliases for Convenience
# =============================================================================

AgentClass = Type[BaseAgent]
AgentFactory = Callable[..., BaseAgent]
