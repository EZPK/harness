"""
ACI Responses Module.

Defines all response message types for the Agent-Computer Interface.
Responses are sent from receivers back to senders in reply to commands.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .interface import MessageMetadata, MessageID, Timestamp
from .commands import CommandType, TaskBase


# =============================================================================
# Response Status
# =============================================================================

class ResponseStatus(str, Enum):
    """Status codes for ACI responses."""
    
    ACK = "ack"             # Acknowledged, processing started
    NACK = "nack"           # Not acknowledged, will not process
    PROCESSING = "processing"  # Currently processing
    SUCCESS = "success"       # Completed successfully
    PARTIAL = "partial"       # Partial success/completion
    FAILURE = "failure"       # Failed to complete
    ERROR = "error"          # Error occurred
    TIMEOUT = "timeout"       # Operation timed out
    CANCELLED = "cancelled"    # Operation was cancelled
    SKIPPED = "skipped"       # Operation was skipped


# =============================================================================
# Base Response
# =============================================================================

class Response(MessageMetadata):
    """Base class for all ACI responses."""
    
    status: ResponseStatus = Field(..., description="Response status")
    status_message: str = Field(
        default="",
        description="Human-readable status message"
    )
    
    @property
    def is_success(self) -> bool:
        """Check if this response indicates success."""
        return self.status in {ResponseStatus.SUCCESS, ResponseStatus.ACK, ResponseStatus.PROCESSING}
    
    @property
    def is_failure(self) -> bool:
        """Check if this response indicates failure."""
        return self.status in {
            ResponseStatus.NACK,
            ResponseStatus.FAILURE,
            ResponseStatus.ERROR,
            ResponseStatus.TIMEOUT,
            ResponseStatus.CANCELLED,
        }
    
    @property
    def is_task_related(self) -> bool:
        """Check if this response is task-related."""
        return isinstance(self, (TaskAssignmentResponse, TaskProgressResponse, 
                                TaskResultResponse, TaskErrorResponse))
    
    @property
    def is_context_related(self) -> bool:
        """Check if this response is context-related."""
        return isinstance(self, (ContextRequestResponse, ContextResponseResponse))


# =============================================================================
# Task-Related Responses
# =============================================================================

class TaskAssignmentResponse(Response):
    """
    Response to a TaskAssignmentCommand.
    
    Sent from: Specialist Agent
    Sent to: God Agent (or orchestrator)
    """
    
    status: ResponseStatus = Field(
        default=ResponseStatus.ACK,
        description="Typically ACK or NACK"
    )
    
    # Reference to the task
    task_id: MessageID = Field(..., description="ID of the assigned task")
    
    # If NACK, reason for rejection
    rejection_reason: Optional[str] = Field(
        default=None,
        description="Reason for rejecting the task (if NACK)"
    )
    
    # If ACK, when processing will start
    starts_at: Optional[Timestamp] = Field(
        default=None,
        description="When task processing will start"
    )
    
    # Estimated completion time
    estimated_completion_ms: Optional[float] = Field(
        default=None,
        description="Estimated time to complete in milliseconds"
    )


class TaskProgressResponse(Response):
    """
    Response to a TaskProgressCommand (typically ACK).
    
    Sent from: God Agent
    Sent to: Specialist Agent
    """
    
    status: ResponseStatus = Field(
        default=ResponseStatus.ACK,
        description="Acknowledgment status"
    )
    
    task_id: MessageID = Field(..., description="ID of the task being tracked")
    
    # Acknowledgment of receipt
    received_at: Timestamp = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="When the progress update was received"
    )
    
    # Optional feedback
    feedback: Optional[str] = Field(
        default=None,
        description="Optional feedback on the progress"
    )
    
    @classmethod
        return CommandType.TASK_PROGRESS


class TaskResultResponse(Response):
    """
    Response to a TaskResultCommand.
    
    Sent from: God Agent
    Sent to: Specialist Agent
    """
    
    status: ResponseStatus = Field(
        default=ResponseStatus.ACK,
        description="Acknowledgment status"
    )
    
    task_id: MessageID = Field(..., description="ID of the completed task")
    
    # Confirmation
    result_accepted: bool = Field(
        default=True,
        description="Whether the result was accepted"
    )
    
    # If not accepted
    rejection_reason: Optional[str] = Field(
        default=None,
        description="Reason for rejecting the result"
    )
    
    # Next steps
    next_steps: List[str] = Field(
        default_factory=list,
        description="Next steps to take"
    )
    
    # Reward/feedback for the agent
    quality_score: Optional[float] = Field(
        default=None,
        ge=0.0, le=1.0,
        description="Quality score for the result"
    )
    
    feedback: Optional[str] = Field(
        default=None,
        description="Feedback on the result"
    )
    
    @classmethod
        return CommandType.TASK_RESULT


class TaskErrorResponse(Response):
    """
    Response to a TaskErrorCommand.
    
    Sent from: God Agent
    Sent to: Specialist Agent
    """
    
    status: ResponseStatus = Field(
        default=ResponseStatus.ACK,
        description="Acknowledgment status"
    )
    
    task_id: MessageID = Field(..., description="ID of the failed task")
    
    # Action to take
    action: str = Field(
        default="retry",
        description="Action to take (retry, skip, fallback, escalate)"
    )
    
    # Retry configuration
    retry_after_ms: Optional[float] = Field(
        default=None,
        description="Time to wait before retrying in milliseconds"
    )
    
    # Max retries
    max_retries: Optional[int] = Field(
        default=None,
        description="Maximum number of retries allowed"
    )
    
    # Fallback task
    fallback_task: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Fallback task to execute if retry fails"
    )
    
    # Escalation information
    escalate_to: Optional[str] = Field(
        default=None,
        description="Agent to escalate to if error persists"
    )
    
    @classmethod
        return CommandType.TASK_ERROR


# =============================================================================
# Context-Related Responses
# =============================================================================

class ContextRequestResponse(Response):
    """
    Response to a ContextRequestCommand.
    
    Sent from: Any Agent (respondent)
    Sent to: Any Agent (requester)
    """
    
    status: ResponseStatus = Field(
        default=ResponseStatus.SUCCESS,
        description="Status of the context response"
    )
    
    context_id: MessageID = Field(..., description="ID of the context request")
    
    # The context data
    context: Any = Field(
        default=None,
        description="The requested context data"
    )
    
    # Context type
    context_type: Optional[str] = Field(
        default=None,
        description="Type of the context provided"
    )
    
    # If not found
    not_found: bool = Field(
        default=False,
        description="Whether the context was not found"
    )
    
    # Alternative suggestions
    alternatives: List[Any] = Field(
        default_factory=list,
        description="Alternative context options if exact match not found"
    )
    
    @classmethod
        return CommandType.CONTEXT_REQUEST


class ContextResponseResponse(Response):
    """
    Response to a ContextResponseCommand (ACK).
    
    Sent from: Any Agent (requester)
    Sent to: Any Agent (respondent)
    """
    
    status: ResponseStatus = Field(
        default=ResponseStatus.ACK,
        description="Acknowledgment status"
    )
    
    context_id: MessageID = Field(..., description="ID of the context response")
    
    # Confirmation
    context_received: bool = Field(
        default=True,
        description="Whether the context was received successfully"
    )
    
    # Quality feedback
    context_quality: Optional[float] = Field(
        default=None,
        ge=0.0, le=1.0,
        description="Quality score for the context"
    )
    
    # Feedback
    feedback: Optional[str] = Field(
        default=None,
        description="Feedback on the context"
    )
    
    @classmethod
        return CommandType.CONTEXT_RESPONSE


# =============================================================================
# Response Factory
# =============================================================================

class ResponseFactory:
    """Factory for creating ACI responses."""
    
    @staticmethod
    def create_ack(
        sender: str,
        receiver: Optional[str] = None,
        message: str = "Acknowledged",
        correlation_id: Optional[str] = None,
    ) -> Response:
        """Create a generic ACK response."""
        return Response(
            message_id=str(uuid.uuid4()),
            sender=sender,
            receiver=receiver,
            correlation_id=correlation_id,
            status=ResponseStatus.ACK,
            status_message=message,
        )
    
    @staticmethod
    def create_nack(
        sender: str,
        reason: str,
        receiver: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Response:
        """Create a NACK response."""
        return Response(
            message_id=str(uuid.uuid4()),
            sender=sender,
            receiver=receiver,
            correlation_id=correlation_id,
            status=ResponseStatus.NACK,
            status_message=reason,
        )
    
    @staticmethod
    def create_success(
        sender: str,
        message: str = "Success",
        receiver: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Response:
        """Create a SUCCESS response."""
        return Response(
            message_id=str(uuid.uuid4()),
            sender=sender,
            receiver=receiver,
            correlation_id=correlation_id,
            status=ResponseStatus.SUCCESS,
            status_message=message,
        )
    
    @staticmethod
    def create_error(
        sender: str,
        error: str,
        message: Optional[str] = None,
        receiver: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Response:
        """Create an ERROR response."""
        return Response(
            message_id=str(uuid.uuid4()),
            sender=sender,
            receiver=receiver,
            correlation_id=correlation_id,
            status=ResponseStatus.ERROR,
            status_message=message or error,
        )
    
    @staticmethod
    def create_task_ack(
        task_id: str,
        sender: str,
        receiver: Optional[str] = None,
        correlation_id: Optional[str] = None,
        estimated_completion_ms: Optional[float] = None,
    ) -> TaskAssignmentResponse:
        """Create a task assignment ACK response."""
        return TaskAssignmentResponse(
            message_id=str(uuid.uuid4()),
            sender=sender,
            receiver=receiver,
            correlation_id=correlation_id,
            status=ResponseStatus.ACK,
            task_id=task_id,
            estimated_completion_ms=estimated_completion_ms,
        )
    
    @staticmethod
    def create_task_nack(
        task_id: str,
        sender: str,
        reason: str,
        receiver: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> TaskAssignmentResponse:
        """Create a task assignment NACK response."""
        return TaskAssignmentResponse(
            message_id=str(uuid.uuid4()),
            sender=sender,
            receiver=receiver,
            correlation_id=correlation_id,
            status=ResponseStatus.NACK,
            task_id=task_id,
            rejection_reason=reason,
        )
    
    @staticmethod
    def create_context_response(
        context_id: str,
        context: Any,
        context_type: str,
        sender: str,
        receiver: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> ContextRequestResponse:
        """Create a context response."""
        return ContextRequestResponse(
            message_id=str(uuid.uuid4()),
            sender=sender,
            receiver=receiver,
            correlation_id=correlation_id,
            status=ResponseStatus.SUCCESS,
            context_id=context_id,
            context=context,
            context_type=context_type,
        )
    
    @staticmethod
    def create_context_not_found(
        context_id: str,
        sender: str,
        message: str = "Context not found",
        receiver: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> ContextRequestResponse:
        """Create a context not found response."""
        return ContextRequestResponse(
            message_id=str(uuid.uuid4()),
            sender=sender,
            receiver=receiver,
            correlation_id=correlation_id,
            status=ResponseStatus.FAILURE,
            context_id=context_id,
            not_found=True,
            status_message=message,
        )


# =============================================================================
# Response Serialization
# =============================================================================

def serialize_response(response: Response) -> str:
    """Serialize a response to JSON string."""
    return response.model_dump_json()


def deserialize_response(data: Union[str, Dict[str, Any]]) -> Response:
    """
    Deserialize JSON data to a Response object.
    
    Args:
        data: JSON string or dictionary
        
    Returns:
        Response: The deserialized response
        
    Raises:
        ValueError: If the response type cannot be determined
    """
    if isinstance(data, str):
        import json
        data = json.loads(data)
    
    # Try to determine response type based on fields
    if 'task_id' in data and 'status' in data:
        # Could be any task-related response
        if 'result_accepted' in data:
            return TaskResultResponse(**data)
        elif 'rejection_reason' in data:
            return TaskAssignmentResponse(**data)
        elif 'received_at' in data:
            return TaskProgressResponse(**data)
        elif 'action' in data:
            return TaskErrorResponse(**data)
    
    if 'context_id' in data and 'context' in data:
        return ContextRequestResponse(**data)
    elif 'context_id' in data and 'context_received' in data:
        return ContextResponseResponse(**data)
    
    # Fall back to generic Response
    return Response(**data)
