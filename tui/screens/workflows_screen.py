"""
Workflows Screen for TUI.

Displays the list of workflows with visualization.
"""

from typing import List, Optional

try:
    from textual.app import ComposeResult
    from textual.containers import Container, ScrollableContainer
    from textual.reactive import reactive
    from textual.widget import Widget
    from textual.widgets import Label, Button
    from textual import on
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False

import asyncio

from agents.god.agent import GodAgent
from tui.controller import TUIController
from tui.models import TUIWorkflow
from tui.widgets.workflow_tree import WorkflowTree, SimpleWorkflowTree


class WorkflowsScreen(Widget):
    """
    Workflows widget showing all workflows.
    
    Features:
    - List of workflows
    - Workflow tree visualization
    - Real-time updates
    """
    
    DEFAULT_CSS = """
    WorkflowsScreen {
        layout: horizontal;
        width: 100%;
        height: 100%;
        background: #1e1e1e;
    }
    
    WorkflowsScreen .list-container {
        width: 30%;
        height: 100%;
        background: #121212;
        padding: 1;
        overflow-y: auto;
    }
    
    WorkflowsScreen .visual-container {
        width: 70%;
        height: 100%;
        background: #2d2d2d;
        padding: 1;
        overflow-y: auto;
    }
    
    WorkflowsScreen .workflow-item {
        width: 100%;
        height: auto;
        padding: 1 0;
        
        &.selected {
            background: #3d3d3d;
        }
        
        &.running {
            color: #ff9800;
        }
        
        &.completed {
            color: #4caf50;
            opacity: 0.7;
        }
        
        &.failed {
            color: #f44336;
        }
    }
    
    WorkflowsScreen .tree-container {
        width: 100%;
        height: 1fr;
        background: #1e1e1e;
        padding: 1;
    }
    
    WorkflowsScreen .no-selection {
        color: #9e9e9e;
        text-style: italic;
        align: center middle;
        height: 100%;
    }
    
    WorkflowsScreen .controls {
        width: 100%;
        height: auto;
        dock: bottom;
        padding-top: 1;
        border-top: solid #1e88e5;
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
        self._workflows: List[TUIWorkflow] = []
        self._selected_workflow: Optional[TUIWorkflow] = None
    
    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        # List container
        with Container(classes="list-container"):
            yield Label("Workflows", classes="list-header")
            with ScrollableContainer(id="workflow-list"):
                pass  # Will be populated dynamically
        
        # Visual container
        with Container(classes="visual-container"):
            yield Label("Workflow Visualization", classes="tree-header")
            with Container(classes="tree-container", id="workflow-tree"):
                yield Label("Select a workflow to view its tree", classes="no-selection")
    
    def on_mount(self) -> None:
        """Called after the widget is mounted."""
        # Register for workflow updates
        self.controller.on_workflows_updated(self._on_workflows_updated)
        
        # Load initial workflows
        asyncio.create_task(self._load_initial_data())
    
    def on_unmount(self) -> None:
        """Called when the widget is unmounted."""
        # Unregister from updates
        try:
            self.controller._on_workflows_updated.remove(self._on_workflows_updated)
        except (ValueError, AttributeError):
            pass
    
    async def _load_initial_data(self) -> None:
        """Load initial data."""
        self._workflows = await self.controller.get_workflows()
        self._update_workflow_list()
    
    def _on_workflows_updated(self, workflows: List[TUIWorkflow]) -> None:
        """Handle workflow updates."""
        self._workflows = workflows
        self._update_workflow_list()
    
    def _update_workflow_list(self) -> None:
        """Update the workflow list."""
        list_container = self.query_one("#workflow-list", ScrollableContainer)
        if not list_container:
            return
        
        # Clear existing items
        for child in list(list_container.children):
            child.remove()
        
        # Add workflow items
        for workflow in self._workflows:
            item = Label(
                f"{workflow.status_icon} {workflow.name} ({workflow.status.value})",
                classes="workflow-item",
                id=f"wf-{workflow.workflow_id}"
            )
            
            # Add status class
            if workflow.status.value == "running":
                item.classes += " running"
            elif workflow.status.value == "completed":
                item.classes += " completed"
            elif workflow.status.value == "failed":
                item.classes += " failed"
            
            # Set click handler
            item.on_click = lambda wf=workflow: self._on_workflow_selected(wf)
            
            list_container.mount(item)
    
    def _on_workflow_selected(self, workflow: TUIWorkflow) -> None:
        """Handle workflow selection."""
        self._selected_workflow = workflow
        self._update_workflow_tree()
    
    def _update_workflow_tree(self) -> None:
        """Update the workflow tree visualization."""
        tree_container = self.query_one("#workflow-tree", Container)
        if not tree_container:
            return
        
        # Clear existing tree
        for child in list(tree_container.children):
            child.remove()
        
        if self._selected_workflow:
            # Add workflow tree
            tree = WorkflowTree(workflow=self._selected_workflow)
            tree_container.mount(tree)
        else:
            tree_container.mount(Label("Select a workflow to view its tree", classes="no-selection"))



