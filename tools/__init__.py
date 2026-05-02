"""
Tools Module.

Contains all tool implementations for the Harness Agentic Framework.
This includes:
- Base tool classes
- Tool registry
- Concrete tool implementations (Shell, Python, Git, FileIO, etc.)
"""

# Import base classes
from .base import (
    BaseTool,
    SandboxedTool,
    ToolError,
    ExecutionError,
    ValidationError,
    PermissionError,
    TimeoutError,
    ToolConfigModel,
    ToolID,
    ExecutionID,
    ToolState,
    ToolSecurityLevel,
    ExecutionMode,
    ToolStatus,
    ToolResult,
    ToolExecutionContext,
    ToolMetadata,
    InputValidator,
)

# Import registry
from .registry import (
    ToolRegistry,
    get_tool_registry,
    reset_tool_registry,
    register_tool,
    unregister_tool,
    get_tool,
    use_tool,
    ToolRegistryError,
    ToolNotFoundError,
    ToolAlreadyRegisteredError,
)

__all__ = [
    # Base classes
    "BaseTool",
    "SandboxedTool",
    # Exceptions
    "ToolError",
    "ExecutionError",
    "ValidationError",
    "PermissionError",
    "TimeoutError",
    "ToolRegistryError",
    "ToolNotFoundError",
    "ToolAlreadyRegisteredError",
    # Pydantic models
    "ToolConfigModel",
    # Type definitions
    "ToolID",
    "ExecutionID",
    # Enums
    "ToolState",
    "ToolSecurityLevel",
    "ExecutionMode",
    # Data classes
    "ToolStatus",
    "ToolResult",
    "ToolExecutionContext",
    "ToolMetadata",
    # Validators
    "InputValidator",
    # Registry
    "ToolRegistry",
    "get_tool_registry",
    "reset_tool_registry",
    "register_tool",
    "unregister_tool",
    "get_tool",
    "use_tool",
]
