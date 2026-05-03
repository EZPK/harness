"""
Converters for TUI Models.

These functions convert from the internal Harness models to the TUI display models.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from agents.base import BaseAgent, AgentState, AgentStatus, TaskContext, TaskResult
    from agents.god.agent import GodAgent, WorkflowDefinition, WorkflowStep, TaskAssignment
    from core.aci.commands import Command, TaskAssignmentCommand, TaskResultCommand
    from .display_models import (
        TUIAgent,
        TUIAgentStatus,
        TUITask,
        TUITaskStatus,
        TUIWorkflow,
        TUIWorkflowStatus,
        TUIWorkflowStep,
        TUIMessage,
        TUIMessageType,
        TUIMessageSender,
    )


# =============================================================================
# Agent Converters
# =============================================================================

def _convert_agent_state(state: "AgentState") -> "TUIAgentStatus":
    """Convert AgentState enum to TUIAgentStatus enum."""
    from agents.base import AgentState
    from .display_models import TUIAgentStatus
    
    mapping = {
        AgentState.UNINITIALIZED: TUIAgentStatus.UNINITIALIZED,
        AgentState.INITIALIZING: TUIAgentStatus.INITIALIZING,
        AgentState.IDLE: TUIAgentStatus.IDLE,
        AgentState.BUSY: TUIAgentStatus.BUSY,
        AgentState.PAUSED: TUIAgentStatus.PAUSED,
        AgentState.ERROR: TUIAgentStatus.ERROR,
        AgentState.SHUTDOWN: TUIAgentStatus.SHUTDOWN,
        AgentState.CHECKPOINTING: TUIAgentStatus.CHECKPOINTING,
        AgentState.RESTORING: TUIAgentStatus.RESTORING,
    }
    return mapping.get(state, TUIAgentStatus.UNINITIALIZED)


def convert_agent_to_tui(agent: "BaseAgent") -> "TUIAgent":
    """
    Convert a BaseAgent to a TUIAgent display model.
    
    Args:
        agent: The agent to convert
        
    Returns:
        TUIAgent: The display model
    """
    from agents.base import BaseAgent
    from .display_models import TUIAgent
    
    if not isinstance(agent, BaseAgent):
        raise TypeError(f"Expected BaseAgent, got {type(agent)}")
    
    # Get current task info
    current_task_id = None
    current_task_description = None
    current_task_progress = 0.0
    
    if agent._active_tasks:
        for task_id, context in agent._active_tasks.items():
            current_task_id = task_id
            # Get description from user_request or metadata
            current_task_description = context.user_request or context.metadata.get("description", "") or ""
            # TODO: Get progress from context if available
            break
    
    # Get capabilities
    capabilities = []
    if hasattr(agent, 'capabilities'):
        capabilities = [cap.name for cap in agent.capabilities]
    elif hasattr(agent, '_runtime_config') and agent._runtime_config:
        capabilities = [cap.name for cap in agent._runtime_config.capabilities]
    
    # Get metrics from agent status
    tasks_completed = 0
    tasks_failed = 0
    tasks_active = len(agent._active_tasks)
    avg_execution_time = 0.0
    
    if hasattr(agent, '_status') and agent._status:
        tasks_completed = agent._status.task_count
        tasks_failed = agent._status.error_count
        tasks_active = agent._status.active_tasks
    
    return TUIAgent(
        name=agent.name,
        agent_id=agent.agent_id,
        description=agent.description or "",
        status=_convert_agent_state(agent.state),
        tasks_completed=tasks_completed,
        tasks_failed=tasks_failed,
        tasks_active=tasks_active,
        avg_execution_time=avg_execution_time,
        capabilities=capabilities,
        current_task_id=current_task_id,
        current_task_description=current_task_description,
        current_task_progress=current_task_progress,
        created_at=getattr(agent, '_created_at', None),
        last_activity=datetime.utcnow(),
    )


def convert_agent_status_to_tui(
    name: str,
    agent_id: str,
    status: "AgentStatus",
    capabilities: List[str],
    description: str = "",
) -> "TUIAgent":
    """
    Convert agent status data to TUIAgent.
    
    Useful when we only have status data without the full agent object.
    """
    from .display_models import TUIAgent
    
    return TUIAgent(
        name=name,
        agent_id=agent_id,
        description=description,
        status=_convert_agent_state(status.state),
        tasks_completed=status.task_count,
        tasks_failed=status.error_count,
        tasks_active=status.active_tasks,
        capabilities=capabilities,
        last_activity=status.timestamp,
    )


# =============================================================================
# Task Converters
# =============================================================================

def _convert_task_status(status: str) -> "TUITaskStatus":
    """Convert string status to TUITaskStatus enum."""
    from .display_models import TUITaskStatus
    
    mapping = {
        "pending": TUITaskStatus.PENDING,
        "assigned": TUITaskStatus.ASSIGNED,
        "running": TUITaskStatus.RUNNING,
        "completed": TUITaskStatus.COMPLETED,
        "failed": TUITaskStatus.FAILED,
        "cancelled": TUITaskStatus.CANCELLED,
        "retrying": TUITaskStatus.RETRYING,
        "timeout": TUITaskStatus.TIMEOUT,
    }
    return mapping.get(status.lower(), TUITaskStatus.PENDING)


def _get_priority_value(priority: str) -> int:
    """Get numeric priority value."""
    priority_map = {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "low": 1,
    }
    return priority_map.get(priority.lower(), 2)


def convert_task_context_to_tui(context: "TaskContext") -> "TUITask":
    """
    Convert a TaskContext to a TUITask.
    
    Args:
        context: The task context to convert
        
    Returns:
        TUITask: The display model
    """
    from .display_models import TUITask
    
    # TaskContext doesn't have a 'task' attribute - use user_request for description
    description = context.user_request or context.metadata.get("description", "") or ""
    # Try to extract type from metadata or use a default
    task_type = context.metadata.get("type", "") or ""
    
    return TUITask(
        task_id=context.task_id,
        description=description,
        task_type=task_type,
        status=_convert_task_status(context.status.value if hasattr(context.status, 'value') else str(context.status)),
        assigned_agent=context.agent_name if hasattr(context, 'agent_name') else None,
        assignment_id=context.assignment_id if hasattr(context, 'assignment_id') else None,
        progress=context.progress if hasattr(context, 'progress') else 0.0,
        priority=context.metadata.get("priority", "medium"),
        priority_value=_get_priority_value(context.metadata.get("priority", "medium")),
        created_at=context.created_at,
        started_at=context.started_at,
        completed_at=context.completed_at,
        workflow_id=context.workflow_id if hasattr(context, 'workflow_id') else None,
        parent_task_id=context.parent_task_id if hasattr(context, 'parent_task_id') else None,
    )


def convert_task_dict_to_tui(
    task: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> "TUITask":
    """
    Convert a task dictionary to a TUITask.
    
    Args:
        task: The task dictionary
        context: Optional context dictionary
        
    Returns:
        TUITask: The display model
    """
    from .display_models import TUITask
    
    # Extract from context if available
    if context:
        task = {**task, **context}
    
    return TUITask(
        task_id=task.get("task_id", str(uuid.uuid4())),
        description=task.get("description", ""),
        task_type=task.get("type", task.get("task_type", "")),
        status=_convert_task_status(task.get("status", "pending")),
        assigned_agent=task.get("assigned_agent", task.get("agent_name")),
        progress=task.get("progress", 0.0),
        priority=task.get("priority", "medium"),
        priority_value=_get_priority_value(task.get("priority", "medium")),
        created_at=task.get("created_at"),
        started_at=task.get("started_at"),
        completed_at=task.get("completed_at"),
        result=task.get("result"),
        error=task.get("error"),
        workflow_id=task.get("workflow_id"),
        parent_task_id=task.get("parent_task_id"),
    )


def convert_task_assignment_to_tui(assignment: "TaskAssignment") -> "TUITask":
    """
    Convert a TaskAssignment to a TUITask.
    
    Args:
        assignment: The task assignment to convert
        
    Returns:
        TUITask: The display model
    """
    from .display_models import TUITask
    
    task_data = assignment.task or {}
    
    return TUITask(
        task_id=assignment.task_id,
        description=task_data.get("description", ""),
        task_type=task_data.get("type", ""),
        status=_convert_task_status(assignment.status),
        assigned_agent=assignment.agent_name,
        assignment_id=assignment.assignment_id,
        progress=0.0,  # TODO: Get progress from context
        priority=assignment.priority.level if hasattr(assignment.priority, 'level') else "medium",
        priority_value=assignment.priority.value if hasattr(assignment.priority, 'value') else 2,
        created_at=assignment.created_at,
        assigned_at=assignment.assigned_at,
        completed_at=assignment.completed_at,
        result=assignment.result,
        error=assignment.error,
        retry_count=assignment.retry_count,
    )


# =============================================================================
# Workflow Converters
# =============================================================================

def _convert_workflow_status(status: str) -> "TUIWorkflowStatus":
    """Convert string status to TUIWorkflowStatus enum."""
    from .display_models import TUIWorkflowStatus
    
    mapping = {
        "pending": TUIWorkflowStatus.PENDING,
        "running": TUIWorkflowStatus.RUNNING,
        "paused": TUIWorkflowStatus.PAUSED,
        "completed": TUIWorkflowStatus.COMPLETED,
        "failed": TUIWorkflowStatus.FAILED,
        "cancelled": TUIWorkflowStatus.CANCELLED,
    }
    return mapping.get(status.lower(), TUIWorkflowStatus.PENDING)


def convert_workflow_step_to_tui(step: "WorkflowStep") -> "TUIWorkflowStep":
    """
    Convert a WorkflowStep to a TUIWorkflowStep.
    
    Args:
        step: The workflow step to convert
        
    Returns:
        TUIWorkflowStep: The display model
    """
    from .display_models import TUIWorkflowStep
    
    return TUIWorkflowStep(
        step_id=step.step_id,
        name=step.name,
        description=step.description,
        agent_name=step.agent_name,
        task_type=step.task_type,
        status=_convert_task_status(step.status),
        progress=step.progress if hasattr(step, 'progress') else 0.0,
        depends_on=step.depends_on,
        result=step.result,
        error=step.error,
        started_at=step.start_time,
        completed_at=step.end_time,
    )


def convert_workflow_to_tui(workflow: "WorkflowDefinition") -> "TUIWorkflow":
    """
    Convert a WorkflowDefinition to a TUIWorkflow.
    
    Args:
        workflow: The workflow definition to convert
        
    Returns:
        TUIWorkflow: The display model
    """
    from .display_models import TUIWorkflow
    
    steps = [convert_workflow_step_to_tui(step) for step in workflow.steps]
    
    # Calculate progress
    total_steps = len(workflow.steps)
    completed_steps = len(workflow.completed_steps)
    failed_steps = len(workflow.failed_steps)
    progress = workflow.progress if hasattr(workflow, 'progress') else 0.0
    
    return TUIWorkflow(
        workflow_id=workflow.workflow_id,
        name=workflow.name,
        description=workflow.description,
        status=_convert_workflow_status(workflow.status),
        progress=progress,
        completed_steps=completed_steps,
        total_steps=total_steps,
        failed_steps=failed_steps,
        steps=steps,
        step_order=[step.step_id for step in workflow.steps],
        current_step_id=workflow.current_step,
        created_at=workflow.start_time,
        started_at=workflow.start_time,
        completed_at=workflow.end_time,
        results=workflow.results,
        errors=workflow.errors,
    )


def convert_workflow_dict_to_tui(
    workflow_data: Dict[str, Any],
    steps_data: List[Dict[str, Any]],
) -> "TUIWorkflow":
    """
    Convert workflow data to TUIWorkflow.
    
    Args:
        workflow_data: Workflow metadata dictionary
        steps_data: List of step dictionaries
        
    Returns:
        TUIWorkflow: The display model
    """
    from .display_models import TUIWorkflow, TUIWorkflowStep
    
    steps = []
    for step_data in steps_data:
        step = TUIWorkflowStep(
            step_id=step_data.get("step_id", ""),
            name=step_data.get("name", ""),
            description=step_data.get("description", ""),
            agent_name=step_data.get("agent_name", ""),
            task_type=step_data.get("task_type", ""),
            status=_convert_task_status(step_data.get("status", "pending")),
            progress=step_data.get("progress", 0.0),
            depends_on=step_data.get("depends_on", []),
            result=step_data.get("result"),
            error=step_data.get("error"),
        )
        steps.append(step)
    
    total_steps = len(steps)
    completed_steps = sum(1 for s in steps if s.status == "completed")
    failed_steps = sum(1 for s in steps if s.status == "failed")
    
    return TUIWorkflow(
        workflow_id=workflow_data.get("workflow_id", ""),
        name=workflow_data.get("name", ""),
        description=workflow_data.get("description", ""),
        status=_convert_workflow_status(workflow_data.get("status", "pending")),
        progress=workflow_data.get("progress", completed_steps / total_steps if total_steps > 0 else 0.0),
        completed_steps=completed_steps,
        total_steps=total_steps,
        failed_steps=failed_steps,
        steps=steps,
        step_order=workflow_data.get("step_order", [s.step_id for s in steps]),
        current_step_id=workflow_data.get("current_step_id"),
        results=workflow_data.get("results", {}),
        errors=workflow_data.get("errors", {}),
    )


# =============================================================================
# Message Converters
# =============================================================================

def _convert_message_sender(sender: str) -> "TUIMessageSender":
    """Convert sender string to TUIMessageSender enum."""
    from .display_models import TUIMessageSender
    
    mapping = {
        "user": TUIMessageSender.USER,
        "system": TUIMessageSender.SYSTEM,
        "god": TUIMessageSender.GOD_AGENT,
        "god_agent": TUIMessageSender.GOD_AGENT,
    }
    return mapping.get(sender.lower(), TUIMessageSender.AGENT)


def _convert_message_type(msg_type: str) -> "TUIMessageType":
    """Convert message type string to TUIMessageType enum."""
    from .display_models import TUIMessageType
    
    mapping = {
        "text": TUIMessageType.TEXT,
        "command": TUIMessageType.COMMAND,
        "task": TUIMessageType.TASK,
        "result": TUIMessageType.RESULT,
        "error": TUIMessageType.ERROR,
        "warning": TUIMessageType.WARNING,
        "info": TUIMessageType.INFO,
        "debug": TUIMessageType.DEBUG,
    }
    return mapping.get(msg_type.lower(), TUIMessageType.TEXT)


def convert_command_to_tui_message(
    command: "Command",
    sender: str = "user",
) -> "TUIMessage":
    """
    Convert an ACI Command to a TUIMessage.
    
    Args:
        command: The command to convert
        sender: The sender name
        
    Returns:
        TUIMessage: The display model
    """
    from .display_models import TUIMessage, TUIMessageType
    
    msg_type = TUIMessageType.COMMAND
    if command.command_type == "task_assignment":
        msg_type = TUIMessageType.TASK
    elif command.command_type == "task_result":
        msg_type = TUIMessageType.RESULT
    
    return TUIMessage(
        message_id=str(uuid.uuid4()),
        sender=_convert_message_sender(sender),
        sender_name=sender,
        content=str(command),
        message_type=msg_type,
        task_id=command.task_id if hasattr(command, 'task_id') else None,
        data=command.model_dump() if hasattr(command, 'model_dump') else command.dict(),
    )


def convert_message_to_tui(
    content: str,
    sender: str = "user",
    msg_type: str = "text",
    task_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    agent_name: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> "TUIMessage":
    """
    Create a TUIMessage from basic data.
    
    Args:
        content: Message content
        sender: Sender name or type
        msg_type: Message type
        task_id: Related task ID
        workflow_id: Related workflow ID
        agent_name: Related agent name
        data: Additional data
        
    Returns:
        TUIMessage: The display model
    """
    from .display_models import TUIMessage
    
    is_agent = sender != "user" and sender != "system" and sender != "god"
    sender_enum = _convert_message_sender(sender)
    
    if is_agent and sender_enum == "agent":
        # Keep the agent name
        pass
    elif sender == "god":
        sender_enum = "god_agent"
    
    return TUIMessage(
        message_id=str(uuid.uuid4()),
        sender=sender_enum,
        sender_name=sender,
        content=content,
        message_type=_convert_message_type(msg_type),
        task_id=task_id,
        workflow_id=workflow_id,
        agent_name=agent_name,
        data=data,
    )


# =============================================================================
# Batch Converters
# =============================================================================

def convert_agents_to_tui(agents: List["BaseAgent"]) -> List["TUIAgent"]:
    """Convert a list of agents to TUIAgent list."""
    return [convert_agent_to_tui(agent) for agent in agents]


def convert_tasks_to_tui(tasks: List[Dict[str, Any]]) -> List["TUITask"]:
    """Convert a list of task dictionaries to TUITask list."""
    return [convert_task_dict_to_tui(task) for task in tasks]


def convert_workflows_to_tui(workflows: List["WorkflowDefinition"]) -> List["TUIWorkflow"]:
    """Convert a list of workflow definitions to TUIWorkflow list."""
    return [convert_workflow_to_tui(wf) for wf in workflows]


def convert_task_contexts_to_tui(contexts: List["TaskContext"]) -> List["TUITask"]:
    """Convert a list of TaskContext to TUITask list."""
    return [convert_task_context_to_tui(ctx) for ctx in contexts]


# =============================================================================
# God Agent Specific Converters
# =============================================================================

def convert_god_status_to_metrics(god_agent: "GodAgent") -> Dict[str, Any]:
    """
    Convert GodAgent status to metrics dictionary.
    
    Args:
        god_agent: The God Agent instance
        
    Returns:
        Dictionary of metrics
    """
    status = god_agent.get_status() if hasattr(god_agent, 'get_status') else {}
    
    return {
        "registered_agents": status.get("registered_agents", 0),
        "active_assignments": status.get("active_assignments", 0),
        "active_workflows": status.get("active_workflows", 0),
        "decomposition_strategy": status.get("decomposition_strategy", "unknown"),
        "routing_strategy": status.get("routing_strategy", "unknown"),
        "max_concurrent_tasks": status.get("max_concurrent_tasks", 0),
    }


def create_task_submission_message(
    task_description: str,
    task_id: str,
) -> "TUIMessage":
    """Create a message for task submission."""
    from .display_models import TUIMessage, TUIMessageSender, TUIMessageType
    
    return TUIMessage(
        message_id=str(uuid.uuid4()),
        sender=TUIMessageSender.USER,
        sender_name="User",
        content=task_description,
        message_type=TUIMessageType.TASK,
        task_id=task_id,
    )


def create_agent_response_message(
    agent_name: str,
    content: str,
    task_id: Optional[str] = None,
    msg_type: str = "text",
) -> "TUIMessage":
    """Create a message from an agent."""
    from .display_models import TUIMessage, TUIMessageSender, TUIMessageType
    
    return TUIMessage(
        message_id=str(uuid.uuid4()),
        sender=TUIMessageSender.AGENT,
        sender_name=agent_name,
        content=content,
        message_type=_convert_message_type(msg_type),
        task_id=task_id,
        agent_name=agent_name,
    )


def create_god_response_message(
    content: str,
    task_id: Optional[str] = None,
    msg_type: str = "text",
) -> "TUIMessage":
    """Create a message from the God Agent."""
    from .display_models import TUIMessage, TUIMessageSender, TUIMessageType
    
    return TUIMessage(
        message_id=str(uuid.uuid4()),
        sender=TUIMessageSender.GOD_AGENT,
        sender_name="God",
        content=content,
        message_type=_convert_message_type(msg_type),
        task_id=task_id,
    )


def create_error_message(
    content: str,
    task_id: Optional[str] = None,
    agent_name: Optional[str] = None,
) -> "TUIMessage":
    """Create an error message."""
    from .display_models import TUIMessage, TUIMessageSender, TUIMessageType
    
    return TUIMessage(
        message_id=str(uuid.uuid4()),
        sender=TUIMessageSender.SYSTEM,
        sender_name="System",
        content=content,
        message_type=TUIMessageType.ERROR,
        task_id=task_id,
        agent_name=agent_name,
    )
