"""
TUI Screens Module.

Contains all the screens for the Textual application.
Note: Screens require Textual to be installed.
"""

# Check if Textual is available
try:
    from .chat_screen import ChatScreen
    from .agents_screen import AgentsScreen
    from .tasks_screen import TasksScreen
    from .workflows_screen import WorkflowsScreen
    from .metrics_screen import MetricsScreen
    from .config_screen import ConfigScreen
    
    __all__ = [
        "ChatScreen",
        "AgentsScreen", 
        "TasksScreen",
        "WorkflowsScreen",
        "MetricsScreen",
        "ConfigScreen",
    ]
except ImportError:
    # Textual not available - provide None for all screens
    __all__ = []
