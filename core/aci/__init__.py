"""
Agent-Computer Interface (ACI) Module.

The ACI provides a standardized interface for communication between:
- God Agent and Specialist Agents
- Agents and Tools
- Internal Harness components

This is a critical component (Part of the 98.4% harness infrastructure).
"""

from .interface import ACIInterface, ACIProtocol
from .commands import (
    Command,
    CommandType,
    TaskAssignmentCommand,
    TaskProgressCommand,
    TaskResultCommand,
    TaskErrorCommand,
    ContextRequestCommand,
    ContextResponseCommand,
)
from .responses import (
    Response,
    ResponseStatus,
    TaskAssignmentResponse,
    TaskProgressResponse,
    TaskResultResponse,
    TaskErrorResponse,
    ContextRequestResponse,
    ContextResponseResponse,
)
from .validation import ACIValidator, ValidationResult, sanitize_input, validate_output

__all__ = [
    # Interface
    "ACIInterface",
    "ACIProtocol",
    # Commands
    "Command",
    "CommandType",
    "TaskAssignmentCommand",
    "TaskProgressCommand",
    "TaskResultCommand",
    "TaskErrorCommand",
    "ContextRequestCommand",
    "ContextResponseCommand",
    # Responses
    "Response",
    "ResponseStatus",
    "TaskAssignmentResponse",
    "TaskProgressResponse",
    "TaskResultResponse",
    "TaskErrorResponse",
    "ContextRequestResponse",
    "ContextResponseResponse",
    # Validation
    "ACIValidator",
    "ValidationResult",
    "sanitize_input",
    "validate_output",
]
