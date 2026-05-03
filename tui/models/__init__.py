"""
TUI Models Module.

Contains display models and converters for the TUI.
"""

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
    TUIMetrics,
    TUIDashboardState,
)
from .converters import (
    convert_agent_to_tui,
    convert_task_dict_to_tui,
    convert_task_context_to_tui,
    convert_task_assignment_to_tui,
    convert_workflow_to_tui,
    convert_workflow_step_to_tui,
    convert_workflow_dict_to_tui,
    convert_message_to_tui,
    convert_command_to_tui_message,
    convert_agents_to_tui,
    convert_tasks_to_tui,
    convert_workflows_to_tui,
    convert_task_contexts_to_tui,
    convert_god_status_to_metrics,
    create_task_submission_message,
    create_agent_response_message,
    create_god_response_message,
    create_error_message,
)

__all__ = [
    # Display Models
    "TUIAgent",
    "TUIAgentStatus",
    "TUITask",
    "TUITaskStatus",
    "TUIWorkflow",
    "TUIWorkflowStatus",
    "TUIWorkflowStep",
    "TUIMessage",
    "TUIMessageType",
    "TUIMessageSender",
    "TUIMetrics",
    "TUIDashboardState",
    # Converters
    "convert_agent_to_tui",
    "convert_task_dict_to_tui",
    "convert_task_context_to_tui",
    "convert_task_assignment_to_tui",
    "convert_workflow_to_tui",
    "convert_workflow_step_to_tui",
    "convert_workflow_dict_to_tui",
    "convert_message_to_tui",
    "convert_command_to_tui_message",
    "convert_agents_to_tui",
    "convert_tasks_to_tui",
    "convert_workflows_to_tui",
    "convert_task_contexts_to_tui",
    "convert_god_status_to_metrics",
    # Factory functions
    "create_task_submission_message",
    "create_agent_response_message",
    "create_god_response_message",
    "create_error_message",
]
