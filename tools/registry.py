"""
Tool Registry Module.

Provides a centralized registry for managing and accessing tools.
This is a critical component of the harness infrastructure (98.4%).
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, Set, Callable, Awaitable, TypeVar

from pydantic import BaseModel, Field

from .base import BaseTool, ToolMetadata, ToolSecurityLevel
from core.aci.interface import ACIInterface, InMemoryACI
from core.sandbox.executor import SandboxExecutor
from configs.settings import get_tool_config

from core.monitoring import (
    get_metrics_collector,
    increment_metric,
)


T = TypeVar('T', bound=BaseTool)


# =============================================================================
# Tool Registry
# =============================================================================

class ToolRegistry:
    """
    Central registry for managing tools in the Harness Agentic Framework.
    
    The registry provides:
    - Tool registration and discovery
    - Tool factory functions
    - Tool lifecycle management
    - Tool access control
    - Tool metadata tracking
    
    Example:
        >>> registry = ToolRegistry()
        >>> registry.register(MyTool)
        >>> tool = registry.get("MyTool")
        >>> await tool.initialize()
        >>> result = await tool.execute("arg1", key="value")
    """
    
    def __init__(
        self,
        name: str = "Global",
        aci: Optional[ACIInterface] = None,
        sandbox: Optional[SandboxExecutor] = None,
    ):
        """
        Initialize the tool registry.
        
        Args:
            name: Registry name
            aci: ACI interface for communication
            sandbox: Sandbox executor for tool isolation
        """
        self._name = name
        self._aci = aci or InMemoryACI(f"{name}-ToolRegistry-ACI")
        self._sandbox = sandbox or SandboxExecutor()
        
        # Tool storage
        self._tools: Dict[str, BaseTool] = {}
        self._tool_classes: Dict[str, Type[BaseTool]] = {}
        self._tool_factories: Dict[str, Callable[..., BaseTool]] = {}
        
        # Metadata
        self._tool_metadata: Dict[str, ToolMetadata] = {}
        
        # State
        self._initialized: bool = False
        self._lock: asyncio.Lock = asyncio.Lock()
        
        # Event handlers
        self._on_register: List[Callable[[str, BaseTool], Awaitable[None]]] = []
        self._on_unregister: List[Callable[[str, BaseTool], Awaitable[None]]] = []
        
        # Monitoring
        self._metrics_collector = get_metrics_collector()
    
    # =========================================================================
    # Properties
    # =========================================================================
    
    @property
    def name(self) -> str:
        """Get the registry name."""
        return self._name
    
    @property
    def aci(self) -> ACIInterface:
        """Get the ACI interface."""
        return self._aci
    
    @property
    def sandbox(self) -> SandboxExecutor:
        """Get the sandbox executor."""
        return self._sandbox
    
    @property
    def tool_names(self) -> List[str]:
        """Get list of registered tool names."""
        return list(self._tools.keys())
    
    @property
    def tool_classes(self) -> Dict[str, Type[BaseTool]]:
        """Get registered tool classes."""
        return self._tool_classes.copy()
    
    @property
    def initialized(self) -> bool:
        """Check if registry is initialized."""
        return self._initialized
    
    # =========================================================================
    # Registration Methods
    # =========================================================================
    
    def register_class(self, tool_class: Type[BaseTool], name: Optional[str] = None) -> None:
        """
        Register a tool class.
        
        This allows the registry to create instances of the tool on demand.
        
        Args:
            tool_class: The tool class to register
            name: Optional name override (defaults to class name)
        """
        name = name or tool_class.__name__
        self._tool_classes[name] = tool_class
        increment_metric("tools.classes_registered", labels={"registry": self.name, "tool": name})
    
    def register_factory(
        self,
        name: str,
        factory: Callable[..., BaseTool]
    ) -> None:
        """
        Register a tool factory function.
        
        Args:
            name: Name for the tool
            factory: Factory function that creates tool instances
        """
        self._tool_factories[name] = factory
        increment_metric("tools.factories_registered", labels={"registry": self.name, "tool": name})
    
    async def register_instance(
        self,
        tool: BaseTool,
        name: Optional[str] = None,
        initialize: bool = True,
    ) -> BaseTool:
        """
        Register a tool instance.
        
        Args:
            tool: The tool instance to register
            name: Optional name override (defaults to tool name)
            initialize: Whether to initialize the tool
            
        Returns:
            The registered tool instance
        """
        name = name or tool.name
        
        async with self._lock:
            if name in self._tools:
                raise ToolRegistryError(f"Tool '{name}' already registered")
            
            self._tools[name] = tool
            
            # Store metadata
            self._tool_metadata[name] = tool.metadata
            
            # Initialize if requested
            if initialize and not tool.is_initialized:
                await tool.initialize()
            
            # Trigger event handlers
            for handler in self._on_register:
                await handler(name, tool)
            
            increment_metric("tools.instances_registered", labels={"registry": self.name, "tool": name})
        
        return tool
    
    async def register(
        self,
        tool_or_class: Type[BaseTool] | BaseTool,
        name: Optional[str] = None,
        initialize: bool = True,
        **kwargs
    ) -> BaseTool:
        """
        Register a tool (class or instance).
        
        This is the main registration method that handles both classes and instances.
        
        Args:
            tool_or_class: Tool class or instance to register
            name: Optional name override
            initialize: Whether to initialize the tool
            **kwargs: Arguments to pass to tool constructor (if class)
            
        Returns:
            The registered tool instance
        """
        if isinstance(tool_or_class, type) and issubclass(tool_or_class, BaseTool):
            # It's a class - create an instance
            name = name or tool_or_class.__name__
            tool_instance = tool_or_class(name=name, **kwargs)
            return await self.register_instance(tool_instance, name, initialize)
        elif isinstance(tool_or_class, BaseTool):
            # It's already an instance
            return await self.register_instance(tool_or_class, name, initialize)
        else:
            raise ToolRegistryError(f"Cannot register: {type(tool_or_class)}")
    
    async def unregister(self, name: str) -> bool:
        """
        Unregister a tool.
        
        Args:
            name: Name of the tool to unregister
            
        Returns:
            True if tool was unregistered, False if not found
        """
        async with self._lock:
            if name not in self._tools:
                return False
            
            tool = self._tools.pop(name)
            
            # Shutdown the tool
            try:
                await tool.shutdown()
            except Exception:
                pass  # Ignore shutdown errors during unregister
            
            # Remove metadata
            self._tool_metadata.pop(name, None)
            
            # Trigger event handlers
            for handler in self._on_unregister:
                await handler(name, tool)
            
            increment_metric("tools.unregistered", labels={"registry": self.name, "tool": name})
        
        return True
    
    async def unregister_all(self) -> int:
        """
        Unregister all tools.
        
        Returns:
            Number of tools unregistered
        """
        count = 0
        for name in list(self._tools.keys()):
            if await self.unregister(name):
                count += 1
        return count
    
    # =========================================================================
    # Access Methods
    # =========================================================================
    
    def get(self, name: str) -> Optional[BaseTool]:
        """
        Get a registered tool instance.
        
        Args:
            name: Name of the tool
            
        Returns:
            The tool instance, or None if not found
        """
        return self._tools.get(name)
    
    def get_or_create(
        self,
        name: str,
        tool_class: Optional[Type[BaseTool]] = None,
        initialize: bool = True,
        **kwargs
    ) -> BaseTool:
        """
        Get a tool or create it if not registered.
        
        Args:
            name: Name of the tool
            tool_class: Tool class to use if creating
            initialize: Whether to initialize the tool
            **kwargs: Arguments to pass to tool constructor
            
        Returns:
            The tool instance
        """
        tool = self.get(name)
        if tool is not None:
            return tool
        
        # Try to find a registered class
        if tool_class is None:
            tool_class = self._tool_classes.get(name)
            if tool_class is None:
                raise ToolRegistryError(f"Tool '{name}' not found and no class provided")
        
        # Create and register
        tool = tool_class(name=name, **kwargs)
        # Use sync registration to avoid deadlock
        self._tools[name] = tool
        self._tool_metadata[name] = tool.metadata
        return tool
    
    async def get_async(
        self,
        name: str,
        tool_class: Optional[Type[BaseTool]] = None,
        initialize: bool = True,
        **kwargs
    ) -> BaseTool:
        """
        Get a tool or create it if not registered (async version).
        
        Args:
            name: Name of the tool
            tool_class: Tool class to use if creating
            initialize: Whether to initialize the tool
            **kwargs: Arguments to pass to tool constructor
            
        Returns:
            The tool instance
        """
        tool = self.get(name)
        if tool is not None:
            if initialize and not tool.is_initialized:
                await tool.initialize()
            return tool
        
        # Try to find a registered class
        if tool_class is None:
            tool_class = self._tool_classes.get(name)
            if tool_class is None:
                raise ToolRegistryError(f"Tool '{name}' not found and no class provided")
        
        # Create and register
        tool = tool_class(name=name, **kwargs)
        await self.register_instance(tool, name, initialize)
        return tool
    
    def get_metadata(self, name: str) -> Optional[ToolMetadata]:
        """
        Get metadata for a registered tool.
        
        Args:
            name: Name of the tool
            
        Returns:
            Tool metadata, or None if not found
        """
        return self._tool_metadata.get(name)
    
    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools
    
    def has_class(self, name: str) -> bool:
        """Check if a tool class is registered."""
        return name in self._tool_classes
    
    def has_factory(self, name: str) -> bool:
        """Check if a tool factory is registered."""
        return name in self._tool_factories
    
    # =========================================================================
    # Filtering Methods
    # =========================================================================
    
    def get_by_security_level(self, level: ToolSecurityLevel) -> List[BaseTool]:
        """Get all tools with a specific security level."""
        return [
            tool for tool in self._tools.values()
            if tool.security_level == level
        ]
    
    def get_by_category(self, category: str) -> List[BaseTool]:
        """Get all tools in a specific category."""
        return [
            tool for tool in self._tools.values()
            if tool.metadata.category == category
        ]
    
    def get_enabled(self) -> List[BaseTool]:
        """Get all enabled tools."""
        return [tool for tool in self._tools.values() if tool.is_enabled]
    
    def get_available(self) -> List[BaseTool]:
        """Get all available tools."""
        return [tool for tool in self._tools.values() if tool.is_available]
    
    def get_dangerous(self) -> List[BaseTool]:
        """Get all dangerous tools."""
        return self.get_by_security_level(ToolSecurityLevel.DANGEROUS)
    
    def get_restricted(self) -> List[BaseTool]:
        """Get all restricted tools."""
        return self.get_by_security_level(ToolSecurityLevel.RESTRICTED)
    
    def get_require_approval(self) -> List[BaseTool]:
        """Get all tools that require approval."""
        return [tool for tool in self._tools.values() if tool.requires_approval]
    
    # =========================================================================
    # Bulk Operations
    # =========================================================================
    
    async def initialize_all(self) -> int:
        """
        Initialize all registered tools.
        
        Returns:
            Number of tools initialized
        """
        count = 0
        coros = []
        
        for tool in self._tools.values():
            if not tool.is_initialized:
                coros.append(tool.initialize())
        
        await asyncio.gather(*coros, return_exceptions=True)
        count = len(coros)
        
        if count > 0:
            self._initialized = True
        
        return count
    
    async def shutdown_all(self) -> int:
        """
        Shutdown all registered tools.
        
        Returns:
            Number of tools shut down
        """
        count = 0
        coros = []
        
        for tool in self._tools.values():
            coros.append(tool.shutdown())
        
        await asyncio.gather(*coros, return_exceptions=True)
        count = len(coros)
        self._initialized = False
        return count
    
    # =========================================================================
    # Event Handlers
    # =========================================================================
    
    def on_register(self, handler: Callable[[str, BaseTool], Awaitable[None]]) -> None:
        """Register a tool registration event handler."""
        self._on_register.append(handler)
    
    def on_unregister(self, handler: Callable[[str, BaseTool], Awaitable[None]]) -> None:
        """Register a tool unregistration event handler."""
        self._on_unregister.append(handler)
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def list_tools(self) -> List[str]:
        """Get a list of all registered tool names."""
        return list(self._tools.keys())
    
    def list_tool_info(self) -> List[Dict[str, Any]]:
        """Get information about all registered tools."""
        info = []
        for name, tool in self._tools.items():
            info.append({
                "name": name,
                "description": tool.description,
                "state": tool.state.value,
                "security_level": tool.security_level.value,
                "enabled": tool.is_enabled,
                "available": tool.is_available,
                "execution_count": tool.execution_count,
                "error_count": tool.error_count,
            })
        return info
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the registry."""
        return {
            "name": self.name,
            "total_tools": len(self._tools),
            "total_classes": len(self._tool_classes),
            "total_factories": len(self._tool_factories),
            "initialized": self._initialized,
            "enabled_tools": len(self.get_enabled()),
            "available_tools": len(self.get_available()),
            "dangerous_tools": len(self.get_dangerous()),
            "restricted_tools": len(self.get_restricted()),
        }
    
    def __repr__(self) -> str:
        return f"ToolRegistry(name={self.name!r}, tools={len(self._tools)})"


