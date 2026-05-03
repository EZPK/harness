"""
Harness TUI Application.

The main Textual application for the Harness Agentic Framework TUI.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Flag to check if Textual is available
HAS_TEXTUAL = False

try:
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Container
    from textual.message import Message
    from textual.reactive import reactive
    from textual.screen import Screen
    from textual.widget import Widget
    from textual.widgets import Header, Footer, TabbedContent, TabPane
    HAS_TEXTUAL = True
except ImportError:
    pass

from agents.god.agent import GodAgent
from tui.controller import TUIController, TUIControllerConfig


# Only define the TUI classes if Textual is available
if HAS_TEXTUAL:
    class HarnessTUIApp(App):
        """
        Main Textual application for the Harness TUI.
        
        This is the entry point for the Terminal User Interface.
        It manages the main screen with tabs for different views.
        """
        
        # Application metadata
        TITLE = "Harness Agentic Framework TUI"
        SUB_TITLE = "Interact with the God Agent"
        VERSION = "0.1.0"
        
        # CSS styling
        CSS = """
        TabbedContent {
            width: 100%;
            height: 1fr;
        }
        TabPane {
            width: 100%;
            height: 1fr;
        }
        Header {
            background: #1e88e5;
            color: #e0e0e0;
            text-style: bold;
        }
        Footer {
            background: #1e1e1e;
            color: #9e9e9e;
        }
        """
        
        # Key bindings
        BINDINGS = [
            Binding(key="q", action="quit", description="Quit"),
            Binding(key="tab", action="next_tab", description="Next Tab"),
            Binding(key="shift+tab", action="prev_tab", description="Prev Tab"),
            Binding(key="ctrl+r", action="refresh", description="Refresh"),
        ]
        
        def __init__(
            self,
            god_agent: Optional[GodAgent] = None,
            controller_config: Optional[TUIControllerConfig] = None,
        ):
            """
            Initialize the Harness TUI Application.
            
            Args:
                god_agent: Optional God Agent instance (created if not provided)
                controller_config: Optional TUI controller configuration
            """
            super().__init__()
            
            # Create or use provided God Agent
            self.god = god_agent or GodAgent()
            
            # Create controller
            self.controller = TUIController(
                self.god,
                controller_config or TUIControllerConfig()
            )
            
            # State
            self._is_ready = False
            self._llm_agent_configured = god_agent is not None  # Skip auto-config if God Agent provided
        
        async def on_ready(self) -> None:
            """Called when the app is ready to start."""
            # Auto-configure LLMAgent if not already done
            if not self._llm_agent_configured:
                await self._setup_llm_agent()
                self._llm_agent_configured = True
            
            # Initialize the controller
            await self.controller.initialize()
            await self.controller.start()
            
            # Mark as ready
            self._is_ready = True
            
            # Set up the title
            self.title = f"{self.TITLE} v{self.VERSION}"
            self.sub_title = self.SUB_TITLE
        
        async def on_shutdown(self) -> None:
            """Called when the app is shutting down."""
            # Stop the controller
            await self.controller.stop()
        
        def compose(self) -> ComposeResult:
            """Compose the main app layout."""
            from tui.screens import ChatScreen, AgentsScreen, TasksScreen, WorkflowsScreen, MetricsScreen, ConfigScreen
            
            yield Header()
            with TabbedContent():
                # Chat tab
                with TabPane("Chat", id="chat-tab"):
                    yield ChatScreen(self.god, self.controller)
                
                # Agents tab
                with TabPane("Agents", id="agents-tab"):
                    yield AgentsScreen(self.god, self.controller)
                
                # Tasks tab
                with TabPane("Tasks", id="tasks-tab"):
                    yield TasksScreen(self.god, self.controller)
                
                # Workflows tab
                with TabPane("Workflows", id="workflows-tab"):
                    yield WorkflowsScreen(self.god, self.controller)
                
                # Metrics tab
                with TabPane("Metrics", id="metrics-tab"):
                    yield MetricsScreen(self.god, self.controller)
                
                # Config tab
                with TabPane("Config", id="config-tab"):
                    yield ConfigScreen(self.god, self.controller)
            yield Footer()
        
        async def action_quit(self) -> None:
            """Quit the application."""
            self.exit()
        
        async def action_refresh(self) -> None:
            """Refresh all data."""
            await self.controller.refresh()
        
        async def _setup_llm_agent(self) -> None:
            """Setup LLMAgent with default provider if available."""
            try:
                from providers import get_registry, register_provider
                from providers.openai_compatible import OpenAICompatibleProvider
                from providers.lite_llm import LiteLLMProvider
                from configs.llm_config import get_llm_config, reload_llm_config
                from agents.specialists.llm_agent import LLMAgent
                
                # Reload config to pick up any .env changes
                reload_llm_config()
                
                # Try to get default provider from config
                config = get_llm_config()
                registry = get_registry()
                
                default_provider = None
                
                # If config has a default provider, try to create it
                if config.default_provider:
                    # Check if provider already registered
                    if registry.get(config.default_provider):
                        default_provider = registry.get(config.default_provider)
                    else:
                        # Handle Ollama specifically
                        provider_str = config.default_provider.lower()
                        
                        if "ollama" in provider_str or provider_str.startswith("http"):
                            # Ollama or custom OpenAI-compatible endpoint
                            model = config.default_provider
                            if "ollama/" in config.default_provider:
                                model = config.default_provider.split("/")[1]
                            
                            base_url = getattr(config, 'ollama_base_url', 'http://localhost:11434/v1')
                            
                            default_provider = OpenAICompatibleProvider(
                                model=model,
                                api_key="",  # Ollama doesn't need API key
                                api_base_url=base_url,
                                temperature=config.default_temperature,
                                max_tokens=getattr(config, 'default_max_tokens', None) or 4096,
                                timeout=config.default_timeout,
                            )
                            registry.register(config.default_provider, default_provider, as_default=True)
                        else:
                            # Use LiteLLM for other providers
                            from providers.base import LLMConfig, ProviderType
                            from providers.lite_llm import LiteLLMProvider
                            llm_config = LLMConfig(
                                provider=ProviderType.LITELLML,
                                model=config.default_provider,
                                api_key="",
                                api_base_url="",
                                temperature=config.default_temperature,
                                max_tokens=getattr(config, 'default_max_tokens', None) or 4096,
                                timeout=config.default_timeout,
                            )
                            default_provider = LiteLLMProvider(config=llm_config)
                            registry.register(config.default_provider, default_provider, as_default=True)
                else:
                    default_provider = registry.get_default()
                
                # Also check for any existing registered provider
                if default_provider is None:
                    default_provider = registry.get_default()
                
                if default_provider is not None:
                    llm_agent = LLMAgent(
                        name="LLMAgent",
                        provider=default_provider,
                        system_prompt="""
                        You are a helpful AI assistant in the Harness Agentic Framework.
                        You assist with coding, analysis, planning, and any other tasks.
                        Always respond in French if the user writes in French.
                        Be concise and helpful.
                        """
                    )
                    await llm_agent.initialize()
                    await self.god.agent_registry.register(llm_agent)
                    # Notify in TUI (don't print to console, it goes to logs)
                    logger.info(f"LLMAgent registered with provider: {default_provider.model}")
                else:
                    logger.warning("No default LLM provider configured. Use /provider to configure.")
            except Exception as e:
                logger.error(f"Could not auto-configure LLMAgent: {e}")
                logger.debug(f"Traceback: {e}", exc_info=True)


# Entry point for running the TUI
async def run_tui(god_agent: Optional[GodAgent] = None) -> None:
    """
    Run the Harness TUI.
    
    Args:
        god_agent: Optional God Agent instance to use
    """
    if not HAS_TEXTUAL:
        logger.error("Textual is not installed. Please install it with:")
        logger.error("  pip install textual>=0.48.0")
        return
    
    app = HarnessTUIApp(god_agent)
    await app.run_async()


def run_tui_sync(god_agent: Optional[GodAgent] = None) -> None:
    """
    Run the Harness TUI synchronously.
    
    Args:
        god_agent: Optional God Agent instance to use
    """
    if not HAS_TEXTUAL:
        logger.error("Textual is not installed. Please install it with:")
        logger.error("  pip install textual>=0.48.0")
        return
    
    asyncio.run(run_tui(god_agent))
