"""
Agents Screen for TUI.

Displays the list of registered agents with filtering and details.
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
from tui.models import TUIAgent
from tui.widgets.agent_list import AgentList
from tui.widgets.agent_card import AgentCard


class AgentsScreen(Widget):
    """
    Agents widget showing all registered agents.
    
    Features:
    - List of agents with filtering
    - Agent details panel
    - Real-time updates
    """
    
    DEFAULT_CSS = """
    AgentsScreen {
        layout: horizontal;
        width: 100%;
        height: 100%;
        background: #1e1e1e;
    }
    
    AgentsScreen .list-container {
        width: 60%;
        height: 100%;
        background: #121212;
    }
    
    AgentsScreen .details-container {
        width: 40%;
        height: 100%;
        background: #2d2d2d;
        padding: 1;
        overflow-y: auto;
    }
    
    AgentsScreen AgentList {
        width: 100%;
        height: 100%;
    }
    
    AgentsScreen AgentCard {
        width: 100%;
        height: auto;
    }
    
    AgentsScreen .details-header {
        width: 100%;
        height: auto;
        dock: top;
        text-style: bold;
        padding-bottom: 1;
        border-bottom: solid #1e88e5;
    }
    
    AgentsScreen .details-content {
        width: 100%;
        height: 1fr;
    }
    
    AgentsScreen .no-selection {
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
        self._agents: List[TUIAgent] = []
        self._selected_agent: Optional[TUIAgent] = None
    
    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        # List container
        with Container(classes="list-container"):
            yield AgentList(
                agents=self._agents,
                on_agent_selected=self._on_agent_selected,
                id="agent-list"
            )
        
        # Details container
        with Container(classes="details-container"):
            yield Label("Agent Details", classes="details-header")
            with Container(classes="details-content", id="agent-details"):
                yield Label("Select an agent to view details", classes="no-selection")
    
    def on_mount(self) -> None:
        """Called after the widget is mounted."""
        # Register for agent updates
        self.controller.on_agents_updated(self._on_agents_updated)
        
        # Load initial agents
        asyncio.create_task(self._load_initial_data())
    
    def on_unmount(self) -> None:
        """Called when the widget is unmounted."""
        # Unregister from updates
        try:
            self.controller._on_agents_updated.remove(self._on_agents_updated)
        except (ValueError, AttributeError):
            pass
    
    async def _load_initial_data(self) -> None:
        """Load initial data."""
        self._agents = await self.controller.get_agents()
        self._update_agent_list()
    
    def _on_agents_updated(self, agents: List[TUIAgent]) -> None:
        """Handle agent updates."""
        self._agents = agents
        self._update_agent_list()
    
    def _update_agent_list(self) -> None:
        """Update the agent list."""
        agent_list = self.query_one("#agent-list", AgentList)
        if agent_list:
            agent_list.set_agents(self._agents)
    
    def _on_agent_selected(self, agent: TUIAgent) -> None:
        """Handle agent selection."""
        self._selected_agent = agent
        self._update_agent_details()
    
    def _update_agent_details(self) -> None:
        """Update the agent details panel."""
        details_container = self.query_one("#agent-details", Container)
        if not details_container:
            return
        
        # Clear existing details
        for child in list(details_container.children):
            child.remove()
        
        if self._selected_agent:
            agent = self._selected_agent
            
            # Add agent card
            card = AgentCard(agent=agent, classes="agent-card")
            details_container.mount(card)
            
            # Add additional details
            details_container.mount(Label(""))
            details_container.mount(Label(f"ID: {agent.agent_id}"))
            details_container.mount(Label(f"Created: {agent.created_at}" if agent.created_at else Label("Created: N/A")))
            
            # Metrics
            details_container.mount(Label(""))
            details_container.mount(Label("[bold]Metrics[/bold]"))
            details_container.mount(Label(f"  Tasks Completed: {agent.tasks_completed}"))
            details_container.mount(Label(f"  Tasks Failed: {agent.tasks_failed}"))
            details_container.mount(Label(f"  Tasks Active: {agent.tasks_active}"))
            details_container.mount(Label(f"  Avg Execution Time: {agent.avg_execution_time:.2f}s"))
            
            # Capabilities
            if agent.capabilities:
                details_container.mount(Label(""))
                details_container.mount(Label("[bold]Capabilities[/bold]"))
                for cap in agent.capabilities:
                    details_container.mount(Label(f"  - {cap}"))
        else:
            details_container.mount(Label("Select an agent to view details", classes="no-selection"))



