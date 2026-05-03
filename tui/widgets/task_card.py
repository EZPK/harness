"""
Task Card Widget for TUI.

Displays information about a single task in a card format.
"""

from typing import Optional

try:
    from textual.app import ComposeResult
    from textual.containers import Container
    from textual.reactive import reactive
    from textual.widget import Widget
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False

from tui.models import TUITask, TUITaskStatus


class TaskCard(Widget):
    """
    Card widget that displays task information.
    
    Shows: ID, description, status, agent, progress, priority.
    """
    
    DEFAULT_CSS = """
    TaskCard {
        width: 100%;
        height: auto;
        border: left #1e88e5;
        background: #2d2d2d;
        padding: 1 2;
        
        &.selected {
            border: left #ffc107;
            background: #3d3d3d;
        }
        
        &.completed {
            border: left #4caf50;
            opacity: 0.7;
        }
        
        &.failed {
            border: left #f44336;
        }
        
        &.running {
            border: left #ff9800;
        }
    }
    """
    
    DEFAULT_CLASSES = "task-card"
    
    # Task data
    task: Optional[TUITask] = reactive(None, init=False)
    selected: bool = reactive(False, init=False)
    
    def __init__(
        self,
        task: Optional[TUITask] = None,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self.task = task
    
    def compose(self) -> ComposeResult:
        yield from super().compose()
    
    def watch_task(self, task: Optional[TUITask]) -> None:
        """React to task changes."""
        if task:
            # Update classes based on status
            self.set_class(False, "completed", "failed", "running")
            if task.status == TUITaskStatus.COMPLETED:
                self.set_class(True, "completed")
            elif task.status == TUITaskStatus.FAILED:
                self.set_class(True, "failed")
            elif task.status == TUITaskStatus.RUNNING:
                self.set_class(True, "running")
    
    def watch_selected(self, selected: bool) -> None:
        """React to selection changes."""
        self.set_class(selected, "selected")
    
    def render(self) -> str:
        """Render the task card."""
        if not self.task:
            return "[dim]No task[/]"
        
        t = self.task
        lines = []
        
        # Header: Priority + Status icon + Description
        priority_icon = t.priority_icon
        status_icon = t.status_icon
        status_color = t.status_color
        
        header = f"[{status_color}]{status_icon}[/{status_color}] [{priority_icon}] [bold white]{t.description[:60]}[/]"
        if len(t.description) > 60:
            header += "..."
        lines.append(header)
        
        # Body
        lines.append(f"  ID: [dim]{t.task_id}[/] | Type: [dim]{t.task_type}[/]")
        
        # Agent and progress
        if t.assigned_agent:
            progress = int(t.progress * 100)
            lines.append(f"  Agent: [{t.status_color}]{t.assigned_agent}[/] | Progress: {progress}%")
        else:
            lines.append(f"  Agent: [dim]Not assigned[/]")
        
        # Subtasks
        if t.subtasks:
            completed = sum(1 for s in t.subtask_statuses.values() if s == TUITaskStatus.COMPLETED)
            total = len(t.subtasks)
            lines.append(f"  Subtasks: {completed}/{total}")
        
        # Timestamps
        if t.created_at:
            lines.append(f"  Created: [dim]{t.created_at.strftime('%H:%M:%S')}[/]")
        
        return "\n".join(lines)
    
    def set_task(self, task: TUITask) -> None:
        """Set the task to display."""
        self.task = task
    
    def select(self) -> None:
        """Select this card."""
        self.selected = True
    
    def deselect(self) -> None:
        """Deselect this card."""
        self.selected = False
    
    def toggle_select(self) -> None:
        """Toggle selection."""
        self.selected = not self.selected
