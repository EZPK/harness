"""
Display Models for TUI.

These models represent data in a format optimized for display in the terminal UI.
They are lightweight and contain only the information needed for rendering.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# =============================================================================
# Agent Models
# =============================================================================

class TUIAgentStatus(str, Enum):
    """Status of an agent for display purposes."""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    IDLE = "idle"
    BUSY = "busy"
    PAUSED = "paused"
    ERROR = "error"
    SHUTDOWN = "shutdown"
    CHECKPOINTING = "checkpointing"
    RESTORING = "restoring"


@dataclass
class TUIAgent:
    """
    Display model for an agent.
    
    Contains only the information needed to display an agent in the TUI.
    """
    name: str
    agent_id: str
    description: str = ""
    status: TUIAgentStatus = TUIAgentStatus.UNINITIALIZED
    
    # Metrics
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_active: int = 0
    avg_execution_time: float = 0.0
    
    # Capabilities
    capabilities: List[str] = field(default_factory=list)
    
    # Current work
    current_task_id: Optional[str] = None
    current_task_description: Optional[str] = None
    current_task_progress: float = 0.0
    
    # Timestamps
    created_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    
    # Display properties
    icon: str = ""  # Unicode icon for display
    color: str = "white"  # Color for status display
    
    @property
    def status_icon(self) -> str:
        """Get the icon representing the agent status."""
        icons = {
            TUIAgentStatus.UNINITIALIZED: "⏳",
            TUIAgentStatus.INITIALIZING: "🔄",
            TUIAgentStatus.IDLE: "✓",
            TUIAgentStatus.BUSY: "◴",
            TUIAgentStatus.PAUSED: "⏸",
            TUIAgentStatus.ERROR: "✗",
            TUIAgentStatus.SHUTDOWN: "▢",
            TUIAgentStatus.CHECKPOINTING: "💾",
            TUIAgentStatus.RESTORING: "📥",
        }
        return icons.get(self.status, "?")
    
    @property
    def status_color(self) -> str:
        """Get the color for the agent status."""
        colors = {
            TUIAgentStatus.UNINITIALIZED: "yellow",
            TUIAgentStatus.INITIALIZING: "yellow",
            TUIAgentStatus.IDLE: "green",
            TUIAgentStatus.BUSY: "blue",
            TUIAgentStatus.PAUSED: "yellow",
            TUIAgentStatus.ERROR: "red",
            TUIAgentStatus.SHUTDOWN: "dim",
            TUIAgentStatus.CHECKPOINTING: "cyan",
            TUIAgentStatus.RESTORING: "cyan",
        }
        return colors.get(self.status, "white")


# =============================================================================
# Task Models
# =============================================================================

class TUITaskStatus(str, Enum):
    """Status of a task for display purposes."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    TIMEOUT = "timeout"


