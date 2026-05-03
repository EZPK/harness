"""
Config Screen for TUI.

Provides configuration interface for LLM provider and other settings.
"""

from typing import Optional

try:
    from textual.app import ComposeResult
    from textual.containers import Container, ScrollableContainer
    from textual.reactive import reactive
    from textual.widget import Widget
    from textual.widgets import Label, Input, Button, Static, Select
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False

from agents.god.agent import GodAgent
from tui.controller import TUIController

# Import ProviderType for type hints (will be imported where needed)
try:
    from providers.base import ProviderType
except ImportError:
    ProviderType = None


class ConfigScreen(Widget):
    """
    Configuration screen for Harness TUI.
    
    Allows users to configure:
    - LLM Provider (Ollama, OpenAI, etc.)
    - Model selection
    - API keys and endpoints
    """
    
    DEFAULT_CSS = """
    ConfigScreen {
        layout: vertical;
        width: 100%;
        height: 1fr;
        background: #1e1e1e;
    }
    
    ConfigScreen .config-container {
        width: 100%;
        height: 1fr;
        background: #121212;
        padding: 1;
        overflow-y: auto;
    }
    
    ConfigScreen .config-section {
        width: 100%;
        margin-bottom: 1;
        padding: 1;
        background: #1e1e1e;
        border-bottom: solid #333;
    }
    
    ConfigScreen .section-title {
        text-style: bold;
        color: #90caf9;
        margin-bottom: 1;
    }
    
    ConfigScreen .config-row {
        layout: horizontal;
        width: 100%;
        margin-bottom: 1;
        height: auto;
    }
    
    ConfigScreen .config-label {
        width: 20;
        color: #9e9e9e;
        text-align: right;
        padding-right: 1;
    }
    
    ConfigScreen Input {
        width: 1fr;
        color: #e0e0e0;
        background: #2d2d2d;
    }
    
    ConfigScreen Button {
        width: auto;
        margin-left: 1;
    }
    
    ConfigScreen .status-message {
        color: #81c784;
        margin-top: 1;
        padding: 0 1;
    }
    
    ConfigScreen .error-message {
        color: #f44336;
        margin-top: 1;
        padding: 0 1;
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
        
        # Configuration state
        self._provider: str = ""
        self._model: str = ""
        self._base_url: str = ""
        self._api_key: str = ""
        self._status_message: str = ""
        self._error_message: str = ""
    
    def compose(self) -> ComposeResult:
        """Compose the config screen layout."""
        yield Label("LLM Configuration", classes="section-title")
        
        # Provider selection
        with Container(classes="config-section"):
            yield Label("LLM Provider Settings", classes="section-title")
            
            # Provider
            with Container(classes="config-row"):
                yield Label("Provider:", classes="config-label")
                yield Select(
                    [("Ollama (Local)", "ollama"),
                     ("OpenAI", "openai"),
                     ("Mistral", "mistral"),
                     ("Anthropic", "anthropic"),
                     ("Google", "google"),
                     ("LiteLLM", "litellm"),
                     ("Custom", "custom")],
                    id="provider-select",
                    value=self._provider if self._provider else "ollama",
                )
            
            # Model
            with Container(classes="config-row"):
                yield Label("Model:", classes="config-label")
                yield Input(
                    placeholder="smollm:135m, gpt-4, claude-3, etc.",
                    id="model-input",
                    value=self._model,
                )
            
            # Base URL (for Ollama/custom)
            with Container(classes="config-row"):
                yield Label("Base URL:", classes="config-label")
                yield Input(
                    placeholder="http://localhost:11434/v1",
                    id="base-url-input",
                    value=self._base_url,
                )
            
            # API Key (for OpenAI, etc.)
            with Container(classes="config-row"):
                yield Label("API Key:", classes="config-label")
                yield Input(
                    placeholder="Your API key (optional)",
                    id="api-key-input",
                    value=self._api_key,
                    password=True,
                )
            
            # Save button
            with Container(classes="config-row"):
                yield Button("Save Configuration", id="save-config-btn")
                yield Button("Test Connection", id="test-connection-btn")
            
            # Status messages
            yield Static(id="status-message", classes="status-message")
            yield Static(id="error-message", classes="error-message")
    
    def on_mount(self) -> None:
        """Load current configuration when mounted."""
        self._load_configuration()
    
    def _load_configuration(self) -> None:
        """Load current LLM configuration."""
        try:
            from configs.llm_config import get_llm_config
            config = get_llm_config()
            
            # Extract provider info
            provider = config.default_provider or "ollama"
            model = ""
            base_url = ""
            
            if "/" in provider:
                parts = provider.split("/")
                provider = parts[0]
                model = parts[1] if len(parts) > 1 else ""
            
            if hasattr(config, 'ollama_base_url'):
                base_url = config.ollama_base_url
            
            # Update state
            self._provider = provider
            self._model = model or getattr(config, 'ollama_model', '')
            self._base_url = base_url
            self._api_key = ""  # Don't show API key for security
            
            # Update UI
            self._update_input_fields()
            
        except Exception as e:
            self._error_message = f"Error loading config: {e}"
            self._update_status_messages()
    
    def _update_input_fields(self) -> None:
        """Update input field values."""
        try:
            provider_select = self.query_one("#provider-select", Select)
            model_input = self.query_one("#model-input", Input)
            base_url_input = self.query_one("#base-url-input", Input)
            api_key_input = self.query_one("#api-key-input", Input)
            
            if provider_select:
                provider_select.value = self._provider if self._provider else "ollama"
            if model_input:
                model_input.value = self._model
            if base_url_input:
                base_url_input.value = self._base_url
            if api_key_input:
                api_key_input.value = self._api_key
                
        except Exception:
            pass
    
    def _update_status_messages(self) -> None:
        """Update status and error message displays."""
        try:
            status_widget = self.query_one("#status-message", Static)
            error_widget = self.query_one("#error-message", Static)
            
            if status_widget:
                status_widget.update(self._status_message)
            if error_widget:
                error_widget.update(self._error_message)
                error_widget.styles.color = "#f44336" if self._error_message else "transparent"
        except Exception:
            pass
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        
        if button_id == "save-config-btn":
            await self._save_configuration()
        elif button_id == "test-connection-btn":
            await self._test_connection()
    
    async def _save_configuration(self) -> None:
        """Save the configuration."""
        try:
            # Get values from inputs
            provider_select = self.query_one("#provider-select", Select)
            model_input = self.query_one("#model-input", Input)
            base_url_input = self.query_one("#base-url-input", Input)
            api_key_input = self.query_one("#api-key-input", Input)
            
            provider = provider_select.value if provider_select else ""
            model = model_input.value.strip() if model_input else ""
            base_url = base_url_input.value.strip() if base_url_input else ""
            api_key = api_key_input.value.strip() if api_key_input else ""
            
            if not provider:
                self._error_message = "Provider cannot be empty"
                self._update_status_messages()
                return
            
            # Save configuration
            self._save_to_env_file(provider, model, base_url, api_key)
            
            # Update in-memory config
            await self._update_runtime_config(provider, model, base_url, api_key)
            
            self._status_message = "✅ Configuration saved!"
            self._error_message = ""
            self._update_status_messages()
            
            # Clear status after delay
            self.set_timer(5.0, self._clear_status)
            
        except Exception as e:
            self._error_message = f"Error saving config: {e}"
            self._status_message = ""
            self._update_status_messages()
    
    def _save_to_env_file(self, provider: str, model: str, base_url: str, api_key: str) -> None:
        """Save configuration to .env file."""
        import os
        from pathlib import Path
        
        env_path = Path(".env")
        
        # Read current .env
        lines = []
        if env_path.exists():
            with open(env_path, "r") as f:
                lines = f.readlines()
        
        # Update or add configuration
        updated_lines = []
        config_keys = {
            "DEFAULT_LLM_PROVIDER": f"{provider}/{model}" if model else provider,
            "OLLAMA_MODEL": model,
            "OLLAMA_BASE_URL": base_url,
            "OLLAMA_API_KEY": api_key,
        }
        
        # Process each key
        for key, value in config_keys.items():
            found = False
            for line in lines:
                stripped = line.strip()
                if stripped.startswith(key + "="):
                    updated_lines.append(f"{key}={value}\n")
                    found = True
                elif stripped and not stripped.startswith("#"):
                    updated_lines.append(line)
                else:
                    # Keep comments and empty lines
                    updated_lines.append(line)
            
            if not found and value:  # Only add if value is not empty
                updated_lines.append(f"{key}={value}\n")
        
        # Write back
        with open(".env", "w") as f:
            f.writelines(updated_lines)
    
    async def _update_runtime_config(self, provider: str, model: str, base_url: str, api_key: str) -> None:
        """Update runtime configuration."""
        from configs.llm_config import reload_llm_config
        from providers.registry import get_registry, create_provider
        
        # Reload config
        reload_llm_config()
        
        # Recreate provider
        registry = get_registry()
        registry.clear()
        
        # Create provider string
        if provider.lower() == "ollama" or base_url:
            provider_str = f"ollama/{model}" if model else provider
        else:
            provider_str = f"{provider}/{model}" if model else provider
        
        # Create provider based on type
        from providers.base import LLMConfig
        from providers.openai_compatible import OpenAICompatibleProvider
        
        # For Ollama or custom OpenAI-compatible endpoints, use OpenAICompatibleProvider
        if provider.lower() == "ollama" or base_url:
            new_provider = OpenAICompatibleProvider(
                model=model,
                api_key=api_key if api_key else None,
                api_base_url=base_url if base_url else None,
                temperature=0.7,
                max_tokens=4096,
                timeout=120.0,
            )
        else:
            # For other providers, use create_provider with LLMConfig
            provider_type_map = {
                "openai": ProviderType.OPENAI,
                "mistral": ProviderType.MISTRAL,
                "anthropic": ProviderType.ANTHROPIC,
                "google": ProviderType.GOOGLE,
                "litellm": ProviderType.LITELLML,
            }
            provider_type = provider_type_map.get(provider.lower(), ProviderType.LITELLML)
            
            llm_config = LLMConfig(
                provider=provider_type,
                model=model,
                api_key=api_key if api_key else None,
                api_base_url=base_url if base_url else None,
                temperature=0.7,
                timeout=120.0,
            )
            new_provider = create_provider(llm_config, name=provider_str)
        
        if new_provider:
            registry.register(provider_str, new_provider, is_default=True)
            
            # Update LLMAgent if it exists
            from agents.specialists.llm_agent import LLMAgent
            llm_agent = None
            if hasattr(self.god, '_agent_registry'):
                for agent in self.god._agent_registry._agents.values():
                    if isinstance(agent, LLMAgent):
                        llm_agent = agent
                        break
            
            if llm_agent:
                llm_agent.provider = new_provider
        
        # Reload controller agents
        await self.controller.refresh()
    
    async def _test_connection(self) -> None:
        """Test the connection to the LLM provider."""
        try:
            provider_select = self.query_one("#provider-select", Select)
            model_input = self.query_one("#model-input", Input)
            base_url_input = self.query_one("#base-url-input", Input)
            
            provider = provider_select.value if provider_select else ""
            model = model_input.value.strip() if model_input else ""
            base_url = base_url_input.value.strip() if base_url_input else ""
            
            if not provider:
                self._error_message = "Provider cannot be empty"
                self._update_status_messages()
                return
            
            self._status_message = "Testing connection..."
            self._error_message = ""
            self._update_status_messages()
            
            # Test with a simple prompt
            from providers.registry import create_provider
            from providers.base import LLMConfig
            from providers.openai_compatible import OpenAICompatibleProvider
            
            # Create provider for testing
            if provider.lower() == "ollama" or base_url:
                test_provider = OpenAICompatibleProvider(
                    model=model,
                    api_key="",
                    api_base_url=base_url if base_url else None,
                    temperature=0.7,
                    max_tokens=5,
                    timeout=30.0,
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
                provider_type = provider_type_map.get(provider.lower(), ProviderType.LITELLML)
                
                test_config = LLMConfig(
                    provider=provider_type,
                    model=model,
                    api_key="",
                    api_base_url=base_url if base_url else None,
                    temperature=0.7,
                    timeout=30.0,
                )
                test_provider = create_provider(test_config)
            
            # Try to call the provider
            try:
                # This will test the connection
                if hasattr(test_provider, 'chat'):
                    from providers.base import LLMMessage, MessageRole
                    result = await test_provider.chat(
                        [LLMMessage(role=MessageRole.USER, content="Say 'hello'")],
                        max_tokens=5
                    )
                elif hasattr(test_provider, 'complete'):
                    result = await test_provider.complete("Say 'hello'", max_tokens=5)
                elif hasattr(test_provider, 'generate'):
                    result = await test_provider.generate("Say 'hello'", max_tokens=5)
                else:
                    result = "Provider has no chat/complete/generate method"
                self._status_message = f"✅ Connection successful! Response: {str(result)[:50]}..."
            except Exception as e:
                self._error_message = f"Connection failed: {e}"
                self._status_message = ""
            
            self._update_status_messages()
            self.set_timer(5.0, self._clear_status)
            
        except Exception as e:
            self._error_message = f"Test error: {e}"
            self._status_message = ""
            self._update_status_messages()
    
    def _clear_status(self) -> None:
        """Clear status messages."""
        self._status_message = ""
        self._error_message = ""
        self._update_status_messages()
