"""
Sandboxing Module.

Provides secure execution environments for untrusted code and operations.
This is a critical security component (Part of the 98.4% harness infrastructure).
"""

from .executor import (
    SandboxExecutor,
    SandboxResult,
    ExecutionError,
    TimeoutError,
    MemoryLimitExceededError,
)
from .permissions import (
    PermissionSystem,
    Permission,
    PermissionDeniedError,
    Role,
    Action,
    Resource,
    get_permission_system,
)
from .isolation import (
    IsolationManager,
    IsolationMode,
    Namespace,
)

__all__ = [
    # Executor
    "SandboxExecutor",
    "SandboxResult",
    "ExecutionError",
    "TimeoutError",
    "MemoryLimitExceededError",
    # Permissions
    "PermissionSystem",
    "Permission",
    "PermissionDeniedError",
    "Role",
    "Action",
    "Resource",
    "get_permission_system",
    # Isolation
    "IsolationManager",
    "IsolationMode",
    "Namespace",
]