@dataclass
class TUITask:
    """
    Display model for a task.
    
    Contains only the information needed to display a task in the TUI.
    """
    task_id: str
    description: str
    task_type: str = ""
    status: TUITaskStatus = TUITaskStatus.PENDING
    
    # Assignment
    assigned_agent: Optional[str] = None
    assignment_id: Optional[str] = None
    
    # Progress
    progress: float = 0.0  # 0.0 to 1.0
    
    # Priority
    priority: str = "medium"
    priority_value: int = 2  # 1=low, 2=medium, 3=high, 4=critical
    
    # Timestamps
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Result
    result: Optional[Any] = None
    error: Optional[str] = None
    
    # Metadata
    workflow_id: Optional[str] = None
    parent_task_id: Optional[str] = None
    subtasks: List[str] = field(default_factory=list)
    subtask_statuses: Dict[str, TUITaskStatus] = field(default_factory=dict)
    
    # Display properties
    icon: str = ""
    color: str = "white"
    
    @property
    def status_icon(self) -> str:
        """Get the icon representing the task status."""
        icons = {
            TUITaskStatus.PENDING: "⏳",
            TUITaskStatus.ASSIGNED: "→",
            TUITaskStatus.RUNNING: "◴",
            TUITaskStatus.COMPLETED: "✓",
            TUITaskStatus.FAILED: "✗",
            TUITaskStatus.CANCELLED: "▢",
            TUITaskStatus.RETRYING: "🔄",
            TUITaskStatus.TIMEOUT: "⏰",
        }
        return icons.get(self.status, "?")
    
    @property
    def status_color(self) -> str:
        """Get the color for the task status."""
        colors = {
            TUITaskStatus.PENDING: "yellow",
            TUITaskStatus.ASSIGNED: "cyan",
            TUITaskStatus.RUNNING: "blue",
            TUITaskStatus.COMPLETED: "green",
            TUITaskStatus.FAILED: "red",
            TUITaskStatus.CANCELLED: "dim",
            TUITaskStatus.RETRYING: "yellow",
            TUITaskStatus.TIMEOUT: "red",
        }
        return colors.get(self.status, "white")
    
    @property
    def priority_icon(self) -> str:
        """Get the icon for priority."""
        if self.priority_value >= 4:
            return "!!!"
        elif self.priority_value >= 3:
            return "!!"
        elif self.priority_value >= 2:
            return "!"
        return " "


# =============================================================================
# Workflow Models
# =============================================================================

class TUIWorkflowStatus(str, Enum):
    """Status of a workflow for display purposes."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TUIWorkflowStep:
    """Display model for a workflow step."""
    step_id: str
    name: str
    description: str = ""
    agent_name: str = ""
    task_type: str = ""
    
    # Status
    status: TUITaskStatus = TUITaskStatus.PENDING
    
    # Progress
    progress: float = 0.0
    
    # Dependencies
    depends_on: List[str] = field(default_factory=list)
    
    # Result
    result: Optional[Any] = None
    error: Optional[str] = None
    
    # Timestamps
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @property
    def status_icon(self) -> str:
        """Get the icon representing the step status."""
        return TUITask(status=self.status).status_icon
    
    @property
    def status_color(self) -> str:
        """Get the color for the step status."""
        return TUITask(status=self.status).status_color


@dataclass
class TUIWorkflow:
    """
    Display model for a workflow.
    
    Contains only the information needed to display a workflow in the TUI.
    """
    workflow_id: str
    name: str
    description: str = ""
    status: TUIWorkflowStatus = TUIWorkflowStatus.PENDING
    
    # Progress
    progress: float = 0.0  # 0.0 to 1.0
    completed_steps: int = 0
    total_steps: int = 0
    failed_steps: int = 0
    
    # Steps
    steps: List[TUIWorkflowStep] = field(default_factory=list)
    step_order: List[str] = field(default_factory=list)  # Ordered list of step IDs
    
    # Current state
    current_step_id: Optional[str] = None
    
    # Timestamps
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Results
    results: Dict[str, Any] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)
    
    @property
    def status_icon(self) -> str:
        """Get the icon representing the workflow status."""
        icons = {
            TUIWorkflowStatus.PENDING: "⏳",
            TUIWorkflowStatus.RUNNING: "◴",
            TUIWorkflowStatus.PAUSED: "⏸",
            TUIWorkflowStatus.COMPLETED: "✓",
            TUIWorkflowStatus.FAILED: "✗",
            TUIWorkflowStatus.CANCELLED: "▢",
        }
        return icons.get(self.status, "?")
    
    @property
    def status_color(self) -> str:
        """Get the color for the workflow status."""
        colors = {
            TUIWorkflowStatus.PENDING: "yellow",
            TUIWorkflowStatus.RUNNING: "blue",
            TUIWorkflowStatus.PAUSED: "yellow",
            TUIWorkflowStatus.COMPLETED: "green",
            TUIWorkflowStatus.FAILED: "red",
            TUIWorkflowStatus.CANCELLED: "dim",
        }
        return colors.get(self.status, "white")
    
    def get_step(self, step_id: str) -> Optional[TUIWorkflowStep]:
        """Get a specific step by ID."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None


