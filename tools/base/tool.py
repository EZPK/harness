"""
Base Tool Module.

Defines the foundational BaseTool class that all tools inherit from.
This is part of the 98.4% harness infrastructure.
"""

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar, Callable, Awaitable, Set, Tuple

from pydantic import BaseModel, Field, field_validator

from core.sandbox.executor import SandboxExecutor, SandboxResult
from core.sandbox.permissions import PermissionSystem, get_permission_system
from core.aci.interface import ACIInterface, InMemoryACI
from configs.schemas import ToolConfig
from configs.settings import get_tool_config

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

T = TypeVar('T')

ToolID = str
ExecutionID = str


# =============================================================================
# Tool State
# =============================================================================

class ToolState(str, Enum):
    """Lifecycle states for a tool."""
    
    UNINITIALIZED = "uninitialized"
    READY = "ready"              # Tool is ready for use
    BUSY = "busy"                # Tool is currently executing
    ERROR = "error"              # Tool encountered an error
    DISABLED = "disabled"        # Tool is administratively disabled


class ToolStatus(BaseModel):
    """Current status of a tool."""
    
    state: ToolState = Field(..., description="Current tool state")
    message: str = Field(default="", description="Status message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Last state change")
    execution_count: int = Field(default=0, description="Total executions")
    error_count: int = Field(default=0, description="Total errors")
    last_execution: Optional[datetime] = Field(default=None, description="Last execution time")
    last_error: Optional[str] = Field(default=None, description="Last error message")


# =============================================================================
# Tool Security Levels
# =============================================================================

class ToolSecurityLevel(str, Enum):
    """Security classification for tools."""
    
    SAFE = "safe"           # No significant risks (e.g., read-only operations)
    STANDARD = "standard"   # Standard tools with typical risks (e.g., file I/O)
    DANGEROUS = "dangerous" # Tools that can cause damage (e.g., shell commands, network)
    RESTRICTED = "restricted" # Tools requiring special permissions


class ExecutionMode(str, Enum):
    """Execution modes for tools."""
    
    SYNC = "sync"           # Synchronous execution (blocking)
    ASYNC = "async"         # Asynchronous execution (non-blocking)
    SANDBOXED = "sandboxed" # Execution in isolated sandbox
    NATIVE = "native"       # Native execution (no isolation)


# =============================================================================
# Tool Result
# =============================================================================

@dataclass
class ToolResult:
    """Result of a tool execution."""
    
    execution_id: ExecutionID
    tool_name: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    duration_seconds: float = 0.0
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime = field(default_factory=datetime.utcnow)
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.end_time < self.start_time:
            self.end_time = datetime.utcnow()
        self.duration_seconds = (self.end_time - self.start_time).total_seconds()


@dataclass
class ToolExecutionContext:
    """Context for a tool execution."""
    
    execution_id: ExecutionID
    tool_name: str
    args: Tuple = field(default_factory=tuple)
    kwargs: Dict = field(default_factory=dict)
    caller: Optional[str] = None  # Name of the calling agent
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Tool Metadata
# =============================================================================

@dataclass
class ToolMetadata:
    """Metadata about a tool."""
    
    name: str
    description: str
    version: str = "1.0"
    author: str = "Harness Framework"
    category: str = "general"
    security_level: ToolSecurityLevel = ToolSecurityLevel.STANDARD
    execution_mode: ExecutionMode = ExecutionMode.ASYNC
    requires_approval: bool = False
    timeout: float = 60.0
    max_retries: int = 2
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)


# =============================================================================
# Input Validation & Sanitization
# =============================================================================

