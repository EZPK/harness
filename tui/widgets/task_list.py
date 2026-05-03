"""
Task List Widget for TUI.

Displays a scrollable list of tasks with filtering capabilities.
"""

from typing import List, Optional, Callable

try:
    from textual.app import ComposeResult
    from textual.containers import Container, ScrollableContainer
    from textual.message import Message
    from textual.reactive import reactive
    from textual.widget import Widget
    from textual.widgets import Label, Input, Button, OptionList
    from textual import events, on
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False

from tui.models import TUITask, TUITaskStatus
from .task_card import TaskCard


class TaskList(ScrollableContainer):
    """
    Scrollable list of tasks.
    
    Supports filtering by status, agent, and priority.
    """
    
    DEFAULT_CSS = """
    TaskList {
        width: 100%;
        height: 100%;
        background: #1e1e1e;
        padding: 1;
    }
    
    TaskList .filter-bar {
        height: 3;
        width: 100%;
        dock: top;
        background: #2d2d2d;
        padding: 0 1;
        layout: horizontal;
        
    }
    
    TaskList .tasks-container {
        width: 100%;
        height: 1fr;
        layout: vertical;
        
    }
    
    TaskList TaskCard {
        width: 100%;
        height: auto;
    }
    """
    
    # Tasks data
    tasks: List[TUITask] = reactive([], init=False)
    filtered_tasks: List[TUITask] = reactive([], init=False)
    
    # Filter state
    status_filter: str = reactive("all")
    agent_filter: str = reactive("")
    priority_filter: str = reactive("")
    search_filter: str = reactive("")
    
    # Selection
    selected_task: Optional[TUITask] = reactive(None, init=False)
    
    # Callbacks
    on_task_selected: Optional[Callable[[TUITask], None]] = None
    
    def __init__(
        self,
        tasks: Optional[List[TUITask]] = None,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
        on_task_selected: Optional[Callable[[TUITask], None]] = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        if tasks:
            self.tasks = tasks
        self.on_task_selected = on_task_selected
    
    def compose(self) -> ComposeResult:
        # Filter bar
        with Container(classes="filter-bar"):
            yield Label("Filter:", classes="filter-label")
            yield Input(
                placeholder="Search tasks...",
                classes="search-input",
                id="search-input"
            )
            yield Button("Status: All", id="status-filter", classes="filter-button")
            yield Button("Agent: All", id="agent-filter", classes="filter-button")
            yield Button("Priority: All", id="priority-filter", classes="filter-button")
            yield Button("Clear", id="clear-filter", classes="filter-button")
        
        # Tasks container
        with Container(classes="tasks-container", id="tasks-container"):
            for task in self.filtered_tasks:
                yield TaskCard(task=task, classes="task-card")
    
    def watch_tasks(self, tasks: List[TUITask]) -> None:
        """React to tasks list changes."""
        self._apply_filters()
    
    def watch_status_filter(self, status: str) -> None:
        """React to status filter changes."""
        self._apply_filters()
    
    def watch_agent_filter(self, agent: str) -> None:
        """React to agent filter changes."""
        self._apply_filters()
    
    def watch_priority_filter(self, priority: str) -> None:
        """React to priority filter changes."""
        self._apply_filters()
    
    def watch_search_filter(self, search: str) -> None:
        """React to search filter changes."""
        self._apply_filters()
    
    def _apply_filters(self) -> None:
        """Apply all filters to the tasks list."""
        filtered = self.tasks
        
        # Status filter
        if self.status_filter != "all":
            status = TUITaskStatus(self.status_filter.upper())
            filtered = [t for t in filtered if t.status == status]
        
        # Agent filter
        if self.agent_filter:
            filtered = [t for t in filtered if t.assigned_agent and self.agent_filter.lower() in t.assigned_agent.lower()]
        
        # Priority filter
        if self.priority_filter:
            filtered = [t for t in filtered if t.priority.lower() == self.priority_filter.lower()]
        
        # Search filter
        if self.search_filter:
            search = self.search_filter.lower()
            filtered = [
                t for t in filtered 
                if (search in t.description.lower() or
                    search in t.task_id.lower() or
                    search in t.task_type.lower() or
                    (t.assigned_agent and search in t.assigned_agent.lower()))
            ]
        
        self.filtered_tasks = filtered
        self._update_container()
    
    def _update_container(self) -> None:
        """Update the tasks container with filtered tasks."""
        container = self.query_one("#tasks-container", Container)
        if container:
            # Clear existing cards
            for child in container.children:
                child.remove()
            
            # Add new cards
            for task in self.filtered_tasks:
                card = TaskCard(task=task)
                card.on_click = lambda t=task: self._on_task_clicked(t)
                container.mount(card)
    
    def _on_task_clicked(self, task: TUITask) -> None:
        """Handle task click."""
        self.selected_task = task
        if self.on_task_selected:
            self.on_task_selected(task)
    
    def set_tasks(self, tasks: List[TUITask]) -> None:
        """Set the list of tasks."""
        self.tasks = tasks
    
    def add_task(self, task: TUITask) -> None:
        """Add a task to the list."""
        self.tasks = self.tasks + [task]
    
    def remove_task(self, task_id: str) -> None:
        """Remove a task from the list."""
        self.tasks = [t for t in self.tasks if t.task_id != task_id]
    
    def set_status_filter(self, status: str) -> None:
        """Set the status filter."""
        self.status_filter = status
    
    def set_agent_filter(self, agent: str) -> None:
        """Set the agent filter."""
        self.agent_filter = agent
    
    def set_priority_filter(self, priority: str) -> None:
        """Set the priority filter."""
        self.priority_filter = priority
    
    def set_search_filter(self, search: str) -> None:
        """Set the search filter."""
        self.search_filter = search
    
    def clear_filters(self) -> None:
        """Clear all filters."""
        self.status_filter = "all"
        self.agent_filter = ""
        self.priority_filter = ""
        self.search_filter = ""
    
    @on(Input.Changed, "#search-input")
    def on_search_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        self.search_filter = event.value
    
    @on(Button.Pressed, "#status-filter")
    def on_status_filter_pressed(self, event: Button.Pressed) -> None:
        """Handle status filter button press."""
        statuses = ["all", "pending", "assigned", "running", "completed", "failed"]
        current = self.status_filter
        next_idx = (statuses.index(current) + 1) % len(statuses)
        self.status_filter = statuses[next_idx]
        event.button.label = f"Status: {self.status_filter}"
    
    @on(Button.Pressed, "#priority-filter")
    def on_priority_filter_pressed(self, event: Button.Pressed) -> None:
        """Handle priority filter button press."""
        priorities = ["all", "critical", "high", "medium", "low"]
        current = self.priority_filter
        next_idx = (priorities.index(current) + 1) % len(priorities)
        self.priority_filter = priorities[next_idx]
        event.button.label = f"Priority: {self.priority_filter}"
    
    @on(Button.Pressed, "#clear-filter")
    def on_clear_filter_pressed(self, event: Button.Pressed) -> None:
        """Handle clear filter button press."""
        self.clear_filters()
        self.query_one("#search-input", Input).value = ""


class TaskSelected(Message):
    """Message emitted when a task is selected."""
    
    def __init__(self, task: TUITask):
        self.task = task
        super().__init__()