# =============================================================================
# Message Models (for Chat)
# =============================================================================

class TUIMessageType(str, Enum):
    """Type of message in the chat."""
    TEXT = "text"
    COMMAND = "command"
    TASK = "task"
    RESULT = "result"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"


class TUIMessageSender(str, Enum):
    """Sender of a message."""
    USER = "user"
    SYSTEM = "system"
    GOD_AGENT = "god_agent"
    AGENT = "agent"  # For specialist agents


@dataclass
class TUIMessage:
    """
    Display model for a chat message.
    
    Represents a message in the chat interface.
    """
    message_id: str
    sender: TUIMessageSender
    sender_name: str  # Specific name (e.g., "PlannerAgent", "User")
    content: str
    message_type: TUIMessageType = TUIMessageType.TEXT
    
    # Timestamps
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Metadata
    task_id: Optional[str] = None
    workflow_id: Optional[str] = None
    agent_name: Optional[str] = None
    
    # Display properties
    color: str = "white"
    bg_color: Optional[str] = None
    bold: bool = False
    italic: bool = False
    
    # For code blocks
    is_code: bool = False
    code_language: str = ""
    
    # For structured data
    data: Optional[Dict[str, Any]] = None
    
    @property
    def formatted_timestamp(self) -> str:
        """Get formatted timestamp."""
        return self.timestamp.strftime("%H:%M:%S")
    
    @property
    def sender_color(self) -> str:
        """Get color based on sender."""
        colors = {
            TUIMessageSender.USER: "cyan",
            TUIMessageSender.SYSTEM: "dim",
            TUIMessageSender.GOD_AGENT: "yellow",
            TUIMessageSender.AGENT: "green",
        }
        return colors.get(self.sender, "white")
    
    @property
    def type_color(self) -> str:
        """Get color based on message type."""
        colors = {
            TUIMessageType.TEXT: "white",
            TUIMessageType.COMMAND: "blue",
            TUIMessageType.TASK: "cyan",
            TUIMessageType.RESULT: "green",
            TUIMessageType.ERROR: "red",
            TUIMessageType.WARNING: "yellow",
            TUIMessageType.INFO: "blue",
            TUIMessageType.DEBUG: "dim",
        }
        return colors.get(self.message_type, "white")
    
    @property
    def sender_display(self) -> str:
        """Get display name for sender."""
        names = {
            TUIMessageSender.USER: "User",
            TUIMessageSender.SYSTEM: "System",
            TUIMessageSender.GOD_AGENT: "God",
            TUIMessageSender.AGENT: self.sender_name,
        }
        return names.get(self.sender, self.sender_name)


# =============================================================================
# Dashboard Models
# =============================================================================

@dataclass
class TUIMetrics:
    """Metrics for display in the dashboard."""
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    active_tasks: int = 0
    
    total_agents: int = 0
    active_agents: int = 0
    idle_agents: int = 0
    error_agents: int = 0
    
    total_workflows: int = 0
    active_workflows: int = 0
    completed_workflows: int = 0
    
    avg_execution_time: float = 0.0
    avg_agent_response_time: float = 0.0
    
    # Per-agent metrics
    agent_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Timestamps
    last_updated: Optional[datetime] = None


@dataclass
class TUIDashboardState:
    """Complete state for the dashboard."""
    metrics: TUIMetrics = field(default_factory=TUIMetrics)
    agents: List[TUIAgent] = field(default_factory=list)
    tasks: List[TUITask] = field(default_factory=list)
    workflows: List[TUIWorkflow] = field(default_factory=list)
    recent_messages: List[TUIMessage] = field(default_factory=list)
    
    # Alerts
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    
    last_updated: Optional[datetime] = None