class InputValidator:
    """Validates and sanitizes tool inputs."""
    
    @staticmethod
    def validate_string(value: Any, max_length: int = 10000) -> str:
        """Validate and sanitize a string input."""
        if not isinstance(value, str):
            raise ValueError(f"Expected string, got {type(value).__name__}")
        if len(value) > max_length:
            raise ValueError(f"String too long: {len(value)} > {max_length}")
        return value
    
    @staticmethod
    def validate_list(value: Any, max_items: int = 1000) -> List:
        """Validate a list input."""
        if not isinstance(value, list):
            raise ValueError(f"Expected list, got {type(value).__name__}")
        if len(value) > max_items:
            raise ValueError(f"List too long: {len(value)} > {max_items}")
        return value
    
    @staticmethod
    def validate_dict(value: Any, max_depth: int = 5) -> Dict:
        """Validate a dict input."""
        if not isinstance(value, dict):
            raise ValueError(f"Expected dict, got {type(value).__name__}")
        return value
    
    @staticmethod
    def validate_path(path: str, allowed_paths: Optional[List[str]] = None) -> str:
        """Validate a filesystem path."""
        import os
        from pathlib import Path
        
        # Normalize path
        path = os.path.normpath(path)
        
        # Check for path traversal
        if ".." in path or path.startswith("/"):
            # Check against allowed paths
            if allowed_paths:
                resolved = os.path.abspath(path)
                for allowed in allowed_paths:
                    allowed_abs = os.path.abspath(allowed)
                    if resolved.startswith(allowed_abs):
                        return path
                raise ValueError(f"Path not in allowed directories: {path}")
            else:
                raise ValueError(f"Path traversal detected: {path}")
        
        return path
    
    @staticmethod
    def sanitize_command(command: str) -> str:
        """Sanitize a shell command."""
        import re
        
        # Remove dangerous patterns
        dangerous = [
            r'\$\(',
            r'`',
            r';',
            r'\|',
            r'&&',
            r'\|\|',
            r'>',
            r'<',
            r'\brm\b',
            r'\bdd\b',
            r'\bmv\b',
            r'\bcp\b',
            r'\bchmod\b',
            r'\bsudo\b',
        ]
        
        for pattern in dangerous:
            if re.search(pattern, command):
                raise ValueError(f"Dangerous pattern detected in command: {pattern}")
        
        return command


# =============================================================================
# Base Tool Class
# =============================================================================