# =============================================================================
# Global Registry Instance
# =============================================================================

_global_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """
    Get the global tool registry instance.
    
    Returns:
        The global ToolRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry(name="Global")
    return _global_registry


def reset_tool_registry() -> ToolRegistry:
    """
    Reset the global tool registry.
    
    Returns:
        A new global ToolRegistry instance
    """
    global _global_registry
    _global_registry = ToolRegistry(name="Global")
    return _global_registry


# =============================================================================
# Convenience Functions
# =============================================================================

async def register_tool(
    tool_or_class: Type[BaseTool] | BaseTool,
    name: Optional[str] = None,
    initialize: bool = True,
    **kwargs
) -> BaseTool:
    """
    Register a tool with the global registry.
    
    Args:
        tool_or_class: Tool class or instance to register
        name: Optional name override
        initialize: Whether to initialize the tool
        **kwargs: Arguments to pass to tool constructor (if class)
        
    Returns:
        The registered tool instance
    """
    registry = get_tool_registry()
    return await registry.register(tool_or_class, name, initialize, **kwargs)


async def unregister_tool(name: str) -> bool:
    """
    Unregister a tool from the global registry.
    
    Args:
        name: Name of the tool to unregister
        
    Returns:
        True if tool was unregistered, False if not found
    """
    registry = get_tool_registry()
    return await registry.unregister(name)


def get_tool(name: str) -> Optional[BaseTool]:
    """
    Get a tool from the global registry.
    
    Args:
        name: Name of the tool
        
    Returns:
        The tool instance, or None if not found
    """
    registry = get_tool_registry()
    return registry.get(name)


async def use_tool(
    name: str,
    *args,
    initialize: bool = True,
    **kwargs
) -> Any:
    """
    Get a tool and execute it.
    
    This is a convenience function for getting a tool and executing it in one call.
    
    Args:
        name: Name of the tool
        *args: Arguments to pass to the tool
        initialize: Whether to initialize the tool if not already
        **kwargs: Keyword arguments to pass to the tool
        
    Returns:
        The result of the tool execution
    """
    registry = get_tool_registry()
    tool = await registry.get_async(name, initialize=initialize)
    return await tool.execute(*args, **kwargs)


# =============================================================================
# Exceptions
# =============================================================================

class ToolRegistryError(Exception):
    """Exception for tool registry errors."""
    
    def __init__(self, message: str, code: Optional[str] = None, details: Optional[Dict] = None):
        super().__init__(message)
        self.message = message
        self.code = code or "REGISTRY_ERROR"
        self.details = details or {}


class ToolNotFoundError(ToolRegistryError):
    """Exception for tool not found errors."""
    
    def __init__(self, message: str, tool_name: Optional[str] = None, details: Optional[Dict] = None):
        super().__init__(message, code="TOOL_NOT_FOUND", details=details)
        self.tool_name = tool_name


class ToolAlreadyRegisteredError(ToolRegistryError):
    """Exception for tool already registered errors."""
    
    def __init__(self, message: str, tool_name: Optional[str] = None, details: Optional[Dict] = None):
        super().__init__(message, code="TOOL_ALREADY_REGISTERED", details=details)
        self.tool_name = tool_name
