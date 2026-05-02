"""
ACI Interface Module.

Defines the core protocol and interface for Agent-Computer communication.
This is the foundation of all agent interactions in the harness.
"""

import asyncio
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic, Callable, Awaitable

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Type Definitions
# =============================================================================

T = TypeVar('T')
MessageID = str  # UUID string
Timestamp = str   # ISO format timestamp


# =============================================================================
# Message Base Classes (Pydantic Models)
# =============================================================================

class MessageMetadata(BaseModel):
    """Metadata common to all ACI messages."""
    
    message_id: MessageID = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: Timestamp = Field(default_factory=lambda: datetime.utcnow().isoformat())
    sender: str = Field(..., description="Sender identifier (agent name or 'system')")
    receiver: Optional[str] = Field(default=None, description="Receiver identifier (optional)")
    correlation_id: Optional[MessageID] = Field(
        default=None,
        description="Correlation ID for tracking related messages"
    )
    version: str = Field(default="1.0", description="ACI protocol version")


class Priority(str, Enum):
    """Message priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# =============================================================================
# ACI Protocol Definition
# =============================================================================

class ACIProtocol(BaseModel):
    """
    ACI Protocol Definition.
    
    This defines the protocol version, supported message types,
    and capabilities of the ACI implementation.
    """
    
    version: str = "1.0"
    name: str = "Harness ACI"
    description: str = "Agent-Computer Interface for Harness Agentic Framework"
    
    # Supported command types
    supported_commands: List[str] = Field(
        default_factory=lambda: [
            "task_assignment",
            "task_progress",
            "task_result",
            "task_error",
            "context_request",
            "context_response",
        ]
    )
    
    # Supported response types
    supported_responses: List[str] = Field(
        default_factory=lambda: [
            "ack",
            "nack",
            "progress",
            "result",
            "error",
            "context",
        ]
    )
    
    # Security capabilities
    supports_validation: bool = True
    supports_sanitization: bool = True
    supports_encryption: bool = False
    supports_signing: bool = False
    
    # Performance capabilities
    supports_async: bool = True
    supports_streaming: bool = False
    max_message_size: int = 1024 * 1024  # 1 MB


# =============================================================================
# ACI Interface (Abstract Base)
# =============================================================================

class ACIInterface(ABC):
    """
    Abstract base class for ACI implementations.
    
    All ACI implementations must extend this class and implement
    the required methods for sending and receiving messages.
    """
    
    def __init__(self, name: str, protocol: ACIProtocol = None):
        """
        Initialize the ACI interface.
        
        Args:
            name: Identifier for this interface instance
            protocol: ACI protocol to use (defaults to standard protocol)
        """
        self.name = name
        self.protocol = protocol or ACIProtocol()
        self._message_handlers: Dict[str, Callable] = {}
        self._middleware: List[Callable] = []
    
    @property
    def protocol_version(self) -> str:
        """Get the protocol version."""
        return self.protocol.version
    
    @abstractmethod
    async def send(self, message: BaseModel, receiver: Optional[str] = None) -> BaseModel:
        """
        Send a message via the ACI.
        
        Args:
            message: The message to send (must be a Pydantic model)
            receiver: Optional specific receiver
            
        Returns:
            The response message from the receiver
            
        Raises:
            ACIError: If the message cannot be sent or delivered
        """
        pass
    
    @abstractmethod
    async def receive(self) -> BaseModel:
        """
        Receive a message from the ACI.
        
        Returns:
            The received message (Pydantic model)
            
        Raises:
            ACIError: If no message is available
        """
        pass
    
    @abstractmethod
    async def request(self, message: BaseModel, timeout: float = 30.0) -> BaseModel:
        """
        Send a request and wait for a response.
        
        Args:
            message: The request message
            timeout: Timeout in seconds
            
        Returns:
            The response message
            
        Raises:
            asyncio.TimeoutError: If response not received in time
            ACIError: If the request fails
        """
        pass
    
    def register_handler(self, message_type: str, handler: Callable[[BaseModel], Awaitable[BaseModel]]):
        """
        Register a message handler for a specific message type.
        
        Args:
            message_type: The type of message to handle
            handler: Async function to call when message received
        """
        self._message_handlers[message_type] = handler
    
    def add_middleware(self, middleware: Callable[[BaseModel, BaseModel], Awaitable[BaseModel]]):
        """
        Add middleware that processes messages before handling.
        
        Args:
            middleware: Async function that takes (message, next) and returns response
        """
        self._middleware.append(middleware)
    
    async def handle(self, message: BaseModel) -> BaseModel:
        """
        Handle an incoming message.
        
        This method routes the message to the appropriate handler
        based on its type and applies any registered middleware.
        
        Args:
            message: The incoming message
            
        Returns:
            The response message
        """
        # Apply middleware
        for mw in self._middleware:
            message = await mw(message, self._handle_direct)
        
        return await self._handle_direct(message)
    
    async def _handle_direct(self, message: BaseModel) -> BaseModel:
        """Internal method to handle message directly."""
        message_type = message.__class__.__name__
        handler = self._message_handlers.get(message_type)
        
        if handler is None:
            raise ACIError(f"No handler registered for message type: {message_type}")
        
        return await handler(message)


# =============================================================================
# In-Memory ACI Implementation (for internal harness communication)
# =============================================================================

class InMemoryACI(ACIInterface):
    """
    In-memory ACI implementation for internal harness communication.
    
    This is used for communication between:
    - God Agent and Specialist Agents
    - Agents and Tools
    - Internal harness components
    """
    
    def __init__(self, name: str):
        super().__init__(name)
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._response_futures: Dict[MessageID, asyncio.Future] = {}
    
    async def send(self, message: BaseModel, receiver: Optional[str] = None) -> BaseModel:
        """Send a message and return immediately (fire-and-forget)."""
        # Add metadata if not present
        if not hasattr(message, 'message_id'):
            metadata = MessageMetadata(
                sender=self.name,
                receiver=receiver,
                correlation_id=getattr(message, 'correlation_id', None)
            )
            message_with_metadata = {**metadata.model_dump(), **message.model_dump()}
            # Recreate with metadata
            message = type(message)(**message_with_metadata)
        
        await self._message_queue.put(message)
        return message
    
    async def receive(self) -> BaseModel:
        """Receive the next available message."""
        return await self._message_queue.get()
    
    async def request(self, message: BaseModel, timeout: float = 30.0) -> BaseModel:
        """Send a request and wait for a response."""
        message_id = getattr(message, 'message_id', str(uuid.uuid4()))
        correlation_id = getattr(message, 'correlation_id', message_id)
        
        # Create a future for the response
        future: asyncio.Future = asyncio.Future()
        self._response_futures[message_id] = future
        
        # Add metadata
        metadata = MessageMetadata(
            message_id=message_id,
            sender=self.name,
            correlation_id=correlation_id
        )
        message_with_metadata = {**metadata.model_dump(), **message.model_dump()}
        message = type(message)(**message_with_metadata)
        
        # Send the message
        await self._message_queue.put(message)
        
        # Wait for response
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            # Clean up
            self._response_futures.pop(message_id, None)
            raise ACIError(f"Request timed out after {timeout}s: {message_id}")
    
    async def respond(self, response: BaseModel, correlation_id: Optional[MessageID] = None) -> None:
        """
        Send a response to a pending request.
        
        Args:
            response: The response message
            correlation_id: The ID of the request to respond to
        """
        if correlation_id is None:
            correlation_id = getattr(response, 'correlation_id', None)
        
        if correlation_id and correlation_id in self._response_futures:
            future = self._response_futures.pop(correlation_id)
            if not future.done():
                future.set_result(response)


# =============================================================================
# ACI Errors
# =============================================================================

class ACIError(Exception):
    """Base exception for ACI errors."""
    
    def __init__(self, message: str, code: Optional[str] = None, details: Optional[Dict] = None):
        super().__init__(message)
        self.message = message
        self.code = code or "ACI_ERROR"
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary."""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details
        }


class ACITimeoutError(ACIError):
    """Timeout error for ACI operations."""
    
    def __init__(self, message: str = "ACI operation timed out", timeout: float = 0):
        super().__init__(message, code="ACI_TIMEOUT")
        self.timeout = timeout


class ACIValidationError(ACIError):
    """Validation error for ACI messages."""
    
    def __init__(self, message: str, errors: Optional[List[Dict]] = None):
        super().__init__(message, code="ACI_VALIDATION_ERROR", details={"errors": errors or []})
        self.errors = errors or []


class ACISecurityError(ACIError):
    """Security error for ACI operations."""
    
    def __init__(self, message: str = "ACI security violation"):
        super().__init__(message, code="ACI_SECURITY_ERROR")