class BaseTool(ABC):
    """
    Abstract base class for all tools in the Harness Agentic Framework.
    
    Tools are used by agents to perform specific operations like:
    - File I/O
    - Shell commands
    - Code execution
    - Git operations
    - Network requests
    
    All tools inherit from this class and implement the `execute` method.
    
    Example:
        >>> class MyTool(BaseTool):
        ...     async def execute(self, *args, **kwargs) -> Any:
        ...         return "Result"
        ...
        >>> tool = MyTool(name="MyTool")
        >>> result = await tool.execute("arg1", key="value")
    """
    
    # Class-level defaults
    DEFAULT_TIMEOUT = 60.0
    DEFAULT_RETRIES = 2
    
    def __init__(
        self,
        name: str,
        config: Optional[ToolConfig] = None,
        sandbox: Optional[SandboxExecutor] = None,
        aci: Optional[ACIInterface] = None,
        metadata: Optional[ToolMetadata] = None,
    ):
        """
        Initialize the base tool.
        
        Args:
            name: Tool name (must be unique)
            config: Tool configuration (from configs.schemas)
            sandbox: Sandbox executor for safe code execution
            aci: ACI interface for communication
            metadata: Tool metadata
        """
        # Unique identifiers
        self._tool_id: ToolID = str(uuid.uuid4())
        self._name: str = name
        
        # Configuration
        if config is None:
            try:
                config = get_tool_config(name.lower())
            except (ValueError, Exception):
                from configs.schemas import ToolConfig
                config = ToolConfig(
                    name=name,
                    description=f"Tool: {name}",
                    enabled=True
                )
        self._config: ToolConfig = config
        
        # Metadata
        if metadata is None:
            metadata = ToolMetadata(
                name=name,
                description=config.description or f"Tool: {name}",
                security_level=self._infer_security_level(name),
            )
        self._metadata: ToolMetadata = metadata
        
        # Sandbox
        if sandbox is None:
            from core.sandbox.executor import SandboxExecutor
            sandbox = SandboxExecutor()
        self._sandbox: SandboxExecutor = sandbox
        
        # ACI
        if aci is None:
            aci = InMemoryACI(name=f"{name}-Tool-ACI")
        self._aci: ACIInterface = aci
        
        # Permission system
        self._permissions = get_permission_system()
        
        # State
        self._state: ToolState = ToolState.UNINITIALIZED
        self._status: ToolStatus = ToolStatus(
            state=ToolState.UNINITIALIZED,
            message="Tool created, not yet initialized"
        )
        
        # Execution tracking
        self._execution_count: int = 0
        self._error_count: int = 0
        self._active_executions: Dict[ExecutionID, ToolExecutionContext] = {}
        self._execution_lock: asyncio.Lock = asyncio.Lock()
        
        # Monitoring
        self._metrics_collector = get_metrics_collector()
        self._tracer = get_tracer()
        
        # Validator
        self._validator = InputValidator()
        
        # Record creation
        increment_metric("tools.created", labels={"tool": name})
    
    # =========================================================================
    # Properties
    # =========================================================================
    
    @property
    def tool_id(self) -> ToolID:
        """Get the unique tool identifier."""
        return self._tool_id
    
    @property
    def name(self) -> str:
        """Get the tool name."""
        return self._name
    
    @property
    def description(self) -> str:
        """Get the tool description."""
        return self._metadata.description or self._config.description or f"Tool: {self._name}"
    
    @property
    def config(self) -> ToolConfig:
        """Get the tool configuration."""
        return self._config
    
    @property
    def metadata(self) -> ToolMetadata:
        """Get the tool metadata."""
        return self._metadata
    
    @property
    def sandbox(self) -> SandboxExecutor:
        """Get the sandbox executor."""
        return self._sandbox
    
    @property
    def aci(self) -> ACIInterface:
        """Get the ACI interface."""
        return self._aci
    
    @property
    def state(self) -> ToolState:
        """Get the current tool state."""
        return self._state
    
    @property
    def status(self) -> ToolStatus:
        """Get the current tool status."""
        return self._status
    
    @property
    def execution_count(self) -> int:
        """Get the total number of executions."""
        return self._execution_count
    
    @property
    def error_count(self) -> int:
        """Get the total number of errors."""
        return self._error_count
    
    @property
    def is_enabled(self) -> bool:
        """Check if the tool is enabled."""
        return self._config.enabled and self._state != ToolState.DISABLED
    
    @property
    def is_available(self) -> bool:
        """Check if the tool is available for use."""
        return self.is_enabled and self._state == ToolState.READY
    
    @property
    def requires_approval(self) -> bool:
        """Check if the tool requires approval for use."""
        return self._metadata.requires_approval or self._config.requires_approval
    
    @property
    def security_level(self) -> ToolSecurityLevel:
        """Get the tool's security level."""
        return self._metadata.security_level
    
    # =========================================================================
    # Lifecycle Methods
    # =========================================================================
    
    async def initialize(self) -> None:
        """
        Initialize the tool.
        
        This method should be called before the tool can be used.
        It sets up the tool's resources and transitions to the READY state.
        """
        if self._state != ToolState.UNINITIALIZED:
            raise ToolError(f"Cannot initialize tool in state: {self._state}")
        
        self._set_state(ToolState.READY, "Tool initialized and ready")
        
        try:
            # Call the abstract initialization method
            await self._do_initialize()
            
            increment_metric("tools.initialized", labels={"tool": self.name})
            
        except Exception as e:
            self._set_state(ToolState.ERROR, f"Initialization failed: {e}")
            raise ToolError(f"Failed to initialize tool {self.name}: {e}") from e
    
    async def shutdown(self) -> None:
        """
        Shutdown the tool gracefully.
        """
        if self._state == ToolState.SHUTDOWN:
            return  # Already shut down
        
        self._set_state(ToolState.DISABLED, "Shutting down...")
        
        try:
            # Wait for active executions
            await self._wait_for_executions()
            
            # Call the abstract shutdown method
            await self._do_shutdown()
            
            self._set_state(ToolState.DISABLED, "Tool shut down")
            
        except Exception as e:
            self._set_state(ToolState.ERROR, f"Shutdown failed: {e}")
            raise ToolError(f"Failed to shutdown tool {self.name}: {e}") from e
    
    async def enable(self) -> None:
        """Enable the tool."""
        self._config.enabled = True
        self._set_state(ToolState.READY, "Tool enabled")
    
    async def disable(self) -> None:
        """Disable the tool."""
        self._config.enabled = False
        self._set_state(ToolState.DISABLED, "Tool disabled")
    
    # =========================================================================
    # Abstract Lifecycle Methods
    # =========================================================================
    
    @abstractmethod
    async def _do_initialize(self) -> None:
        """
        Perform tool-specific initialization.
        
        Subclasses should override this method to perform custom initialization.
        """
        pass
    
    @abstractmethod
    async def _do_shutdown(self) -> None:
        """
        Perform tool-specific shutdown.
        
        Subclasses should override this method to perform custom cleanup.
        """
        pass
    
    # =========================================================================
    # Execution Methods
    # =========================================================================
    
    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        """
        Execute the tool.
        
        This is the main method that subclasses must implement.
        It contains the tool-specific logic for performing operations.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            The result of the tool execution
            
        Raises:
            ToolError: If the tool cannot complete the operation
        """
        pass
    
    async def safe_execute(
        self,
        *args,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        validate: bool = True,
        caller: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """
        Execute the tool safely with validation, retries, and error handling.
        
        This is the recommended way to execute tools as it provides:
        - Input validation and sanitization
        - Timeout handling
        - Retry logic
        - Error tracking
        - Monitoring
        
        Args:
            *args: Positional arguments
            timeout: Execution timeout (defaults to config)
            max_retries: Maximum retry attempts (defaults to config)
            validate: Whether to validate inputs
            caller: Name of the calling agent
            **kwargs: Keyword arguments
            
        Returns:
            ToolResult with execution details
            
        Raises:
            ToolError: If execution fails after all retries
        """
        if not self.is_available:
            raise ToolError(f"Tool {self.name} is not available")
        
        # Generate execution ID
        execution_id = str(uuid.uuid4())
        
        # Create execution context
        context = ToolExecutionContext(
            execution_id=execution_id,
            tool_name=self.name,
            args=args,
            kwargs=kwargs,
            caller=caller,
            correlation_id=kwargs.pop('correlation_id', None),
            metadata=kwargs.pop('metadata', {}),
        )
        
        # Track execution
        self._active_executions[execution_id] = context
        
        # Validate inputs
        if validate:
            await self._validate_inputs(*args, **kwargs)
        
        # Setup timeout and retries
        timeout = timeout or self._config.timeout or self.DEFAULT_TIMEOUT
        max_retries = max_retries or self._config.max_retries or self.DEFAULT_RETRIES
        
        try:
            async with start_span(
                f"{self.name}.execute",
                {
                    "execution_id": execution_id,
                    "caller": caller,
                    "args_count": len(args),
                    "kwargs_count": len(kwargs)
                }
            ):
                result = await self._execute_with_retries(
                    execution_id, context, args, kwargs, timeout, max_retries
                )
                
                # Record success
                self._execution_count += 1
                self._status.last_execution = datetime.utcnow()
                
                tool_result = ToolResult(
                    execution_id=execution_id,
                    tool_name=self.name,
                    success=True,
                    output=result,
                    start_time=context.metadata.get('start_time', datetime.utcnow()),
                    end_time=datetime.utcnow(),
                )
                
                increment_metric("tools.executed", labels={
                    "tool": self.name,
                    "status": "success",
                    "caller": caller or "unknown"
                })
                
                return tool_result
        
        except ToolError as e:
            # Record error
            self._error_count += 1
            self._status.last_error = str(e)
            
            increment_metric("tools.executed", labels={
                "tool": self.name,
                "status": "failed",
                "caller": caller or "unknown"
            })
            
            raise
        
        finally:
            # Clean up
            self._active_executions.pop(execution_id, None)
    
    async def _execute_with_retries(
        self,
        execution_id: ExecutionID,
        context: ToolExecutionContext,
        args: Tuple,
        kwargs: Dict,
        timeout: float,
        max_retries: int,
        retry_count: int = 0
    ) -> Any:
        """Execute with retry logic."""
        try:
            return await asyncio.wait_for(
                self.execute(*args, **kwargs),
                timeout=timeout
            )
        
        except asyncio.TimeoutError:
            if retry_count < max_retries:
                await asyncio.sleep(self._config.retry_delay or 1.0)
                return await self._execute_with_retries(
                    execution_id, context, args, kwargs, timeout, max_retries, retry_count + 1
                )
            else:
                raise ToolError(f"Execution timed out after {timeout}s (retries: {retry_count})")
        
        except ToolError:
            raise
        
        except Exception as e:
            if retry_count < max_retries:
                await asyncio.sleep(self._config.retry_delay or 1.0)
                return await self._execute_with_retries(
                    execution_id, context, args, kwargs, timeout, max_retries, retry_count + 1
                )
            else:
                raise ToolError(f"Execution failed: {e}") from e
    
    async def _validate_inputs(self, *args, **kwargs) -> None:
        """Validate and sanitize inputs before execution."""
        # Default implementation does basic validation
        # Subclasses can override for tool-specific validation
        
        # Check for dangerous patterns in string arguments
        for arg in args:
            if isinstance(arg, str):
                self._validator.validate_string(arg)
        
        for value in kwargs.values():
            if isinstance(value, str):
                self._validator.validate_string(value)
    
    async def _wait_for_executions(self) -> None:
        """Wait for all active executions to complete."""
        while len(self._active_executions) > 0:
            await asyncio.sleep(0.1)
    
    # =========================================================================
    # State Management
    # =========================================================================
    
    def _set_state(self, state: ToolState, message: str = "") -> None:
        """Update the tool state."""
        old_state = self._state
        self._state = state
        self._status = ToolStatus(
            state=state,
            message=message,
            timestamp=datetime.utcnow(),
            execution_count=self._execution_count,
            error_count=self._error_count,
            last_execution=self._status.last_execution,
            last_error=self._status.last_error,
        )
        
        # Update metrics
        if old_state != state:
            increment_metric("tools.state_changes", labels={
                "tool": self.name,
                "from": old_state.value,
                "to": state.value
            })
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def _infer_security_level(self, tool_name: str) -> ToolSecurityLevel:
        """Infer security level from tool name."""
        dangerous_tools = [
            "shell", "bash", "sh", "cmd", "command",
            "exec", "execute", "run", "spawn",
            "network", "http", "request", "curl", "wget",
            "git", "svn", "hg",
            "file", "fs", "io",
        ]
        
        for dangerous in dangerous_tools:
            if dangerous in tool_name.lower():
                return ToolSecurityLevel.DANGEROUS
        
        return ToolSecurityLevel.STANDARD
    
    def log(self, message: str, level: str = "INFO") -> None:
        """Log a message with tool context."""
        import logging
        logger = logging.getLogger(f"harness.tools.{self.name}")
        getattr(logger, level.lower(), logger.info)(f"[{self.state.value}] {message}")
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, state={self.state.value!r})"


