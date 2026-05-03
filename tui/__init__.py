"""
TUI Module for Harness Agentic Framework.

This module provides a Textual-based Terminal User Interface for interacting
with the God Agent and visualizing agent work.
"""

# Import models (always available)
from .models.display_models import (
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
from .models.converters import (
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

# Import app and controller (may not be available during early development)
try:
    from .app import HarnessTUIApp
    from .controller import TUIController
    HAS_APP = True
except ImportError:
    HAS_APP = False
    HarnessTUIApp = None
    TUIController = None

__all__ = [
    # Models
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
    # App (if available)
    "HarnessTUIApp",
    "TUIController",
]
