"""
Agent List Widget for TUI.

Displays a scrollable list of agents with filtering capabilities.
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

from tui.models import TUIAgent, TUIAgentStatus
from .agent_card import AgentCard


class AgentList(ScrollableContainer):
    """
    Scrollable list of agents.
    
    Supports filtering by status and capability.
    """
    
    DEFAULT_CSS = """
    AgentList {
        width: 100%;
        height: 100%;
        background: #1e1e1e;
        padding: 1;
    }
    
    AgentList .filter-bar {
        height: 3;
        width: 100%;
        dock: top;
        background: #2d2d2d;
        padding: 0 1;
    }
    
    AgentList .agents-grid {
        width: 100%;
        height: 1fr;
        layout: grid;
        grid-size: 3;
        grid-columns: 3;
        grid-rows: auto;
        
    }
    
    AgentList AgentCard {
        width: 1fr;
        height: auto;
    }
    """
    
    # Agents data
    agents: List[TUIAgent] = reactive([], init=False)
    filtered_agents: List[TUIAgent] = reactive([], init=False)
    
    # Filter state
    status_filter: str = reactive("all")
    capability_filter: str = reactive("")
    search_filter: str = reactive("")
    
    # Selection
    selected_agent: Optional[TUIAgent] = reactive(None, init=False)
    
    # Callbacks
    on_agent_selected: Optional[Callable[[TUIAgent], None]] = None
    
    def __init__(
        self,
        agents: Optional[List[TUIAgent]] = None,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
        on_agent_selected: Optional[Callable[[TUIAgent], None]] = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        if agents:
            self.agents = agents
        self.on_agent_selected = on_agent_selected
    
    def compose(self) -> ComposeResult:
        # Filter bar
        with Container(classes="filter-bar"):
            yield Label("Filter:", classes="filter-label")
            yield Input(
                placeholder="Search agents...",
                classes="search-input",
                id="search-input"
            )
            yield Button("Status: All", id="status-filter", classes="filter-button")
            yield Button("Clear", id="clear-filter", classes="filter-button")
        
        # Agents grid
        with Container(classes="agents-grid", id="agents-grid"):
            for agent in self.filtered_agents:
                yield AgentCard(agent=agent, classes="agent-card")
    
    def watch_agents(self, agents: List[TUIAgent]) -> None:
        """React to agents list changes."""
        self._apply_filters()
    
    def watch_status_filter(self, status: str) -> None:
        """React to status filter changes."""
        self._apply_filters()
    
    def watch_capability_filter(self, capability: str) -> None:
        """React to capability filter changes."""
        self._apply_filters()
    
    def watch_search_filter(self, search: str) -> None:
        """React to search filter changes."""
        self._apply_filters()
    
    def _apply_filters(self) -> None:
        """Apply all filters to the agents list."""
        filtered = self.agents
        
        # Status filter
        if self.status_filter != "all":
            status = TUIAgentStatus(self.status_filter.upper())
            filtered = [a for a in filtered if a.status == status]
        
        # Capability filter
        if self.capability_filter:
            filtered = [
                a for a in filtered 
                if self.capability_filter.lower() in [c.lower() for c in a.capabilities]
            ]
        
        # Search filter
        if self.search_filter:
            search = self.search_filter.lower()
            filtered = [
                a for a in filtered 
                if (search in a.name.lower() or 
                    search in a.description.lower() or
                    any(search in c.lower() for c in a.capabilities))
            ]
        
        self.filtered_agents = filtered
        self._update_grid()
    
    def _update_grid(self) -> None:
        """Update the agents grid with filtered agents."""
        grid = self.query_one("#agents-grid", Container)
        if grid:
            # Clear existing cards
            for child in grid.children:
                child.remove()
            
            # Add new cards
            for agent in self.filtered_agents:
                card = AgentCard(agent=agent)
                card.on_click = lambda a=agent: self._on_agent_clicked(a)
                grid.mount(card)
    
    def _on_agent_clicked(self, agent: TUIAgent) -> None:
        """Handle agent click."""
        self.selected_agent = agent
        if self.on_agent_selected:
            self.on_agent_selected(agent)
    
    def set_agents(self, agents: List[TUIAgent]) -> None:
        """Set the list of agents."""
        self.agents = agents
    
    def add_agent(self, agent: TUIAgent) -> None:
        """Add an agent to the list."""
        self.agents = self.agents + [agent]
    
    def remove_agent(self, agent_name: str) -> None:
        """Remove an agent from the list."""
        self.agents = [a for a in self.agents if a.name != agent_name]
    
    def set_status_filter(self, status: str) -> None:
        """Set the status filter."""
        self.status_filter = status
    
    def set_capability_filter(self, capability: str) -> None:
        """Set the capability filter."""
        self.capability_filter = capability
    
    def set_search_filter(self, search: str) -> None:
        """Set the search filter."""
        self.search_filter = search
    
    def clear_filters(self) -> None:
        """Clear all filters."""
        self.status_filter = "all"
        self.capability_filter = ""
        self.search_filter = ""
    
    @on(Input.Changed, "#search-input")
    def on_search_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        self.search_filter = event.value
    
    @on(Button.Pressed, "#status-filter")
    def on_status_filter_pressed(self, event: Button.Pressed) -> None:
        """Handle status filter button press."""
        # Cycle through statuses
        statuses = ["all", "idle", "busy", "error", "paused"]
        current = self.status_filter
        next_idx = (statuses.index(current) + 1) % len(statuses)
        self.status_filter = statuses[next_idx]
        event.button.label = f"Status: {self.status_filter}"
    
    @on(Button.Pressed, "#clear-filter")
    def on_clear_filter_pressed(self, event: Button.Pressed) -> None:
        """Handle clear filter button press."""
        self.clear_filters()
        self.query_one("#search-input", Input).value = ""


class AgentSelected(Message):
    """Message emitted when an agent is selected."""
    
    def __init__(self, agent: TUIAgent):
        self.agent = agent
        super().__init__()