# =============================================================================
# Sandboxed Tool Base Class
# =============================================================================

class SandboxedTool(BaseTool):
    """
    Base class for tools that execute code in a sandbox.
    
    This provides built-in sandbox integration for tools that need
    to execute untrusted code safely.
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[ToolConfig] = None,
        sandbox: Optional[SandboxExecutor] = None,
        aci: Optional[ACIInterface] = None,
        metadata: Optional[ToolMetadata] = None,
    ):
        # Set execution mode to sandboxed
        if metadata is None:
            metadata = ToolMetadata(
                name=name,
                description="",
                execution_mode=ExecutionMode.SANDBOXED,
            )
        else:
            metadata.execution_mode = ExecutionMode.SANDBOXED
        
        super().__init__(name, config, sandbox, aci, metadata)
    
    async def execute_in_sandbox(
        self,
        code: str,
        language: str = "python",
        timeout: Optional[float] = None,
        **kwargs
    ) -> SandboxResult:
        """
        Execute code in the sandbox.
        
        Args:
            code: Code to execute
            language: Programming language
            timeout: Execution timeout
            **kwargs: Additional sandbox parameters
            
        Returns:
            SandboxResult with execution details
        """
        timeout = timeout or self._config.timeout or self.DEFAULT_TIMEOUT
        
        return await self._sandbox.execute(
            code=code,
            language=language,
            timeout=timeout,
            **kwargs
        )
    
    async def _validate_inputs(self, *args, **kwargs) -> None:
        """Validate inputs for sandboxed execution."""
        # Check for blocked patterns
        import re
        
        blocked_patterns = [
            r'__import__',
            r'open\s*\(\s*["\']',
            r'os\.',
            r'sys\.',
            r'subprocess\.',
            r'socket\.',
            r'requests\.',
            r'boto3\.',
        ]
        
        for arg in args:
            if isinstance(arg, str):
                for pattern in blocked_patterns:
                    if re.search(pattern, arg):
                        raise ToolError(f"Blocked pattern detected: {pattern}")
        
        for value in kwargs.values():
            if isinstance(value, str):
                for pattern in blocked_patterns:
                    if re.search(pattern, value):
                        raise ToolError(f"Blocked pattern detected: {pattern}")


# =============================================================================
# Exceptions
# =============================================================================

class ToolError(Exception):
    """Base exception for tool-related errors."""
    
    def __init__(self, message: str, code: Optional[str] = None, details: Optional[Dict] = None):
        super().__init__(message)
        self.message = message
        self.code = code or "TOOL_ERROR"
        self.details = details or {}


class ExecutionError(ToolError):
    """Exception for execution errors."""
    
    def __init__(self, message: str, execution_id: Optional[str] = None, details: Optional[Dict] = None):
        super().__init__(message, code="EXECUTION_ERROR", details=details)
        self.execution_id = execution_id


class ValidationError(ToolError):
    """Exception for input validation errors."""
    
    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict] = None):
        super().__init__(message, code="VALIDATION_ERROR", details=details)
        self.field = field


class PermissionError(ToolError):
    """Exception for permission errors."""
    
    def __init__(self, message: str, tool_name: Optional[str] = None, details: Optional[Dict] = None):
        super().__init__(message, code="PERMISSION_ERROR", details=details)
        self.tool_name = tool_name


class TimeoutError(ToolError):
    """Exception for timeout errors."""
    
    def __init__(self, message: str, timeout: float = 0, details: Optional[Dict] = None):
        super().__init__(message, code="TIMEOUT_ERROR", details=details)
        self.timeout = timeout


# =============================================================================
# Tool Config for Pydantic compatibility
# =============================================================================

class ToolConfigModel(BaseModel):
    """Pydantic-compatible tool configuration."""
    
    name: str = Field(..., description="Tool name")
    description: str = Field(default="", description="Tool description")
    enabled: bool = Field(default=True, description="Whether tool is enabled")
    timeout: float = Field(default=60.0, ge=0.1, le=600.0, description="Execution timeout")
    max_retries: int = Field(default=2, ge=0, le=10, description="Max retry attempts")
    retry_delay: float = Field(default=1.0, ge=0.1, le=60.0, description="Delay between retries")
    requires_approval: bool = Field(default=False, description="Require approval for use")
