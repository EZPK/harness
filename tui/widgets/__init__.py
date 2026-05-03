"""
TUI Widgets Module.

Contains all custom Textual widgets for the TUI.
Note: Widgets require Textual to be installed.
"""

# Check if Textual is available
try:
    from .status_bar import StatusBar, StatusUpdate
    from .agent_card import AgentCard
    from .agent_list import AgentList, AgentSelected
    from .task_card import TaskCard
    from .task_list import TaskList, TaskSelected
    from .metrics_chart import MetricsChart, SimpleMetricsChart
    from .chat_message import ChatMessage
    from .chat_input import ChatInput, ChatInputSubmitted
    from .workflow_tree import WorkflowTree, SimpleWorkflowTree
    from .provider_config_modal import ProviderConfigModal, ProviderConfigSave
    
    __all__ = [
        "StatusBar",
        "StatusUpdate",
        "AgentCard",
        "AgentList",
        "AgentSelected",
        "TaskCard",
        "TaskList",
        "TaskSelected",
        "MetricsChart",
        "SimpleMetricsChart",
        "ChatMessage",
        "ChatInput",
        "ChatInputSubmitted",
        "WorkflowTree",
        "SimpleWorkflowTree",
        "ProviderConfigModal",
        "ProviderConfigSave",
    ]
except ImportError:
    # Textual not available - provide None for all widgets
    __all__ = []
