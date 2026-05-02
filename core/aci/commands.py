"""
ACI Commands Module.

Defines all command message types for the Agent-Computer Interface.
Commands are sent from senders (typically God Agent) to receivers (typically Specialist Agents).
"""

import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .interface import MessageMetadata, Priority, MessageID, Timestamp


# =============================================================================
# Command Types
# =============================================================================

class CommandType(str, Enum):
    """Types of ACI commands."""
    
    TASK_ASSIGNMENT = "task_assignment"      # Assign a task to an agent
    TASK_PROGRESS = "task_progress"           # Report progress on a task
    TASK_RESULT = "task_result"              # Report completion of a task
    TASK_ERROR = "task_error"                # Report an error with a task
    CONTEXT_REQUEST = "context_request"      # Request context from another agent
    CONTEXT_RESPONSE = "context_response"    # Provide context to another agent


# =============================================================================
# Base Command
# =============================================================================

class Command(MessageMetadata):
    """Base class for all ACI commands."""
    
    command_type: CommandType = Field(..., description="Type of command")
    priority: Priority = Field(default=Priority.MEDIUM, description="Command priority")
    
    @property
    def is_task_related(self) -> bool:
        """Check if this command is task-related."""
        return self.command_type in {
            CommandType.TASK_ASSIGNMENT,
            CommandType.TASK_PROGRESS,
            CommandType.TASK_RESULT,
            CommandType.TASK_ERROR,
        }
    
    @property
    def is_context_related(self) -> bool:
        """Check if this command is context-related."""
        return self.command_type in {
            CommandType.CONTEXT_REQUEST,
            CommandType.CONTEXT_RESPONSE,
        }


# =============================================================================
# Task-Related Commands
# =============================================================================

class TaskBase(Command):
    """Base class for task-related commands."""
    
    task_id: MessageID = Field(..., description="Unique identifier for the task")
    parent_task_id: Optional[MessageID] = Field(
        default=None,
        description="Parent task ID if this is a subtask"
    )
    workflow_id: Optional[MessageID] = Field(
        default=None,
        description="Workflow ID if part of a workflow"
    )


class TaskAssignmentCommand(TaskBase):
    """
    Command to assign a task to an agent.
    
    Sent from: God Agent (or other orchestrator)
    Sent to: Specialist Agent
    """
    
    command_type: CommandType = CommandType.TASK_ASSIGNMENT
    
    # Task details
    task_name: str = Field(..., description="Human-readable task name")
    task_description: str = Field(..., description="Detailed task description")
    task_type: str = Field(..., description="Type of task (e.g., 'code', 'review', 'test')")
    
    # Task parameters
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for the task"
    )
    
    # Context from previous tasks
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Context from parent tasks or workflow"
    )
    
    # Execution constraints
    timeout: Optional[int] = Field(
        default=None,
        description="Task-specific timeout (overrides agent default)"
    )
    max_retries: Optional[int] = Field(
        default=None,
        description="Task-specific max retries (overrides agent default)"
    )
    
    # Requirements
    required_tools: List[str] = Field(
        default_factory=list,
        description="Tools required for this task"
    )
    required_capabilities: List[str] = Field(
        default_factory=list,
        description="Agent capabilities required for this task"
    )
    
    # Dependencies
    depends_on: List[MessageID] = Field(
        default_factory=list,
        description="List of task IDs this task depends on"
    )
    
    # Callback information
    callback_url: Optional[str] = Field(
        default=None,
        description="URL to send results back to (for distributed systems)"
    )
    
    @field_validator('command_type')
    @classmethod
    def validate_command_type(cls, v):
        if v != CommandType.TASK_ASSIGNMENT:
            raise ValueError(f"TaskAssignmentCommand must have type TASK_ASSIGNMENT, got {v}")
        return v


class TaskProgressCommand(TaskBase):
    """
    Command to report progress on a task.
    
    Sent from: Specialist Agent
    Sent to: God Agent (or orchestrator)
    """
    
    command_type: CommandType = CommandType.TASK_PROGRESS
    
    # Progress information
    progress_percent: float = Field(
        ge=0.0, le=100.0,
        description="Percentage of task completed (0-100)"
    )
    progress_message: str = Field(
        default="",
        description="Human-readable progress message"
    )
    
    # Current state
    current_step: str = Field(
        default="",
        description="Current step being executed"
    )
    total_steps: Optional[int] = Field(
        default=None,
        description="Total number of steps"
    )
    current_step_number: Optional[int] = Field(
        default=None,
        description="Current step number"
    )
    
    # Partial results
    partial_results: Dict[str, Any] = Field(
        default_factory=dict,
        description="Partial results available so far"
    )
    
    # Estimated time remaining (seconds)
    estimated_time_remaining: Optional[float] = Field(
        default=None,
        description="Estimated seconds remaining"
    )
    
    @field_validator('command_type')
    @classmethod
    def validate_command_type(cls, v):
        if v != CommandType.TASK_PROGRESS:
            raise ValueError(f"TaskProgressCommand must have type TASK_PROGRESS, got {v}")
        return v


