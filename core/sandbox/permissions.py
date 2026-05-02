"""
Permissions Module.

Provides a role-based permission system for controlling access to resources.
This is a critical security component (Part of the 98.4% harness infrastructure).
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from functools import wraps
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Set, TypeVar, Union

from configs.settings import get_config


# =============================================================================
# Type Definitions
# =============================================================================

T = TypeVar('T')


class Action(str, Enum):
    """Permission actions."""
    
    READ = auto()
    WRITE = auto()
    EXECUTE = auto()
    CREATE = auto()
    DELETE = auto()
    LIST = auto()
    UPDATE = auto()
    MANAGE = auto()  # Full control
    
    @classmethod
    def from_string(cls, action: str) -> 'Action':
        """Convert string to Action enum."""
        return cls[action.upper()]
    
    def __str__(self) -> str:
        return self.name.lower()


class Resource(str, Enum):
    """Resource types that can be protected by permissions."""
    
    # System resources
    SYSTEM = "system"
    CONFIG = "config"
    SETTINGS = "settings"
    
    # Agent resources
    AGENT = "agent"
    AGENT_GOD = "agent:god"
    AGENT_PLANNER = "agent:planner"
    AGENT_CODER = "agent:coder"
    AGENT_REVIEWER = "agent:reviewer"
    AGENT_TESTER = "agent:tester"
    AGENT_DEBUGGER = "agent:debugger"
    AGENT_RESEARCHER = "agent:researcher"
    AGENT_DOCUMENTER = "agent:documenter"
    AGENT_ALL = "agent:*"
    
    # Tool resources
    TOOL = "tool"
    TOOL_SHELL = "tool:shell"
    TOOL_PYTHON = "tool:python"
    TOOL_GIT = "tool:git"
    TOOL_FILE_IO = "tool:file_io"
    TOOL_TEST_RUNNER = "tool:test_runner"
    TOOL_LINTER = "tool:linter"
    TOOL_ALL = "tool:*"
    
    # File system resources
    FILESYSTEM = "filesystem"
    FILE_READ = "filesystem:read"
    FILE_WRITE = "filesystem:write"
    FILE_DELETE = "filesystem:delete"
    FILE_ALL = "filesystem:*"
    
    # Network resources
    NETWORK = "network"
    NETWORK_HTTP = "network:http"
    NETWORK_SOCKET = "network:socket"
    NETWORK_ALL = "network:*"
    
    # Process resources
    PROCESS = "process"
    PROCESS_CREATE = "process:create"
    PROCESS_KILL = "process:kill"
    PROCESS_ALL = "process:*"
    
    # Workflow resources
    WORKFLOW = "workflow"
    WORKFLOW_CREATE = "workflow:create"
    WORKFLOW_EXECUTE = "workflow:execute"
    WORKFLOW_DELETE = "workflow:delete"
    WORKFLOW_ALL = "workflow:*"
    
    # General wildcard
    ALL = "*"
    
    @classmethod
    def from_string(cls, resource: str) -> 'Resource':
        """Convert string to Resource enum."""
        try:
            return cls[resource.upper()]
        except KeyError:
            # Handle custom resources
            return cls(resource)
    
    def matches(self, other: 'Resource') -> bool:
        """Check if this resource matches another (supports wildcards)."""
        if self == other:
            return True
        if self == Resource.ALL or other == Resource.ALL:
            return True
        if self.name.endswith(':*') and other.name.startswith(self.name[:-2] + ':'):
            return True
        if other.name.endswith(':*') and self.name.startswith(other.name[:-2] + ':'):
            return True
        return False


class Role(str, Enum):
    """Predefined roles with common permission sets."""
    
    # System roles
    ADMIN = "admin"          # Full access to everything
    SUPERUSER = "superuser"  # Most access, except some system operations
    
    # Agent roles
    GOD = "god"              # God Agent role
    PLANNER = "planner"      # Planner Agent role
    CODER = "coder"          # Coder Agent role
    REVIEWER = "reviewer"    # Reviewer Agent role
    TESTER = "tester"        # Tester Agent role
    DEBUGGER = "debugger"    # Debugger Agent role
    RESEARCHER = "researcher"  # Researcher Agent role
    DOCUMENTER = "documenter"  # Documenter Agent role
    
    # Specialized roles
    TOOL_USER = "tool_user"  # Can use tools
    READ_ONLY = "read_only"  # Can only read, not modify
    GUEST = "guest"          # Minimal permissions
    
    # Anonymous
    ANONYMOUS = "anonymous"  # No permissions by default
    
    @classmethod
    def from_string(cls, role: str) -> 'Role':
        """Convert string to Role enum."""
        try:
            return cls[role.lower()]
        except KeyError:
            # Custom role
            return cls(role.lower())


# =============================================================================
# Permission Definition
# =============================================================================

@dataclass(frozen=True)
class Permission:
    """A permission granted to a role or user."""
    
    action: Action
    resource: Resource
    
    def matches(self, action: Action, resource: Resource) -> bool:
        """Check if this permission matches the given action and resource."""
        if self.action != Action.MANAGE and action == Action.MANAGE:
            return False
        if self.resource != Resource.ALL and not self.resource.matches(resource):
            return False
        if self.action != Action.ALL and self.action != action:
            # If this permission is MANAGE, it covers all actions
            if self.action != Action.MANAGE:
                return False
        return True
    
    def __str__(self) -> str:
        return f"{self.action}:{self.resource}"
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary."""
        return {
            "action": str(self.action),
            "resource": str(self.resource),
        }
    
    @classmethod
    def from_string(cls, permission_str: str) -> 'Permission':
        """Create a Permission from a string like 'read:filesystem'."""
        parts = permission_str.split(':')
        if len(parts) != 2:
            raise ValueError(f"Invalid permission format: {permission_str}")
        
        try:
            action = Action[parts[0].upper()]
        except KeyError:
            action = Action.READ  # Default to read
        
        resource = Resource.from_string(parts[1])
        
        return cls(action=action, resource=resource)


