"""
TUI Events Module.

Contains event definitions for the TUI.
"""

# Import events from widgets
from tui.widgets.agent_list import AgentSelected
from tui.widgets.task_list import TaskSelected
from tui.widgets.chat_input import ChatInputSubmitted
from tui.widgets.status_bar import StatusUpdate

__all__ = [
    "AgentSelected",
    "TaskSelected", 
    "ChatInputSubmitted",
    "StatusUpdate",
]