class TaskResultCommand(TaskBase):
    """
    Command to report successful completion of a task.
    
    Sent from: Specialist Agent
    Sent to: God Agent (or orchestrator)
    """
    
    command_type: CommandType = CommandType.TASK_RESULT
    
    # Results
    result: Any = Field(..., description="The main result of the task")
    result_type: str = Field(..., description="Type/format of the result")
    
    # Additional outputs
    outputs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional outputs from the task"
    )
    
    # Metadata
    started_at: Timestamp = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="When the task started"
    )
    completed_at: Timestamp = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="When the task completed"
    )
    
    # Performance metrics
    execution_time_ms: float = Field(
        ge=0.0,
        description="Time taken to execute in milliseconds"
    )
    tokens_used: Optional[int] = Field(
        default=None,
        description="Number of tokens used (if applicable)"
    )
    
    # Quality metrics
    confidence_score: Optional[float] = Field(
        default=None,
        ge=0.0, le=1.0,
        description="Confidence in the result (0-1)"
    )
    quality_score: Optional[float] = Field(
        default=None,
        ge=0.0, le=1.0,
        description="Quality score for the result (0-1)"
    )
    
    # Warnings
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings generated during task execution"
    )
    
    @field_validator('command_type')
    @classmethod
    def validate_command_type(cls, v):
        if v != CommandType.TASK_RESULT:
            raise ValueError(f"TaskResultCommand must have type TASK_RESULT, got {v}")
        return v


class TaskErrorCommand(TaskBase):
    """
    Command to report an error during task execution.
    
    Sent from: Specialist Agent
    Sent to: God Agent (or orchestrator)
    """
    
    command_type: CommandType = CommandType.TASK_ERROR
    
    # Error details
    error_type: str = Field(..., description="Type of error (e.g., 'validation', 'execution')")
    error_message: str = Field(..., description="Human-readable error message")
    error_code: Optional[str] = Field(
        default=None,
        description="Machine-readable error code"
    )
    
    # Error context
    error_details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional error details"
    )
    
    # Stack trace
    stack_trace: Optional[str] = Field(
        default=None,
        description="Stack trace if available"
    )
    
    # Retry information
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Number of retries attempted"
    )
    max_retries_reached: bool = Field(
        default=False,
        description="Whether maximum retries was reached"
    )
    
    # Partial results (if any)
    partial_results: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Any partial results before the error"
    )
    
    # Suggested actions
    suggested_actions: List[str] = Field(
        default_factory=list,
        description="Suggested actions to resolve the error"
    )
    
    @field_validator('command_type')
    @classmethod
    def validate_command_type(cls, v):
        if v != CommandType.TASK_ERROR:
            raise ValueError(f"TaskErrorCommand must have type TASK_ERROR, got {v}")
        return v


# =============================================================================
# Context-Related Commands
# =============================================================================

class ContextBase(Command):
    """Base class for context-related commands."""
    
    context_id: MessageID = Field(..., description="Unique identifier for the context request")


class ContextRequestCommand(ContextBase):
    """
    Command to request context from another agent.
    
    Sent from: Any Agent
    Sent to: Any Agent (typically God Agent or another Specialist)
    """
    
    command_type: CommandType = CommandType.CONTEXT_REQUEST
    
    # Request details
    context_type: str = Field(..., description="Type of context needed")
    context_description: str = Field(
        default="",
        description="Description of what context is needed"
    )
    
    # Query parameters
    query: Dict[str, Any] = Field(
        default_factory=dict,
        description="Query parameters for the context request"
    )
    
    # Filter criteria
    filters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Filters to apply to the context"
    )
    
    # Priority for this request
    priority: Priority = Field(
        default=Priority.MEDIUM,
        description="Priority of this context request"
    )
    
    @field_validator('command_type')
    @classmethod
    def validate_command_type(cls, v):
        if v != CommandType.CONTEXT_REQUEST:
            raise ValueError(f"ContextRequestCommand must have type CONTEXT_REQUEST, got {v}")
        return v


class ContextResponseCommand(ContextBase):
    """
    Command to provide context in response to a request.
    
    Sent from: Any Agent (respondent)
    Sent to: Any Agent (requester)
    """
    
    command_type: CommandType = CommandType.CONTEXT_RESPONSE
    
    # Response details
    context_type: str = Field(..., description="Type of context provided")
    context: Any = Field(..., description="The context data")
    
    # Additional metadata
    context_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata about the context"
    )
    
    # Source information
    source: str = Field(
        default="",
        description="Source of the context (e.g., 'database', 'cache')"
    )
    
    # Timestamp when context was generated
    generated_at: Timestamp = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="When the context was generated"
    )
    
    # Expiration (if applicable)
    expires_at: Optional[Timestamp] = Field(
        default=None,
        description="When the context expires"
    )
    
    @field_validator('command_type')
    @classmethod
    def validate_command_type(cls, v):
        if v != CommandType.CONTEXT_RESPONSE:
            raise ValueError(f"ContextResponseCommand must have type CONTEXT_RESPONSE, got {v}")
        return v