# =============================================================================
# Permission System
# =============================================================================

class PermissionDeniedError(Exception):
    """Raised when a permission check fails."""
    
    def __init__(self, action: Action, resource: Resource, role: Optional[str] = None):
        self.action = action
        self.resource = resource
        self.role = role
        message = f"Permission denied: {action} on {resource}"
        if role:
            message += f" for role '{role}'"
        super().__init__(message)


@dataclass
class PermissionCheck:
    """Result of a permission check."""
    
    allowed: bool
    permission: Optional[Permission] = None
    matching_permissions: List[Permission] = field(default_factory=list)
    
    def __bool__(self) -> bool:
        return self.allowed


class PermissionSystem:
    """
    Role-Based Access Control (RBAC) system for managing permissions.
    
    This system provides:
    - Role-based permission management
    - Hierarchical role inheritance
    - Fine-grained resource permissions
    - Permission caching for performance
    """
    
    # Default permissions for predefined roles
    DEFAULT_ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
        Role.ADMIN: {
            Permission(Action.MANAGE, Resource.ALL),
        },
        Role.SUPERUSER: {
            Permission(Action.MANAGE, Resource.AGENT_ALL),
            Permission(Action.MANAGE, Resource.TOOL_ALL),
            Permission(Action.MANAGE, Resource.WORKFLOW_ALL),
            Permission(Action.MANAGE, Resource.FILESYSTEM),
            Permission(Action.READ, Resource.SYSTEM),
        },
        Role.GOD: {
            Permission(Action.MANAGE, Resource.AGENT_ALL),
            Permission(Action.EXECUTE, Resource.TOOL_ALL),
            Permission(Action.MANAGE, Resource.WORKFLOW_ALL),
            Permission(Action.READ, Resource.FILESYSTEM),
            Permission(Action.WRITE, Resource.FILESYSTEM),
            Permission(Action.CREATE, Resource.AGENT),
        },
        Role.PLANNER: {
            Permission(Action.READ, Resource.AGENT_GOD),
            Permission(Action.EXECUTE, Resource.TOOL_PYTHON),
            Permission(Action.READ, Resource.FILESYSTEM),
        },
        Role.CODER: {
            Permission(Action.READ, Resource.AGENT_GOD),
            Permission(Action.EXECUTE, Resource.TOOL_PYTHON),
            Permission(Action.EXECUTE, Resource.TOOL_FILE_IO),
            Permission(Action.EXECUTE, Resource.TOOL_GIT),
            Permission(Action.READ, Resource.FILESYSTEM),
            Permission(Action.WRITE, Resource.FILESYSTEM),
        },
        Role.REVIEWER: {
            Permission(Action.READ, Resource.AGENT_GOD),
            Permission(Action.EXECUTE, Resource.TOOL_PYTHON),
            Permission(Action.EXECUTE, Resource.TOOL_LINTER),
            Permission(Action.READ, Resource.FILESYSTEM),
        },
        Role.TESTER: {
            Permission(Action.READ, Resource.AGENT_GOD),
            Permission(Action.EXECUTE, Resource.TOOL_PYTHON),
            Permission(Action.EXECUTE, Resource.TOOL_TEST_RUNNER),
            Permission(Action.READ, Resource.FILESYSTEM),
            Permission(Action.EXECUTE, Resource.PROCESS),
        },
        Role.DEBUGGER: {
            Permission(Action.READ, Resource.AGENT_GOD),
            Permission(Action.EXECUTE, Resource.TOOL_PYTHON),
            Permission(Action.EXECUTE, Resource.TOOL_SHELL),
            Permission(Action.READ, Resource.FILESYSTEM),
            Permission(Action.LIST, Resource.PROCESS),
        },
        Role.RESEARCHER: {
            Permission(Action.READ, Resource.AGENT_GOD),
            Permission(Action.EXECUTE, Resource.TOOL_PYTHON),
            Permission(Action.READ, Resource.FILESYSTEM),
            # Note: Network access might be needed for research
        },
        Role.DOCUMENTER: {
            Permission(Action.READ, Resource.AGENT_GOD),
            Permission(Action.EXECUTE, Resource.TOOL_PYTHON),
            Permission(Action.READ, Resource.FILESYSTEM),
            Permission(Action.WRITE, Resource.FILESYSTEM),
        },
        Role.TOOL_USER: {
            Permission(Action.EXECUTE, Resource.TOOL_ALL),
            Permission(Action.READ, Resource.FILESYSTEM),
        },
        Role.READ_ONLY: {
            Permission(Action.READ, Resource.ALL),
            Permission(Action.LIST, Resource.ALL),
        },
        Role.GUEST: {
            Permission(Action.READ, Resource.AGENT_GOD),
        },
        Role.ANONYMOUS: set(),
    }
    
    # Role hierarchy (higher roles inherit permissions from lower roles)
    ROLE_HIERARCHY: List[Role] = [
        Role.ANONYMOUS,
        Role.GUEST,
        Role.READ_ONLY,
        Role.TOOL_USER,
        Role.DOCUMENTER,
        Role.RESEARCHER,
        Role.REVIEWER,
        Role.TESTER,
        Role.DEBUGGER,
        Role.PLANNER,
        Role.CODER,
        Role.GOD,
        Role.SUPERUSER,
        Role.ADMIN,
    ]
    
    def __init__(self):
        """Initialize the permission system."""
        self._role_permissions: Dict[str, Set[Permission]] = {}
        self._user_permissions: Dict[str, Set[Permission]] = {}
        self._user_roles: Dict[str, Set[Role]] = {}
        
        # Initialize default roles
        for role, permissions in self.DEFAULT_ROLE_PERMISSIONS.items():
            self._role_permissions[role.value] = permissions
    
    def get_permissions_for_role(self, role: Union[Role, str]) -> Set[Permission]:
        """Get all permissions for a role, including inherited permissions."""
        if isinstance(role, Role):
            role = role.value
        
        permissions: Set[Permission] = set()
        role_obj = Role.from_string(role)
        
        # Get permissions for this role and all roles below it in hierarchy
        for candidate_role in self.ROLE_HIERARCHY:
            if candidate_role == role_obj:
                # Include this role and all below
                for r in self.ROLE_HIERARCHY[self.ROLE_HIERARCHY.index(candidate_role):]:
                    if r.value in self._role_permissions:
                        permissions.update(self._role_permissions[r.value])
                break
        
        return permissions
    
    def has_permission(
        self,
        role: Union[Role, str],
        action: Union[Action, str],
        resource: Union[Resource, str],
    ) -> PermissionCheck:
        """
        Check if a role has a specific permission.
        
        Args:
            role: Role to check
            action: Action to perform
            resource: Resource to access
            
        Returns:
            PermissionCheck: Result with details
        """
        if isinstance(role, Role):
            role = role.value
        if isinstance(action, Action):
            action = action
        else:
            action = Action.from_string(action)
        if isinstance(resource, Resource):
            resource = resource
        else:
            resource = Resource.from_string(resource)
        
        permissions = self.get_permissions_for_role(role)
        
        # Find matching permissions
        matching = []
        for perm in permissions:
            if perm.matches(action, resource):
                matching.append(perm)
        
        allowed = len(matching) > 0
        
        return PermissionCheck(
            allowed=allowed,
            permission=matching[0] if matching else None,
            matching_permissions=matching,
        )
    
    def check_permission(
        self,
        role: Union[Role, str],
        action: Union[Action, str],
        resource: Union[Resource, str],
    ) -> None:
        """
        Check permission and raise exception if denied.
        
        Args:
            role: Role to check
            action: Action to perform
            resource: Resource to access
            
        Raises:
            PermissionDeniedError: If permission is denied
        """
        check = self.has_permission(role, action, resource)
        if not check.allowed:
            raise PermissionDeniedError(
                action=Action.from_string(action) if isinstance(action, str) else action,
                resource=Resource.from_string(resource) if isinstance(resource, str) else resource,
                role=role,
            )
    
    def grant_permission_to_role(
        self,
        role: Union[Role, str],
        action: Union[Action, str],
        resource: Union[Resource, str],
    ) -> None:
        """
        Grant a permission to a role.
        
        Args:
            role: Role to grant permission to
            action: Action to allow
            resource: Resource to allow access to
        """
        if isinstance(role, Role):
            role = role.value
        if isinstance(action, Action):
            action = action
        else:
            action = Action.from_string(action)
        if isinstance(resource, Resource):
            resource = resource
        else:
            resource = Resource.from_string(resource)
        
        if role not in self._role_permissions:
            self._role_permissions[role] = set()
        
        self._role_permissions[role].add(Permission(action=action, resource=resource))
    
    def revoke_permission_from_role(
        self,
        role: Union[Role, str],
        action: Union[Action, str],
        resource: Union[Resource, str],
    ) -> bool:
        """
        Revoke a permission from a role.
        
        Args:
            role: Role to revoke permission from
            action: Action to revoke
            resource: Resource to revoke access to
            
        Returns:
            bool: True if permission was revoked, False if not found
        """
        if isinstance(role, Role):
            role = role.value
        if isinstance(action, Action):
            action = action
        else:
            action = Action.from_string(action)
        if isinstance(resource, Resource):
            resource = resource
        else:
            resource = Resource.from_string(resource)
        
        if role in self._role_permissions:
            perm = Permission(action=action, resource=resource)
            if perm in self._role_permissions[role]:
                self._role_permissions[role].remove(perm)
                return True
        
        return False
    
    def grant_role_to_user(self, user_id: str, role: Union[Role, str]) -> None:
        """
        Grant a role to a user.
        
        Args:
            user_id: User identifier
            role: Role to grant
        """
        if isinstance(role, Role):
            role = role
        else:
            role = Role.from_string(role)
        
        if user_id not in self._user_roles:
            self._user_roles[user_id] = set()
        
        self._user_roles[user_id].add(role)
    
    def revoke_role_from_user(self, user_id: str, role: Union[Role, str]) -> bool:
        """
        Revoke a role from a user.
        
        Args:
            user_id: User identifier
            role: Role to revoke
            
        Returns:
            bool: True if role was revoked, False if not found
        """
        if isinstance(role, Role):
            role = role
        else:
            role = Role.from_string(role)
        
        if user_id in self._user_roles and role in self._user_roles[user_id]:
            self._user_roles[user_id].remove(role)
            if not self._user_roles[user_id]:
                del self._user_roles[user_id]
            return True
        
        return False
    
    def get_user_permissions(self, user_id: str) -> Set[Permission]:
        """
        Get all permissions for a user (from all assigned roles).
        
        Args:
            user_id: User identifier
            
        Returns:
            Set of all permissions the user has
        """
        permissions: Set[Permission] = set()
        
        if user_id in self._user_roles:
            for role in self._user_roles[user_id]:
                permissions.update(self.get_permissions_for_role(role))
        
        return permissions
    
    def has_user_permission(
        self,
        user_id: str,
        action: Union[Action, str],
        resource: Union[Resource, str],
    ) -> PermissionCheck:
        """
        Check if a user has a specific permission.
        
        Args:
            user_id: User identifier
            action: Action to perform
            resource: Resource to access
            
        Returns:
            PermissionCheck: Result with details
        """
        permissions = self.get_user_permissions(user_id)
        
        if isinstance(action, str):
            action = Action.from_string(action)
        if isinstance(resource, str):
            resource = Resource.from_string(resource)
        
        # Find matching permissions
        matching = []
        for perm in permissions:
            if perm.matches(action, resource):
                matching.append(perm)
        
        allowed = len(matching) > 0
        
        return PermissionCheck(
            allowed=allowed,
            permission=matching[0] if matching else None,
            matching_permissions=matching,
        )


