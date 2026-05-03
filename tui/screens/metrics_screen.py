"""
Metrics Screen for TUI.

Displays metrics and statistics for the Harness system.
"""

from typing import Optional, Any

try:
    from textual.app import ComposeResult
    from textual.containers import Container, ScrollableContainer
    from textual.reactive import reactive
    from textual.widget import Widget
    from textual.widgets import Label
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False

import asyncio

from agents.god.agent import GodAgent
from tui.controller import TUIController
from tui.models import TUIMetrics, TUIDashboardState
from tui.widgets.metrics_chart import MetricsChart, SimpleMetricsChart


class MetricsScreen(Widget):
    """
    Metrics widget showing system statistics.
    
    Features:
    - Overview statistics
    - Per-agent metrics
    - Task metrics
    - Charts and visualizations
    """
    
    DEFAULT_CSS = """
    MetricsScreen {
        layout: vertical;
        width: 100%;
        height: 100%;
        background: #1e1e1e;
        padding: 1;
    }
    
    MetricsScreen .header {
        width: 100%;
        height: auto;
        dock: top;
        text-style: bold;
        padding-bottom: 1;
        border-bottom: solid #1e88e5;
    }
    
    MetricsScreen .stats-container {
        width: 100%;
        height: auto;
        layout: grid;
        grid-size: 3;
        grid-columns: 3;
        grid-rows: auto;
        
        padding-bottom: 1;
        border-bottom: solid #1e1e1e;
    }
    
    MetricsScreen .stat-card {
        width: 100%;
        height: auto;
        border: round #1e88e5;
        background: #2d2d2d;
        padding: 1;
        
        .stat-value {
            text-style: bold;
            
        }
        
        .stat-label {
            color: #9e9e9e;
            
        }
    }
    
    MetricsScreen .charts-container {
        width: 100%;
        height: 1fr;
        layout: horizontal;
        
    }
    
    MetricsScreen .chart-container {
        width: 1fr;
        height: 100%;
        background: #2d2d2d;
        padding: 1;
    }
    
    MetricsScreen .details-container {
        width: 100%;
        height: auto;
        background: #2d2d2d;
        padding: 1;
    }
    
    MetricsScreen MetricsChart {
        width: 100%;
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
        self._metrics: Optional[TUIMetrics] = None
        self._dashboard: Optional[TUIDashboardState] = None
    
    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        # Header
        yield Label("System Metrics", classes="header")
        
        # Stats overview
        with Container(classes="stats-container"):
            yield Container(classes="stat-card", id="stat-tasks")
            yield Container(classes="stat-card", id="stat-agents")
            yield Container(classes="stat-card", id="stat-workflows")
            yield Container(classes="stat-card", id="stat-completed")
            yield Container(classes="stat-card", id="stat-failed")
            yield Container(classes="stat-card", id="stat-time")
        
        # Charts
        with Container(classes="charts-container"):
            with Container(classes="chart-container"):
                yield MetricsChart(id="chart-tasks", title="Tasks by Status")
            with Container(classes="chart-container"):
                yield MetricsChart(id="chart-agents", title="Agent Activity")
        
        # Details
        with Container(classes="details-container"):
            yield Label("Per-Agent Metrics", classes="details-header")
            with ScrollableContainer(id="agent-metrics"):
                pass
    
    def on_mount(self) -> None:
        """Called after the widget is mounted."""
        # Register for dashboard updates
        self.controller.on_dashboard_updated(self._on_dashboard_updated)
        self.controller.on_metrics_updated(self._on_metrics_updated)
        
        # Load initial data
        asyncio.create_task(self._load_initial_data())
    
    def on_unmount(self) -> None:
        """Called when the widget is unmounted."""
        # Unregister from updates
        try:
            self.controller._on_dashboard_updated.remove(self._on_dashboard_updated)
            self.controller._on_metrics_updated.remove(self._on_metrics_updated)
        except (ValueError, AttributeError):
            pass
    
    async def _load_initial_data(self) -> None:
        """Load initial data."""
        dashboard = await self.controller.get_dashboard_state()
        self._on_dashboard_updated(dashboard)
    
    def _on_dashboard_updated(self, dashboard: TUIDashboardState) -> None:
        """Handle dashboard updates."""
        self._dashboard = dashboard
        self._metrics = dashboard.metrics
        self._update_stats()
        self._update_charts()
        self._update_agent_metrics()
    
    def _on_metrics_updated(self, metrics: TUIMetrics) -> None:
        """Handle metrics updates."""
        self._metrics = metrics
        self._update_stats()
        self._update_charts()
    
    def _update_stats(self) -> None:
        """Update the stat cards."""
        if not self._metrics:
            return
        
        m = self._metrics
        
        # Update each stat card
        self._update_stat_card("stat-tasks", "Tasks", m.total_tasks)
        self._update_stat_card("stat-agents", "Agents", m.total_agents)
        self._update_stat_card("stat-workflows", "Workflows", m.total_workflows)
        self._update_stat_card("stat-completed", "Completed", m.completed_tasks)
        self._update_stat_card("stat-failed", "Failed", m.failed_tasks)
        self._update_stat_card("stat-time", "Avg Time", f"{m.avg_execution_time:.1f}s")
    
    def _update_stat_card(self, card_id: str, label: str, value: Any) -> None:
        """Update a stat card."""
        card = self.query_one(f"#{card_id}", Container)
        if card:
            # Clear existing children
            for child in list(card.children):
                child.remove()
            
            # Add new content
            card.mount(Label(str(value), classes="stat-value"))
            card.mount(Label(label, classes="stat-label"))
    
    def _update_charts(self) -> None:
        """Update the charts."""
        if not self._dashboard:
            return
        
        dashboard = self._dashboard
        
        # Tasks by status chart
        tasks_chart = self.query_one("#chart-tasks", MetricsChart)
        if tasks_chart:
            tasks_data = {
                "Pending": sum(1 for t in dashboard.tasks if t.status.value == "pending"),
                "Running": sum(1 for t in dashboard.tasks if t.status.value == "running"),
                "Completed": sum(1 for t in dashboard.tasks if t.status.value == "completed"),
                "Failed": sum(1 for t in dashboard.tasks if t.status.value == "failed"),
            }
            tasks_chart.set_bar_data(
                tasks_data,
                colors={
                    "Pending": "yellow",
                    "Running": "blue",
                    "Completed": "green",
                    "Failed": "red",
                }
            )
        
        # Agent activity chart
        agents_chart = self.query_one("#chart-agents", MetricsChart)
        if agents_chart:
            agent_data = {}
            for agent in dashboard.agents:
                agent_data[agent.name] = agent.tasks_completed + agent.tasks_active
            
            agents_chart.set_bar_data(agent_data)
    
    def _update_agent_metrics(self) -> None:
        """Update the per-agent metrics display."""
        if not self._dashboard:
            return
        
        container = self.query_one("#agent-metrics", ScrollableContainer)
        if not container:
            return
        
        # Clear existing content
        for child in list(container.children):
            child.remove()
        
        # Add metrics for each agent
        for agent in self._dashboard.agents:
            # Create a card for each agent
            card = Container(classes="agent-metric-card")
            card.mount(Label(f"{agent.status_icon} {agent.name}", classes="agent-name"))
            card.mount(Label(f"  Tasks: {agent.tasks_completed} done, {agent.tasks_failed} failed"))
            card.mount(Label(f"  Active: {agent.tasks_active}"))
            card.mount(Label(f"  Avg Time: {agent.avg_execution_time:.2f}s"))
            container.mount(card)



