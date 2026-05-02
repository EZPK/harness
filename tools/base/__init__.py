"""
Base Tool Module.

Exports the foundational classes for all tools in the Harness Agentic Framework.
"""

from .tool import (
    # Base classes
    BaseTool,
    SandboxedTool,
    
    # Type definitions
    ToolID,
    ExecutionID,
    
    # Enums
    ToolState,
    ToolSecurityLevel,
    ExecutionMode,
    
    # Data classes
    ToolStatus,
    ToolResult,
    ToolExecutionContext,
    ToolMetadata,
    
    # Validators
    InputValidator,
    
    # Exceptions
    ToolError,
    ExecutionError,
    ValidationError,
    PermissionError,
    TimeoutError,
    
    # Pydantic models
    ToolConfigModel,
)

__all__ = [
    # Base classes
    "BaseTool",
    "SandboxedTool",
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
    # Exceptions
    "ToolError",
    "ExecutionError",
    "ValidationError",
    "PermissionError",
    "TimeoutError",
    # Pydantic models
    "ToolConfigModel",
]
