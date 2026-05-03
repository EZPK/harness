"""
Provider Configuration Modal for TUI.

Allows users to change LLM provider and model settings from the TUI.
"""

from typing import Optional, Callable, List, Dict, Any

try:
    from textual.app import ComposeResult
    from textual.containers import Container, Vertical, Horizontal
    from textual.message import Message
    from textual.reactive import reactive
    from textual.widget import Widget
    from textual.widgets import (
        Button,
        Input,
        Label,
        ListItem,
        ListView,
        Select,
        Static,
    )
    from textual import on, events
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


class ProviderConfigModal(Container):
    """
    Modal dialog for configuring LLM provider and model.
    
    Allows users to:
    - Select from available providers
    - Select from available models for each provider
    - Save the configuration
    """
    
    DEFAULT_CSS = """
    ProviderConfigModal {
        layout: vertical;
        height: 100%;
        width: 100%;
        background: black 70%;
        z-index: 1000;
    }
    
    ProviderConfigModal .modal-content {
        layout: vertical;
        height: auto;
        width: 80%;
        max-width: 80;
        max-height: 80%;
        background: $surface;
        border: round $primary 80%;
        padding: 1 2;
        
        /* Center the modal content */
        dock: none;
        offset-x: 50%;
        offset-y: 50%;
        transform: translate(-50%, -50%);
    }
    
    ProviderConfigModal .title {
        text-style: bold;
        text-align: center;
        color: $primary;
        margin-bottom: 1;
    }
    
    ProviderConfigModal .section {
        margin-bottom: 1;
    }
    
    ProviderConfigModal .section-label {
        text-style: bold;
        color: $accent;
        margin-bottom: 0;
    }
    
    ProviderConfigModal ListView {
        height: 10;
        border: solid $primary 30%;
    }
    
    ProviderConfigModal Select {
        width: 100%;
    }
    
    ProviderConfigModal Input {
        width: 100%;
    }
    
    ProviderConfigModal .buttons {
        layout: horizontal;
        height: auto;
        margin-top: 1;
        justify-content: center;
    }
    
    ProviderConfigModal Button {
        width: auto;
        min-width: 10;
        margin: 0 1;
    }
    
    ProviderConfigModal .status {
        text-align: center;
        color: $success;
        margin-top: 1;
    }
    
    ProviderConfigModal .error {
        text-align: center;
        color: $error;
        margin-top: 1;
    }
    """
    
    # Available providers
    PROVIDERS: Dict[str, List[str]] = {
        "Ollama": ["llama3", "llama3:8b", "mistral", "phi3", "qwen2.5:3b", "smollm:135m", "smollm:2b"],
        "Mistral": ["mistral-tiny", "mistral-small", "mistral-medium", "mistral-large", "mixtral-8x7b", "mixtral-8x22b"],
        "OpenAI": ["gpt-4", "gpt-4-32k", "gpt-3.5-turbo", "gpt-3.5-turbo-16k"],
        "Anthropic": ["claude-3-sonnet", "claude-3-haiku", "claude-3-opus", "claude-2"],
        "Google": ["gemini-pro", "gemini-ultra"],
        "Local vLLM": ["hosted_vllm/llama2", "hosted_vllm/mistral"],
    }
    
    # Current selection
    selected_provider: str = reactive("Ollama", init=False)
    selected_model: str = reactive("smollm:135m", init=False)
    custom_base_url: str = reactive("", init=False)
    custom_api_key: str = reactive("", init=False)
    
    # Status
    status_message: str = reactive("", init=False)
    error_message: str = reactive("", init=False)
    
    # Callbacks
    on_save: Optional[Callable[[str, str, str, str], None]] = None
    on_cancel: Optional[Callable[[], None]] = None
    
    def __init__(
        self,
        current_provider: str = "",
        current_model: str = "",
        on_save: Optional[Callable[[str, str, str, str], None]] = None,
        on_cancel: Optional[Callable[[], None]] = None,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self.on_save = on_save
        self.on_cancel = on_cancel
        
        # Set initial values
        if current_provider:
            self.selected_provider = current_provider
        if current_model:
            self.selected_model = current_model
    
    def compose(self) -> ComposeResult:
        # Modal content container (centered)
        with Container(classes="modal-content"):
            yield Label("LLM Provider Configuration", classes="title")
            
            # Provider selection
            with Vertical(classes="section"):
                yield Label("Provider:", classes="section-label")
                yield Select(
                    [(p, p) for p in self.PROVIDERS.keys()],
                    id="provider-select",
                    value=self.selected_provider,
                )
            
            # Model selection
            with Vertical(classes="section"):
                yield Label("Model:", classes="section-label")
                yield Select(
                    [(m, m) for m in self.PROVIDERS.get(self.selected_provider, [])],
                    id="model-select",
                    value=self.selected_model,
                )
            
            # Custom settings for Ollama/Local
            with Vertical(classes="section") as custom_section:
                yield Label("Custom Settings:", classes="section-label")
                yield Input(placeholder="Base URL (e.g., http://localhost:11434/v1)", id="base-url-input")
                yield Input(placeholder="API Key (optional for local providers)", id="api-key-input", password=True)
            
            # Buttons
            with Horizontal(classes="buttons"):
                yield Button("Save", id="save-btn", variant="primary")
                yield Button("Cancel", id="cancel-btn", variant="secondary")
            
            # Status message
            yield Static(id="status-msg")
            yield Static(id="error-msg")
    
    def on_mount(self) -> None:
        """Initialize the modal after mounting."""
        provider_select = self.query_one("#provider-select", Select)
        model_select = self.query_one("#model-select", Select)
        base_url_input = self.query_one("#base-url-input", Input)
        api_key_input = self.query_one("#api-key-input", Input)
        
        # Set initial values
        provider_select.value = self.selected_provider
        model_select.value = self.selected_model
        
        # Set custom settings based on provider
        self._update_custom_settings_visibility()
        
        # Pre-fill base URL for Ollama
        if self.selected_provider == "Ollama":
            base_url_input.value = "http://localhost:11434/v1"
    
    def watch_selected_provider(self, provider: str) -> None:
        """Update model list when provider changes."""
        model_select = self.query_one("#model-select", Select)
        models = self.PROVIDERS.get(provider, [])
        model_select.set_options([(m, m) for m in models])
        
        if models and self.selected_model not in models:
            self.selected_model = models[0]
        
        self._update_custom_settings_visibility()
    
    def _update_custom_settings_visibility(self) -> None:
        """Show/hide custom settings based on provider."""
        base_url_input = self.query_one("#base-url-input", Input)
        api_key_input = self.query_one("#api-key-input", Input)
        
        if self.selected_provider in ["Ollama", "Local vLLM"]:
            base_url_input.display = True
        else:
            base_url_input.display = False
    
    @on(Select.Changed, "#provider-select")
    def on_provider_changed(self, event: Select.Changed) -> None:
        """Handle provider selection change."""
        self.selected_provider = event.value
    
    @on(Select.Changed, "#model-select")
    def on_model_changed(self, event: Select.Changed) -> None:
        """Handle model selection change."""
        self.selected_model = event.value
    
    @on(Button.Pressed, "#save-btn")
    def on_save_pressed(self, event: Button.Pressed) -> None:
        """Handle save button press."""
        base_url_input = self.query_one("#base-url-input", Input)
        api_key_input = self.query_one("#api-key-input", Input)
        status_msg = self.query_one("#status-msg", Static)
        error_msg = self.query_one("#error-msg", Static)
        
        try:
            # Show saving message
            status_msg.update("Saving configuration...")
            error_msg.update("")
            self.app.refresh()
            
            # Call save callback
            if self.on_save:
                self.on_save(
                    self.selected_provider,
                    self.selected_model,
                    base_url_input.value,
                    api_key_input.value,
                )
            
            status_msg.update("✅ Configuration saved!")
            error_msg.update("")
            self.app.refresh()
            
            # Close after a brief delay
            self.call_after(1.5, self._close_modal)
            
        except Exception as e:
            error_msg.update(f"❌ Error: {str(e)}")
            status_msg.update("")
            self.app.refresh()
    
    @on(Button.Pressed, "#cancel-btn")
    def on_cancel_pressed(self, event: Button.Pressed) -> None:
        """Handle cancel button press."""
        if self.on_cancel:
            self.on_cancel()
        self._close_modal()
    
    def on_key(self, event: events.Key) -> None:
        """Handle key events."""
        if event.key == "escape":
            if self.on_cancel:
                self.on_cancel()
            self._close_modal()
            event.stop()
    
    def _close_modal(self) -> None:
        """Close the modal."""
        self.remove()
    
    def focus(self) -> None:
        """Focus the first select widget."""
        provider_select = self.query_one("#provider-select", Select)
        if provider_select:
            provider_select.focus()


class ProviderConfigSave(Message):
    """Message emitted when provider configuration is saved."""
    
    def __init__(
        self,
        provider: str,
        model: str,
        base_url: str = "",
        api_key: str = "",
    ):
        self.provider = provider
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        super().__init__()
