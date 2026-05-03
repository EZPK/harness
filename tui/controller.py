"""
TUI Controller for Harness Agentic Framework.

This is the main controller that connects the TUI to the God Agent.
It handles:
- Communication with the God Agent
- Event subscriptions
- Data conversion for the TUI
- Command execution
- Chat streaming
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING, AsyncIterator

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from agents.god.agent import GodAgent
    from agents.base import BaseAgent, TaskContext, TaskResult
    from core.aci import TaskType
    from tui.models import (
        TUIAgent,
        TUITask,
        TUIWorkflow,
        TUIMessage,
        TUIDashboardState,
    )


@dataclass
class TUIControllerConfig:
    """Configuration for the TUI Controller."""
    auto_refresh_interval: float = 1.0  # Seconds between auto-refreshes
    max_messages: int = 100  # Maximum messages to keep in history
    max_tasks: int = 50  # Maximum tasks to display
    max_workflows: int = 20  # Maximum workflows to display


class TUIController:
    """
    Main controller for the TUI.
    
    Manages communication between the TUI and the God Agent.
    Handles event subscriptions and data updates.
    """
    
    def __init__(
        self,
        god_agent: "GodAgent",
        config: Optional[TUIControllerConfig] = None,
    ):
        """
        Initialize the TUI Controller.
        
        Args:
            god_agent: The God Agent instance
            config: Optional controller configuration
        """
        self.god = god_agent
        self.config = config or TUIControllerConfig()
        
        # State
        self._initialized = False
        self._running = False
        
        # Callbacks for UI updates
        self._on_agents_updated: List[Callable[[List["TUIAgent"]], None]] = []
        self._on_tasks_updated: List[Callable[[List["TUITask"]], None]] = []
        self._on_workflows_updated: List[Callable[[List["TUIWorkflow"]], None]] = []
        self._on_messages_updated: List[Callable[[List["TUIMessage"]], None]] = []
        self._on_dashboard_updated: List[Callable[["TUIDashboardState"], None]] = []
        self._on_metrics_updated: List[Callable[["TUIMetrics"], None]] = []
        
        # Message history
        self._messages: List["TUIMessage"] = []
        
        # Task history
        self._tasks: List["TUITask"] = []
        
        # Workflow history
        self._workflows: List["TUIWorkflow"] = []
        
        # Event handlers
        self._event_handlers = {}
    
    async def initialize(self) -> None:
        """
        Initialize the controller.
        
        Subscribes to God Agent events and performs initial data load.
        """
        if self._initialized:
            return
        
        # Initialize God Agent if not already done
        if self.god.state.name == "UNINITIALIZED":
            await self.god.initialize()
        
        # Subscribe to events
        await self._subscribe_to_events()
        
        # Load initial data
        await self._load_initial_data()
        
        self._initialized = True
    
    async def start(self) -> None:
        """Start the controller's background tasks."""
        if self._running:
            return
        
        self._running = True
        
        # Start auto-refresh loop
        self._refresh_task = asyncio.create_task(self._auto_refresh_loop())
    
    async def stop(self) -> None:
        """Stop the controller's background tasks."""
        self._running = False
        
        if hasattr(self, '_refresh_task'):
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
    
    async def _auto_refresh_loop(self) -> None:
        """Background loop for auto-refreshing data."""
        while self._running:
            await asyncio.sleep(self.config.auto_refresh_interval)
            await self.refresh()
    
    async def _subscribe_to_events(self) -> None:
        """Subscribe to God Agent events."""
        # Note: The God Agent has event handlers as lists
        # We append our handlers to them
        
        if hasattr(self.god, '_on_task_start'):
            self.god._on_task_start.append(self._on_task_start)
        if hasattr(self.god, '_on_task_complete'):
            self.god._on_task_complete.append(self._on_task_complete)
        if hasattr(self.god, '_on_task_error'):
            self.god._on_task_error.append(self._on_task_error)
        if hasattr(self.god, '_on_agent_register'):
            self.god._on_agent_register.append(self._on_agent_register)
        if hasattr(self.god, '_on_agent_unregister'):
            self.god._on_agent_unregister.append(self._on_agent_unregister)
    
    async def _load_initial_data(self) -> None:
        """Load initial data from the God Agent."""
        # Get agents
        agents = await self.get_agents()
        self._notify_agents_updated(agents)
        
        # Get tasks
        tasks = await self.get_tasks()
        self._notify_tasks_updated(tasks)
        
        # Get workflows
        workflows = await self.get_workflows()
        self._notify_workflows_updated(workflows)
        
        # Get dashboard state
        dashboard = await self.get_dashboard_state()
        self._notify_dashboard_updated(dashboard)
    
    async def refresh(self) -> None:
        """Refresh all data from the God Agent."""
        await self._load_initial_data()
    
    # =========================================================================
    # Data Access Methods
    # =========================================================================
    
    async def get_agents(self) -> List["TUIAgent"]:
        """Get the list of registered agents."""
        from tui.models import TUIAgent, convert_agent_to_tui, convert_agents_to_tui
        
        try:
            # Get agents from God Agent's registry
            if hasattr(self.god, '_agent_registry'):
                registry = self.god._agent_registry
                agents = list(registry._agents.values())
                return convert_agents_to_tui(agents)
            else:
                return []
        except Exception as e:
            logger.error(f"Error getting agents: {e}")
            return []
    
    async def get_tasks(self, limit: Optional[int] = None) -> List["TUITask"]:
        """Get the list of tasks."""
        from tui.models import TUITask, convert_task_dict_to_tui, convert_tasks_to_tui
        
        try:
            # Get tasks from God Agent
            if hasattr(self.god, '_active_assignments'):
                assignments = self.god._active_assignments
                # Convert assignments to TUI tasks
                tasks = []
                for assignment in assignments.values():
                    task = convert_task_dict_to_tui(
                        assignment.task,
                        {
                            "assignment_id": assignment.assignment_id,
                            "agent_name": assignment.agent_name,
                            "status": assignment.status,
                        }
                    )
                    tasks.append(task)
                return tasks
            else:
                return []
        except Exception as e:
            logger.error(f"Error getting tasks: {e}")
            return []
    
    async def get_workflows(self, limit: Optional[int] = None) -> List["TUIWorkflow"]:
        """Get the list of workflows."""
        from tui.models import TUIWorkflow, convert_workflow_to_tui, convert_workflows_to_tui
        
        try:
            # Get workflows from God Agent
            if hasattr(self.god, '_workflows'):
                workflows = list(self.god._workflows.values())
                return convert_workflows_to_tui(workflows)
            else:
                return []
        except Exception as e:
            logger.error(f"Error getting workflows: {e}")
            return []
    
    async def get_dashboard_state(self) -> "TUIDashboardState":
        """Get the complete dashboard state."""
        from tui.models import TUIDashboardState, TUIMetrics
        
        try:
            # Get metrics
            metrics = await self.get_metrics()
            
            # Get agents, tasks, workflows
            agents = await self.get_agents()
            tasks = await self.get_tasks()
            workflows = await self.get_workflows()
            
            # Get recent messages
            messages = self._messages[-self.config.max_messages:]
            
            return TUIDashboardState(
                metrics=metrics,
                agents=agents,
                tasks=tasks,
                workflows=workflows,
                recent_messages=messages,
                last_updated=Any,  # TODO: Use proper datetime
            )
        except Exception as e:
            logger.error(f"Error getting dashboard state: {e}")
            return TUIDashboardState()
    
    async def get_metrics(self) -> "TUIMetrics":
        """Get metrics from the monitoring system."""
        from tui.models import TUIMetrics
        from core.monitoring import get_metrics_collector
        
        try:
            collector = get_metrics_collector()
            
            # Get agent metrics
            agent_metrics = {}
            if hasattr(collector, '_agent_metrics'):
                for agent_name, metrics in collector._agent_metrics.items():
                    agent_metrics[agent_name] = {
                        "tasks_completed": metrics.get("tasks_completed", 0),
                        "tasks_failed": metrics.get("tasks_failed", 0),
                        "avg_execution_time": metrics.get("avg_execution_time", 0),
                    }
            
            # Build TUIMetrics
            return TUIMetrics(
                total_tasks=len(self._tasks),
                completed_tasks=sum(1 for t in self._tasks if t.status.value == "completed"),
                failed_tasks=sum(1 for t in self._tasks if t.status.value == "failed"),
                active_tasks=sum(1 for t in self._tasks if t.status.value in ["running", "assigned"]),
                total_agents=len(self._agents) if hasattr(self, '_agents') else 0,
                active_agents=0,  # TODO
                idle_agents=0,  # TODO
                error_agents=0,  # TODO
                total_workflows=len(self._workflows),
                active_workflows=0,  # TODO
                completed_workflows=0,  # TODO
                agent_metrics=agent_metrics,
            )
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return TUIMetrics()
    
    # =========================================================================
    # Command Execution
    # =========================================================================
    
    async def execute_command(self, command: str) -> Optional[str]:
        """
        Execute a command from the chat.
        
        Everything now goes through GodAgent.chat() which handles:
        - Commands (starting with /)
        - Task requests
        - Conversation
        
        Args:
            command: The command to execute
            
        Returns:
            Response message or None
        """
        command = command.strip()
        
        if not command:
            return None
        
        # Special case: /quit is handled by the TUI
        if command == "/quit":
            return None
        
        # Everything else goes through GodAgent
        try:
            # Use GodAgent.chat() for all interactions
            response = await self.god.chat(command, user_request=command)
            
            # Add messages to history
            from tui.models import create_task_submission_message, create_god_response_message
            user_msg = create_task_submission_message(command, command)
            god_msg = create_god_response_message(response, msg_type="result")
            self._add_message(user_msg)
            self._add_message(god_msg)
            
            return response
            
        except Exception as e:
            from tui.models import create_error_message
            error_msg = create_error_message(f"Erreur: {e}", "")
            self._add_message(error_msg)
            return f"Erreur: {e}"
    
    async def chat_stream(self, message: str) -> AsyncIterator[str]:
        """
        Stream chat responses from GodAgent.
        
        This provides a fluid chat experience with real-time updates.
        
        Args:
            message: User message
            
        Yields:
            Response chunks as they become available
        """
        async for chunk in self.god.chat_stream(message, user_request=message):
            yield chunk
    
    async def _execute_system_command(self, command: str) -> Optional[str]:
        """Execute a system command."""
        parts = command[1:].strip().split(None, 1)
        cmd = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""
        
        handlers = {
            "task": self._cmd_task,
            "agent": self._cmd_agent,
            "workflow": self._cmd_workflow,
            "metrics": self._cmd_metrics,
            "provider": self._cmd_provider,
            "config": self._cmd_provider,
            "clear": self._cmd_clear,
            "help": self._cmd_help,
            "quit": self._cmd_quit,
        }
        
        handler = handlers.get(cmd)
        if handler:
            return await handler(args)
        else:
            return f"Unknown command: /{cmd}. Type /help for available commands."
    
    async def _submit_task(self, description: str) -> str:
        """Submit a task to the God Agent."""
        from tui.models import (
            create_task_submission_message,
            create_god_response_message,
        )
        
        # Create task ID
        task_id = str(uuid.uuid4())
        
        # Create task - use type that routes to LLMAgent
        # The God Agent router looks for keywords like "llm", "reasoning", etc.
        # or matches capabilities
        task = {
            "task_id": task_id,
            "description": description,
            "type": "text_generation",  # This will match LLMAgent's capability
            "capabilities": ["llm", "text_generation", "reasoning", "analysis"],
        }
        
        # Add message to history
        user_msg = create_task_submission_message(description, task_id)
        self._add_message(user_msg)
        
        try:
            # Submit to God Agent with description and metadata for context
            result = await self.god.execute(
                task, 
                user_request=description,
                metadata={"type": task["type"], "description": description}
            )
            
            # Create response message (without task_id in content)
            response = f"Task submitted: {description}\n"
            if result:
                # Extract the actual response content
                if isinstance(result, dict):
                    content = result.get("output", result.get("result", result.get("content", str(result))))
                else:
                    content = str(result)
                response = content
            
            god_msg = create_god_response_message(response, task_id, "result")
            self._add_message(god_msg)
            
            return response
        except Exception as e:
            error_msg = f"Error submitting task: {e}"
            self._add_message(
                create_god_response_message(error_msg, task_id, "error")
            )
            return error_msg
    
    # =========================================================================
    # Command Handlers
    # =========================================================================
    
    async def _cmd_task(self, args: str) -> str:
        """Handle /task command."""
        # /task <description>
        if args:
            return await self._submit_task(args)
        else:
            return "Usage: /task <description>"
    
    async def _cmd_agent(self, args: str) -> str:
        """Handle /agent command."""
        parts = args.strip().split()
        
        if not parts:
            # List agents
            agents = await self.get_agents()
            lines = [f"Registered Agents ({len(agents)}):"]
            for agent in agents:
                lines.append(f"  {agent.status_icon} {agent.name} - {agent.status.value}")
            return "\n".join(lines)
        
        subcmd = parts[0].lower()
        
        if subcmd == "list":
            return await self._cmd_agent("")  # List agents
        elif subcmd == "info":
            if len(parts) > 1:
                agent_name = parts[1]
                agents = await self.get_agents()
                for agent in agents:
                    if agent.name == agent_name:
                        return self._format_agent_info(agent)
                return f"Agent '{agent_name}' not found."
            else:
                return "Usage: /agent info <name>"
        else:
            return "Usage: /agent [list|info <name>]"
    
    async def _cmd_workflow(self, args: str) -> str:
        """Handle /workflow command."""
        parts = args.strip().split()
        
        if not parts:
            # List workflows
            workflows = await self.get_workflows()
            lines = [f"Workflows ({len(workflows)}):"]
            for wf in workflows:
                lines.append(f"  {wf.status_icon} {wf.name} - {wf.status.value}")
            return "\n".join(lines)
        
        subcmd = parts[0].lower()
        
        if subcmd == "list":
            return await self._cmd_workflow("")
        elif subcmd == "info":
            if len(parts) > 1:
                wf_id = parts[1]
                workflows = await self.get_workflows()
                for wf in workflows:
                    if wf.workflow_id == wf_id:
                        return self._format_workflow_info(wf)
                return f"Workflow '{wf_id}' not found."
            else:
                return "Usage: /workflow info <id>"
        elif subcmd == "create":
            # /workflow create <name> <steps...>
            if len(parts) > 1:
                return await self._create_workflow(parts[1:])
            else:
                return "Usage: /workflow create <name> <step1> <step2> ..."
        else:
            return "Usage: /workflow [list|info <id>|create <name> <steps>]"
    
    async def _cmd_metrics(self, args: str) -> str:
        """Handle /metrics command."""
        metrics = await self.get_metrics()
        
        lines = [
            "Metrics:",
            f"  Tasks: {metrics.total_tasks} total, {metrics.active_tasks} active",
            f"  Agents: {metrics.total_agents} total, {metrics.active_agents} active",
            f"  Workflows: {metrics.total_workflows} total",
        ]
        
        if metrics.agent_metrics:
            lines.append("")
            lines.append("Per-Agent Metrics:")
            for agent_name, agent_metrics in metrics.agent_metrics.items():
                lines.append(
                    f"  {agent_name}: {agent_metrics.get('tasks_completed', 0)} done, "
                    f"{agent_metrics.get('avg_execution_time', 0):.1f}s avg"
                )
        
        return "\n".join(lines)
    
    async def _cmd_clear(self, args: str) -> str:
        """Handle /clear command."""
        self._messages = []
        self._notify_messages_updated(self._messages)
        return "Chat cleared."
    
    async def _cmd_help(self, args: str) -> str:
        """Handle /help command."""
        return """Available Commands:
  /task <description>   - Submit a task to the God Agent
  /agent list         - List all registered agents
  /agent info <name>   - Show info about an agent
  /workflow list       - List all workflows
  /workflow info <id>  - Show info about a workflow
  /workflow create ... - Create a new workflow
  /metrics             - Show metrics
  /provider            - Show current LLM provider config
  /provider open       - Open provider configuration modal
  /provider set <p> [m] - Change provider (e.g., /provider set ollama smollm:135m)
  /config              - Same as /provider
  /clear               - Clear the chat
  /help                - Show this help
  /quit                - Quit the TUI

Or just type a task description directly (e.g., "implémenter une API REST")
"""
    
    async def _cmd_quit(self, args: str) -> str:
        """Handle /quit command."""
        # This will be handled by the TUI app
        return None
    
    async def _cmd_provider(self, args: str) -> str:
        """Handle /provider and /config commands."""
        parts = args.strip().split()
        
        if not parts:
            # Show current configuration
            return await self._show_provider_config()
        
        subcmd = parts[0].lower()
        
        if subcmd in ["list", "show"]:
            return await self._show_provider_config()
        elif subcmd in ["set", "change"]:
            if len(parts) >= 2:
                return await self._change_provider(" ".join(parts[1:]))
            else:
                return "Usage: /provider set <provider> [model]"
        elif subcmd == "open":
            # Open the configuration modal (handled by TUI)
            return "OPEN_PROVIDER_MODAL"
        else:
            return "Usage: /provider [open|list|set <provider> [model]]"
    
    async def _show_provider_config(self) -> str:
        """Show current provider configuration."""
        from configs.llm_config import get_llm_config
        
        try:
            config = get_llm_config()
            lines = [
                "Current LLM Configuration:",
                f"  Provider: {config.default_provider}",
                f"  Model: {config.ollama_model if hasattr(config, 'ollama_model') else 'N/A'}",
                f"  Base URL: {config.ollama_base_url if hasattr(config, 'ollama_base_url') else 'N/A'}",
                f"  Temperature: {config.default_temperature}",
                f"  Timeout: {config.default_timeout}s",
            ]
            
            # Add provider-specific info
            if config.default_provider:
                lines.append("")
                lines.append("Available commands:")
                lines.append("  /provider open  - Open configuration modal")
                lines.append("  /provider set <provider> [model] - Change provider")
            
            return "\n".join(lines)
        except Exception as e:
            return f"Error getting configuration: {e}"
    
    async def _change_provider(self, provider_model: str) -> str:
        """Change the current provider."""
        from configs.llm_config import get_llm_config, reload_llm_config
        from providers.registry import get_registry, create_provider
        from providers.base import LLMConfig, ProviderType
        from providers.openai_compatible import OpenAICompatibleProvider
        
        parts = provider_model.split()
        
        if len(parts) >= 2:
            provider_name = parts[0]
            model_name = parts[1]
        elif len(parts) == 1:
            provider_name = parts[0]
            model_name = ""
        else:
            return "Usage: /provider set <provider> [model]"
        
        try:
            # Update configuration
            config = get_llm_config()
            
            # For Ollama
            if provider_name.lower() == "ollama" or "/" in provider_name:
                config.default_provider = f"ollama/{model_name}" if model_name else provider_name
                if hasattr(config, 'ollama_model'):
                    config.ollama_model = model_name
            else:
                config.default_provider = f"{provider_name}/{model_name}" if model_name else provider_name
            
            # Reload configuration
            reload_llm_config()
            
            # Recreate the default provider in registry
            registry = get_registry()
            registry.clear()  # Clear existing providers
            
            # Create new default provider
            # Parse provider_model to create appropriate provider
            provider_str = config.default_provider
            
            # For Ollama, use OpenAICompatibleProvider directly
            if provider_name.lower() == "ollama" or "ollama" in provider_str.lower():
                base_url = getattr(config, 'ollama_base_url', 'http://localhost:11434/v1')
                api_key = getattr(config, 'ollama_api_key', None)
                default_provider = OpenAICompatibleProvider(
                    model=model_name,
                    api_key=api_key,
                    api_base_url=base_url,
                    temperature=0.7,
                    max_tokens=4096,
                    timeout=120.0,
                )
            else:
                # Map provider name to ProviderType
                provider_type_map = {
                    "openai": ProviderType.OPENAI,
                    "mistral": ProviderType.MISTRAL,
                    "anthropic": ProviderType.ANTHROPIC,
                    "google": ProviderType.GOOGLE,
                    "litellm": ProviderType.LITELLML,
                }
                provider_type = provider_type_map.get(provider_name.lower(), ProviderType.LITELLML)
                
                llm_config = LLMConfig(
                    provider=provider_type,
                    model=model_name,
                    api_key=None,  # Will be loaded from env
                    temperature=0.7,
                    timeout=120.0,
                )
                default_provider = create_provider(llm_config)
            
            if default_provider:
                registry.register(provider_str, default_provider, is_default=True)
                return f"Provider changed to: {provider_str}"
            else:
                return f"Provider {provider_str} created but may need API key"
            
        except Exception as e:
            return f"Error changing provider: {e}"
    
    # =========================================================================
    # Event Handlers
    # =========================================================================
    
    async def _on_task_start(self, agent: "BaseAgent", context: "TaskContext") -> None:
        """Handle task start event."""
        from tui.models import create_god_response_message
        
        task_id = context.task_id
        # Get description from metadata or user_request
        description = context.metadata.get("description", "") or context.user_request or ""
        
        message = create_god_response_message(
            f"Task started: {description}",
            task_id,
            "task"
        )
        self._add_message(message)
    
    async def _on_task_complete(
        self, agent: "BaseAgent", context: "TaskContext", result: "TaskResult"
    ) -> None:
        """Handle task complete event."""
        from tui.models import create_agent_response_message
        
        task_id = context.task_id
        agent_name = agent.name
        
        message = create_agent_response_message(
            agent_name,
            f"Task completed: {result.output}",
            task_id,
            "result"
        )
        self._add_message(message)
    
    async def _on_task_error(self, agent: "BaseAgent", context: "TaskContext", error: Exception) -> None:
        """Handle task error event."""
        from tui.models import create_error_message
        
        task_id = context.task_id
        
        message = create_error_message(
            f"Task error: {str(error)}",
            task_id,
            agent.name
        )
        self._add_message(message)
    
    async def _on_agent_register(self, agent: "BaseAgent") -> None:
        """Handle agent register event."""
        from tui.models import create_god_response_message
        
        message = create_god_response_message(
            f"Agent registered: {agent.name}",
            msg_type="info"
        )
        self._add_message(message)
        
        # Refresh agents list
        agents = await self.get_agents()
        self._notify_agents_updated(agents)
    
    async def _on_agent_unregister(self, agent_name: str) -> None:
        """Handle agent unregister event."""
        from tui.models import create_god_response_message
        
        message = create_god_response_message(
            f"Agent unregistered: {agent_name}",
            msg_type="info"
        )
        self._add_message(message)
        
        # Refresh agents list
        agents = await self.get_agents()
        self._notify_agents_updated(agents)
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _add_message(self, message: "TUIMessage") -> None:
        """Add a message to the history."""
        self._messages.append(message)
        # Limit history
        if len(self._messages) > self.config.max_messages:
            self._messages = self._messages[-self.config.max_messages:]
        
        self._notify_messages_updated(self._messages)
    
    def _format_agent_info(self, agent: "TUIAgent") -> str:
        """Format agent info for display."""
        lines = [
            f"{agent.status_icon} {agent.name}",
            f"  Status: {agent.status.value}",
            f"  Description: {agent.description}",
            f"  Tasks: {agent.tasks_completed} completed, {agent.tasks_failed} failed",
            f"  Capabilities: {', '.join(agent.capabilities)}",
        ]
        
        if agent.current_task_description:
            lines.append(f"  Current Task: {agent.current_task_description}")
        
        return "\n".join(lines)
    
    def _format_workflow_info(self, workflow: "TUIWorkflow") -> str:
        """Format workflow info for display."""
        lines = [
            f"{workflow.status_icon} {workflow.name}",
            f"  Status: {workflow.status.value}",
            f"  Progress: {int(workflow.progress * 100)}%",
            f"  Steps: {workflow.completed_steps}/{workflow.total_steps} completed",
            f"  Description: {workflow.description}",
        ]
        
        if workflow.steps:
            lines.append("")
            lines.append("  Steps:")
            for step in workflow.steps:
                lines.append(f"    {step.status_icon} {step.name} ({step.status.value})")
        
        return "\n".join(lines)
    
    async def _create_workflow(self, parts: List[str]) -> str:
        """Create a new workflow."""
        if not parts:
            return "Usage: /workflow create <name> <step1> <step2> ..."
        
        name = parts[0]
        steps = parts[1:]
        
        # For now, just echo back - full implementation needs workflow engine
        return f"Workflow '{name}' created with {len(steps)} steps: {', '.join(steps)}"
    
    # =========================================================================
    # Notification Methods
    # =========================================================================
    
    def on_agents_updated(self, callback: Callable[[List["TUIAgent"]], None]) -> None:
        """Register a callback for agent updates."""
        self._on_agents_updated.append(callback)
    
    def on_tasks_updated(self, callback: Callable[[List["TUITask"]], None]) -> None:
        """Register a callback for task updates."""
        self._on_tasks_updated.append(callback)
    
    def on_workflows_updated(self, callback: Callable[[List["TUIWorkflow"]], None]) -> None:
        """Register a callback for workflow updates."""
        self._on_workflows_updated.append(callback)
    
    def on_messages_updated(self, callback: Callable[[List["TUIMessage"]], None]) -> None:
        """Register a callback for message updates."""
        self._on_messages_updated.append(callback)
    
    def on_dashboard_updated(self, callback: Callable[["TUIDashboardState"], None]) -> None:
        """Register a callback for dashboard updates."""
        self._on_dashboard_updated.append(callback)
    
    def on_metrics_updated(self, callback: Callable[["TUIMetrics"], None]) -> None:
        """Register a callback for metrics updates."""
        self._on_metrics_updated.append(callback)
    
    def _notify_agents_updated(self, agents: List["TUIAgent"]) -> None:
        """Notify listeners of agent updates."""
        self._agents = agents
        for callback in self._on_agents_updated:
            try:
                callback(agents)
            except Exception:
                pass
    
    def _notify_tasks_updated(self, tasks: List["TUITask"]) -> None:
        """Notify listeners of task updates."""
        self._tasks = tasks
        for callback in self._on_tasks_updated:
            try:
                callback(tasks)
            except Exception:
                pass
    
    def _notify_workflows_updated(self, workflows: List["TUIWorkflow"]) -> None:
        """Notify listeners of workflow updates."""
        self._workflows = workflows
        for callback in self._on_workflows_updated:
            try:
                callback(workflows)
            except Exception:
                pass
    
    def _notify_messages_updated(self, messages: List["TUIMessage"]) -> None:
        """Notify listeners of message updates."""
        for callback in self._on_messages_updated:
            try:
                callback(messages)
            except Exception:
                pass
    
    def _notify_dashboard_updated(self, dashboard: "TUIDashboardState") -> None:
        """Notify listeners of dashboard updates."""
        for callback in self._on_dashboard_updated:
            try:
                callback(dashboard)
            except Exception:
                pass
        # Also notify metrics callbacks with the metrics from dashboard
        self._notify_metrics_updated(dashboard.metrics)
    
    def _notify_metrics_updated(self, metrics: "TUIMetrics") -> None:
        """Notify listeners of metrics updates."""
        for callback in self._on_metrics_updated:
            try:
                callback(metrics)
            except Exception:
                pass
