"""
Agent Card Widget for TUI.

Displays information about a single agent in a card format.
"""

from typing import Optional

from tui._textual_compat import (
    Widget, ComposeResult, reactive, HAS_TEXTUAL, Container
)
from tui.models import TUIAgent, TUIAgentStatus


if HAS_TEXTUAL:
    class AgentCard(Widget):
        """
        Card widget that displays agent information.
        
        Shows: name, status, capabilities, metrics.
        """
        
        DEFAULT_CSS = """
        AgentCard {
            width: 30;
            height: auto;
            border: round #1e88e5;
            background: #2d2d2d;
            padding: 1 2;
            
            &.selected {
                border: round #ffc107;
                background: #3d3d3d;
            }
            
            &.busy {
                border: round #ff9800;
            }
            
            &.error {
                border: round #f44336;
            }
        }
        """
        
        DEFAULT_CLASSES = "agent-card"
        
        # Agent data
        agent: Optional[TUIAgent] = reactive(None, init=False)
        selected: bool = reactive(False, init=False)
        
        def __init__(
            self,
            agent: Optional[TUIAgent] = None,
            name: Optional[str] = None,
            id: Optional[str] = None,
            classes: Optional[str] = None,
        ):
            super().__init__(name=name, id=id, classes=classes)
            self.agent = agent
        
        def compose(self) -> ComposeResult:
            yield from super().compose()
        
        def watch_agent(self, agent: Optional[TUIAgent]) -> None:
            """React to agent changes."""
            if agent:
                # Update classes based on status
                self.set_class(False, "busy", "error")
                if agent.status == TUIAgentStatus.BUSY:
                    self.set_class(True, "busy")
                elif agent.status == TUIAgentStatus.ERROR:
                    self.set_class(True, "error")
        
        def watch_selected(self, selected: bool) -> None:
            """React to selection changes."""
            self.set_class(selected, "selected")
        
        def render(self) -> str:
            """Render the agent card."""
            if not self.agent:
                return "[dim]No agent[/]"
            
            a = self.agent
            lines = []
            
            # Header: Status icon + Name
            status_icon = a.status_icon
            status_color = a.status_color
            header = f"[{status_color}]{status_icon}[/{status_color}] [bold white]{a.name}[/]"
            lines.append(header)
            
            # Body
            # Description
            if a.description:
                # Truncate if too long
                desc = a.description[:40] + "..." if len(a.description) > 40 else a.description
                lines.append(f"[dim]{desc}[/]")
            
            # Status and metrics
            lines.append(f"  State: [{a.status_color}]{a.status.value}[/]")
            lines.append(f"  Tasks: {a.tasks_completed} done, {a.tasks_failed} failed, {a.tasks_active} active")
            
            # Current task
            if a.current_task_description:
                progress = int(a.current_task_progress * 100)
                lines.append(f"  Current: {a.current_task_description[:30]} ({progress}%)")
            
            # Capabilities (truncated)
            if a.capabilities:
                caps = ", ".join(a.capabilities[:3])
                if len(a.capabilities) > 3:
                    caps += ",..."
                lines.append(f"  Caps: [dim]{caps}[/]")
            
            return "\n".join(lines)
        
        def set_agent(self, agent: TUIAgent) -> None:
            """Set the agent to display."""
            self.agent = agent
        
        def select(self) -> None:
            """Select this card."""
            self.selected = True
        
        def deselect(self) -> None:
            """Deselect this card."""
            self.selected = False
        
        def toggle_select(self) -> None:
            """Toggle selection."""
            self.selected = not self.selected
else:
    AgentCard = None
