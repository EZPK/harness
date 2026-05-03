"""
Tasks Screen for TUI.

Displays the list of tasks with filtering and details.
"""

from typing import List, Optional

try:
    from textual.app import ComposeResult
    from textual.containers import Container
    from textual.reactive import reactive
    from textual.widget import Widget
    from textual.widgets import Label
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False

import asyncio

from agents.god.agent import GodAgent
from tui.controller import TUIController
from tui.models import TUITask
from tui.widgets.task_list import TaskList
from tui.widgets.task_card import TaskCard


class TasksScreen(Widget):
    """
    Tasks widget showing all tasks.
    
    Features:
    - List of tasks with filtering
    - Task details panel
    - Real-time updates
    """
    
    DEFAULT_CSS = """
    TasksScreen {
        layout: horizontal;
        width: 100%;
        height: 100%;
        background: #1e1e1e;
    }
    
    TasksScreen .list-container {
        width: 60%;
        height: 100%;
        background: #121212;
    }
    
    TasksScreen .details-container {
        width: 40%;
        height: 100%;
        background: #2d2d2d;
        padding: 1;
        overflow-y: auto;
    }
    
    TasksScreen TaskList {
        width: 100%;
        height: 100%;
    }
    
    TasksScreen TaskCard {
        width: 100%;
        height: auto;
    }
    
    TasksScreen .details-header {
        width: 100%;
        height: auto;
        dock: top;
        text-style: bold;
        padding-bottom: 1;
        border-bottom: solid #1e88e5;
    }
    
    TasksScreen .details-content {
        width: 100%;
        height: 1fr;
    }
    
    TasksScreen .no-selection {
        color: #9e9e9e;
        text-style: italic;
        align: center middle;
        height: 100%;
    }
    """
    
    def __init__(
        self,
        god_agent: GodAgent,
        controller: TUIController,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self.god = god_agent
        self.controller = controller
        
        # State
        self._tasks: List[TUITask] = []
        self._selected_task: Optional[TUITask] = None
    
    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        # List container
        with Container(classes="list-container"):
            yield TaskList(
                tasks=self._tasks,
                on_task_selected=self._on_task_selected,
                id="task-list"
            )
        
        # Details container
        with Container(classes="details-container"):
            yield Label("Task Details", classes="details-header")
            with Container(classes="details-content", id="task-details"):
                yield Label("Select a task to view details", classes="no-selection")
    
    def on_mount(self) -> None:
        """Called after the widget is mounted."""
        # Register for task updates
        self.controller.on_tasks_updated(self._on_tasks_updated)
        
        # Load initial tasks
        asyncio.create_task(self._load_initial_data())
    
    def on_unmount(self) -> None:
        """Called when the widget is unmounted."""
        # Unregister from updates
        try:
            self.controller._on_tasks_updated.remove(self._on_tasks_updated)
        except (ValueError, AttributeError):
            pass
    
    async def _load_initial_data(self) -> None:
        """Load initial data."""
        self._tasks = await self.controller.get_tasks()
        self._update_task_list()
    
    def _on_tasks_updated(self, tasks: List[TUITask]) -> None:
        """Handle task updates."""
        self._tasks = tasks
        self._update_task_list()
    
    def _update_task_list(self) -> None:
        """Update the task list."""
        task_list = self.query_one("#task-list", TaskList)
        if task_list:
            task_list.set_tasks(self._tasks)
    
    def _on_task_selected(self, task: TUITask) -> None:
        """Handle task selection."""
        self._selected_task = task
        self._update_task_details()
    
    def _update_task_details(self) -> None:
        """Update the task details panel."""
        details_container = self.query_one("#task-details", Container)
        if not details_container:
            return
        
        # Clear existing details
        for child in list(details_container.children):
            child.remove()
        
        if self._selected_task:
            task = self._selected_task
            
            # Add task card
            card = TaskCard(task=task, classes="task-card")
            details_container.mount(card)
            
            # Add additional details
            details_container.mount(Label(""))
            details_container.mount(Label(f"Task ID: {task.task_id}"))
            details_container.mount(Label(f"Type: {task.task_type}"))
            details_container.mount(Label(f"Status: {task.status.value}"))
            details_container.mount(Label(f"Priority: {task.priority}"))
            
            # Progress
            progress_percent = int(task.progress * 100)
            details_container.mount(Label(f"Progress: {progress_percent}%"))
            
            # Timestamps
            if task.created_at:
                details_container.mount(Label(f"Created: {task.created_at.strftime('%Y-%m-%d %H:%M:%S')}"))
            if task.started_at:
                details_container.mount(Label(f"Started: {task.started_at.strftime('%Y-%m-%d %H:%M:%S')}"))
            if task.completed_at:
                details_container.mount(Label(f"Completed: {task.completed_at.strftime('%Y-%m-%d %H:%M:%S')}"))
            
            # Result/Error
            if task.result:
                details_container.mount(Label(""))
                details_container.mount(Label("[bold]Result[/bold]"))
                details_container.mount(Label(str(task.result)))
            
            if task.error:
                details_container.mount(Label(""))
                details_container.mount(Label("[bold red]Error[/bold red]"))
                details_container.mount(Label(str(task.error)))
            
            # Subtasks
            if task.subtasks:
                details_container.mount(Label(""))
                details_container.mount(Label("[bold]Subtasks[/bold]"))
                for i, subtask_id in enumerate(task.subtasks):
                    subtask_status = task.subtask_statuses.get(subtask_id, "unknown")
                    details_container.mount(Label(f"  {i+1}. {subtask_id}: {subtask_status.value}"))
        else:
            details_container.mount(Label("Select a task to view details", classes="no-selection"))



