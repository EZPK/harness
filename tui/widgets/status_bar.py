"""
Status Bar Widget for TUI.

Displays global status information at the bottom of the screen.
"""

from typing import Optional

# Only import Textual components if available
HAS_TEXTUAL = False

try:
    from textual.app import ComposeResult
    from textual.containers import Container
    from textual.message import Message
    from textual.reactive import reactive
    from textual.widget import Widget
    from textual import events
    HAS_TEXTUAL = True
except ImportError:
    # Create dummy classes for when Textual is not installed
    class ComposeResult: pass
    class Container: pass
    class Message: pass
    class reactive: pass
    class Widget: pass
    class events: pass

from tui.models import TUIMetrics, TUIDashboardState


if HAS_TEXTUAL:
    class StatusBar(Widget):
        """
        Status bar widget that displays global information.
        
        Shows: God status, agent count, task count, resource usage.
        """
        
        DEFAULT_CSS = """
        StatusBar {
            dock: bottom;
            height: 1;
            width: 100%;
            background: #1e1e1e;
            color: #e0e0e0;
            text-style: bold;
        }
        """
        
        # Reactive properties
        god_status: str = reactive("IDLE")
        god_color: str = reactive("green")
        registered_agents: int = reactive(0)
        active_agents: int = reactive(0)
        total_tasks: int = reactive(0)
        active_tasks: int = reactive(0)
        total_workflows: int = reactive(0)
        active_workflows: int = reactive(0)
        cpu_usage: float = reactive(0.0)
        memory_usage: str = reactive("0MB")
        
        def __init__(
            self,
            name: Optional[str] = None,
            id: Optional[str] = None,
            classes: Optional[str] = None,
        ):
            super().__init__(name=name, id=id, classes=classes)
            self._metrics: Optional[TUIMetrics] = None
        
        def compose(self) -> ComposeResult:
            yield from super().compose()
        
        def render(self) -> str:
            """Render the status bar."""
            parts = []
            
            # God status
            parts.append(f"[bold {self.god_color}][God:{self.god_status}][/]")
            
            # Agents
            parts.append(f"[bold white][Agents:{self.registered_agents}/{self.active_agents} active][/]")
            
            # Tasks
            parts.append(f"[bold white][Tasks:{self.active_tasks} running/{self.total_tasks} total][/]")
            
            # Workflows
            parts.append(f"[bold white][Workflows:{self.active_workflows}/{self.total_workflows}][/]")
            
            # Resources
            if self.cpu_usage > 0:
                parts.append(f"[bold white][CPU:{self.cpu_usage:.0f}%][/]")
            if self.memory_usage:
                parts.append(f"[bold white][MEM:{self.memory_usage}][/]")
            
            return " ".join(parts)
        
        def update_from_metrics(self, metrics: TUIMetrics) -> None:
            """Update status bar from metrics."""
            self._metrics = metrics
            self.god_status = "IDLE"  # TODO: Get from God Agent
            self.registered_agents = metrics.total_agents
            self.active_agents = metrics.active_agents
            self.total_tasks = metrics.total_tasks
            self.active_tasks = metrics.active_tasks
            self.total_workflows = metrics.total_workflows
            self.active_workflows = metrics.active_workflows
        
        def update_from_dashboard(self, dashboard: TUIDashboardState) -> None:
            """Update status bar from dashboard state."""
            self.update_from_metrics(dashboard.metrics)
        
        def set_god_status(self, status: str, color: str = "green") -> None:
            """Set the God Agent status."""
            self.god_status = status
            self.god_color = color
        
        def set_resource_usage(self, cpu: float, memory: str) -> None:
            """Set resource usage."""
            self.cpu_usage = cpu
            self.memory_usage = memory

    class StatusUpdate(Message):
        """Message to update the status bar."""
        
        def __init__(
            self,
            god_status: Optional[str] = None,
            god_color: Optional[str] = None,
            registered_agents: Optional[int] = None,
            active_agents: Optional[int] = None,
            total_tasks: Optional[int] = None,
            active_tasks: Optional[int] = None,
            total_workflows: Optional[int] = None,
            active_workflows: Optional[int] = None,
        ):
            self.god_status = god_status
            self.god_color = god_color
            self.registered_agents = registered_agents
            self.active_agents = active_agents
            self.total_tasks = total_tasks
            self.active_tasks = active_tasks
            self.total_workflows = total_workflows
            self.active_workflows = active_workflows
            super().__init__()
else:
    # Dummy classes when Textual is not available
    StatusBar = None
    StatusUpdate = None
