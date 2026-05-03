"""
Workflow Tree Widget for TUI.

Displays a workflow as a tree structure.
"""

from typing import List, Optional, Dict, Any

try:
    from textual.app import ComposeResult
    from textual.reactive import reactive
    from textual.widget import Widget
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False

from tui.models import TUIWorkflow, TUIWorkflowStep, TUIWorkflowStatus


class WorkflowTree(Widget):
    """
    Widget that displays a workflow as a tree.
    
    Uses Unicode box-drawing characters to create a visual tree structure.
    """
    
    DEFAULT_CSS = """
    WorkflowTree {
        width: 100%;
        height: auto;
        background: #1e1e1e;
        padding: 1;
    }
    """
    
    # Workflow data
    workflow: Optional[TUIWorkflow] = reactive(None, init=False)
    
    # Tree characters
    TREE_BRANCH = "├── "
    TREE_LAST = "└── "
    TREE_PIPE = "│   "
    TREE_SPACE = "    "
    
    def __init__(
        self,
        workflow: Optional[TUIWorkflow] = None,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self.workflow = workflow
    
    def compose(self) -> ComposeResult:
        yield from super().compose()
    
    def render(self) -> str:
        """Render the workflow tree."""
        if not self.workflow:
            return "[dim]No workflow[/]"
        
        lines = []
        
        # Header
        wf = self.workflow
        status_icon = wf.status_icon
        status_color = wf.status_color
        progress_percent = int(wf.progress * 100)
        
        header = f"[{status_color}]{status_icon}[/{status_color}] [bold white]{wf.name}[/] ({progress_percent}%)"
        if wf.description:
            header += f" - [dim]{wf.description}[/]"
        lines.append(header)
        lines.append("")
        
        # Build tree from steps
        if wf.steps:
            # Build dependency tree
            tree = self._build_tree(wf)
            tree_lines = self._render_tree(tree)
            lines.extend(tree_lines)
        else:
            lines.append("[dim]No steps[/]")
        
        return "\n".join(lines)
    
    def _build_tree(self, workflow: TUIWorkflow) -> Dict[str, Any]:
        """Build a tree structure from workflow steps."""
        # Group steps by dependencies
        tree: Dict[str, Any] = {}
        
        for step in workflow.steps:
            if not step.depends_on:
                # Root step
                if step.step_id not in tree:
                    tree[step.step_id] = {
                        "step": step,
                        "children": [],
                    }
            else:
                # Find parent and add as child
                parent_id = step.depends_on[0]  # Simple case: first dependency
                parent = self._find_parent(tree, parent_id)
                if parent:
                    parent["children"].append({
                        "step": step,
                        "children": [],
                    })
        
        return tree
    
    def _find_parent(self, tree: Dict[str, Any], parent_id: str) -> Optional[Dict[str, Any]]:
        """Find a parent node in the tree."""
        def search(node: Dict[str, Any], target_id: str) -> Optional[Dict[str, Any]]:
            if node.get("step", {}).step_id == target_id:
                return node
            for child in node.get("children", []):
                result = search(child, target_id)
                if result:
                    return result
            return None
        
        for node in tree.values():
            if node.get("step", {}).step_id == parent_id:
                return node
            for child in node.get("children", []):
                result = search(child, parent_id)
                if result:
                    return result
        return None
    
    def _render_tree(self, tree: Dict[str, Any], prefix: str = "") -> List[str]:
        """Render the tree recursively."""
        lines = []
        
        nodes = list(tree.values())
        for i, node in enumerate(nodes):
            step = node["step"]
            is_last = (i == len(nodes) - 1)
            
            # Current line
            connector = self.TREE_LAST if is_last else self.TREE_BRANCH
            step_line = self._render_step(step)
            lines.append(f"{prefix}{connector}{step_line}")
            
            # Children
            children = node.get("children", [])
            if children:
                child_prefix = prefix + (self.TREE_SPACE if is_last else self.TREE_PIPE)
                child_lines = self._render_tree(
                    {str(i): child for i, child in enumerate(children)},
                    child_prefix
                )
                lines.extend(child_lines)
        
        return lines
    
    def _render_step(self, step: TUIWorkflowStep) -> str:
        """Render a single step."""
        status_icon = step.status_icon
        status_color = step.status_color
        
        # Name with agent
        name = step.name
        if step.agent_name:
            name += f" ([dim]{step.agent_name}[/])"
        
        # Type
        if step.task_type:
            name += f" - [dim]{step.task_type}[/]"
        
        # Progress
        if step.progress > 0 and step.progress < 1:
            progress = int(step.progress * 100)
            name += f" ({progress}%)"
        
        return f"[{status_color}]{status_icon}[/{status_color}] {name}"
    
    def set_workflow(self, workflow: TUIWorkflow) -> None:
        """Set the workflow to display."""
        self.workflow = workflow


# Simple text-based workflow tree (no Textual dependency)
class SimpleWorkflowTree:
    """
    Simple text-based workflow tree generator.
    """
    
    TREE_BRANCH = "├── "
    TREE_LAST = "└── "
    TREE_PIPE = "│   "
    TREE_SPACE = "    "
    
    @classmethod
    def render(cls, workflow: TUIWorkflow) -> str:
        """Render a workflow as a tree."""
        lines = []
        
        # Header
        wf = workflow
        status_icon = wf.status_icon
        progress_percent = int(wf.progress * 100)
        lines.append(f"{status_icon} {wf.name} ({progress_percent}%)")
        lines.append("")
        
        # Steps
        if wf.steps:
            for i, step in enumerate(wf.steps):
                is_last = (i == len(wf.steps) - 1)
                connector = cls.TREE_LAST if is_last else cls.TREE_BRANCH
                
                # Step line
                status_icon = step.status_icon
                name = step.name
                if step.agent_name:
                    name += f" ({step.agent_name})"
                
                lines.append(f"{connector}{status_icon} {name}")
        
        return "\n".join(lines)