# =============================================================================
# Command Factory
# =============================================================================

class CommandFactory:
    """Factory for creating ACI commands."""
    
    @staticmethod
    def create_task_assignment(
        task_name: str,
        task_description: str,
        task_type: str,
        sender: str,
        receiver: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        priority: Priority = Priority.MEDIUM,
        timeout: Optional[int] = None,
        required_tools: Optional[List[str]] = None,
        required_capabilities: Optional[List[str]] = None,
    ) -> TaskAssignmentCommand:
        """Create a task assignment command."""
        return TaskAssignmentCommand(
            task_id=str(uuid.uuid4()),
            task_name=task_name,
            task_description=task_description,
            task_type=task_type,
            sender=sender,
            receiver=receiver,
            parameters=parameters or {},
            context=context or {},
            priority=priority,
            timeout=timeout,
            required_tools=required_tools or [],
            required_capabilities=required_capabilities or [],
        )
    
    @staticmethod
    def create_task_progress(
        task_id: str,
        progress_percent: float,
        progress_message: str = "",
        sender: str = "",
        current_step: str = "",
        partial_results: Optional[Dict[str, Any]] = None,
    ) -> TaskProgressCommand:
        """Create a task progress command."""
        return TaskProgressCommand(
            task_id=task_id,
            progress_percent=progress_percent,
            progress_message=progress_message,
            sender=sender,
            current_step=current_step,
            partial_results=partial_results or {},
        )
    
    @staticmethod
    def create_task_result(
        task_id: str,
        result: Any,
        result_type: str,
        sender: str,
        execution_time_ms: float = 0.0,
        outputs: Optional[Dict[str, Any]] = None,
        warnings: Optional[List[str]] = None,
    ) -> TaskResultCommand:
        """Create a task result command."""
        return TaskResultCommand(
            task_id=task_id,
            result=result,
            result_type=result_type,
            sender=sender,
            execution_time_ms=execution_time_ms,
            outputs=outputs or {},
            warnings=warnings or [],
        )
    
    @staticmethod
    def create_task_error(
        task_id: str,
        error_type: str,
        error_message: str,
        sender: str,
        error_code: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None,
        stack_trace: Optional[str] = None,
        retry_count: int = 0,
        max_retries_reached: bool = False,
    ) -> TaskErrorCommand:
        """Create a task error command."""
        return TaskErrorCommand(
            task_id=task_id,
            error_type=error_type,
            error_message=error_message,
            sender=sender,
            error_code=error_code,
            error_details=error_details or {},
            stack_trace=stack_trace,
            retry_count=retry_count,
            max_retries_reached=max_retries_reached,
        )
    
    @staticmethod
    def create_context_request(
        context_type: str,
        sender: str,
        receiver: Optional[str] = None,
        context_description: str = "",
        query: Optional[Dict[str, Any]] = None,
        priority: Priority = Priority.MEDIUM,
    ) -> ContextRequestCommand:
        """Create a context request command."""
        return ContextRequestCommand(
            context_id=str(uuid.uuid4()),
            context_type=context_type,
            sender=sender,
            receiver=receiver,
            context_description=context_description,
            query=query or {},
            priority=priority,
        )
    
    @staticmethod
    def create_context_response(
        context_id: str,
        context_type: str,
        context: Any,
        sender: str,
        source: str = "",
        context_metadata: Optional[Dict[str, Any]] = None,
    ) -> ContextResponseCommand:
        """Create a context response command."""
        return ContextResponseCommand(
            context_id=context_id,
            context_type=context_type,
            context=context,
            sender=sender,
            source=source,
            context_metadata=context_metadata or {},
        )


# =============================================================================
# Command Serialization
# =============================================================================

def serialize_command(command: Command) -> str:
    """Serialize a command to JSON string."""
    return command.model_dump_json()


def deserialize_command(data: Union[str, Dict[str, Any]]) -> Command:
    """
    Deserialize JSON data to a Command object.
    
    Args:
        data: JSON string or dictionary
        
    Returns:
        Command: The deserialized command
        
    Raises:
        ValueError: If the command type cannot be determined
    """
    if isinstance(data, str):
        data = json.loads(data)
    
    command_type = data.get('command_type')
    
    if command_type == CommandType.TASK_ASSIGNMENT:
        return TaskAssignmentCommand(**data)
    elif command_type == CommandType.TASK_PROGRESS:
        return TaskProgressCommand(**data)
    elif command_type == CommandType.TASK_RESULT:
        return TaskResultCommand(**data)
    elif command_type == CommandType.TASK_ERROR:
        return TaskErrorCommand(**data)
    elif command_type == CommandType.CONTEXT_REQUEST:
        return ContextRequestCommand(**data)
    elif command_type == CommandType.CONTEXT_RESPONSE:
        return ContextResponseCommand(**data)
    else:
        raise ValueError(f"Unknown command type: {command_type}")