# =============================================================================
# Permission Decorators
# =============================================================================

def require_permission(
    action: Union[Action, str],
    resource: Union[Resource, str],
    role: Optional[Union[Role, str]] = None,
):
    """
    Decorator to check permissions before executing a function.
    
    Args:
        action: Required action
        resource: Required resource
        role: Role to check (if None, uses 'user' from function kwargs)
        
    Example:
        @require_permission(Action.EXECUTE, Resource.TOOL_PYTHON)
        async def run_python_tool(...):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            permission_system = PermissionSystem()
            
            # Get role from kwargs or use default
            check_role = role
            if check_role is None and 'user' in kwargs:
                user_id = kwargs['user']
                check = permission_system.has_user_permission(user_id, action, resource)
            else:
                if check_role is None:
                    check_role = Role.ANONYMOUS
                check = permission_system.has_permission(check_role, action, resource)
            
            if not check.allowed:
                raise PermissionDeniedError(
                    action=Action.from_string(action) if isinstance(action, str) else action,
                    resource=Resource.from_string(resource) if isinstance(resource, str) else resource,
                    role=str(check_role) if check_role else None,
                )
            
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            permission_system = PermissionSystem()
            
            # Get role from kwargs or use default
            check_role = role
            if check_role is None and 'user' in kwargs:
                user_id = kwargs['user']
                check = permission_system.has_user_permission(user_id, action, resource)
            else:
                if check_role is None:
                    check_role = Role.ANONYMOUS
                check = permission_system.has_permission(check_role, action, resource)
            
            if not check.allowed:
                raise PermissionDeniedError(
                    action=Action.from_string(action) if isinstance(action, str) else action,
                    resource=Resource.from_string(resource) if isinstance(resource, str) else resource,
                    role=str(check_role) if check_role else None,
                )
            
            return func(*args, **kwargs)
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# =============================================================================
# Global Permission System Instance
# =============================================================================

permission_system = PermissionSystem()


# Convenience functions
def has_permission(role: Union[Role, str], action: Union[Action, str], resource: Union[Resource, str]) -> bool:
    """Check if a role has a permission (convenience function)."""
    return permission_system.has_permission(role, action, resource).allowed


def check_permission(role: Union[Role, str], action: Union[Action, str], resource: Union[Resource, str]) -> None:
    """Check permission and raise if denied (convenience function)."""
    permission_system.check_permission(role, action, resource)


# Import asyncio for decorator
import asyncio
import uuid
