"""
Chat Screen for TUI.

Displays the chat interface with message history and input.
"""

import asyncio
from typing import List, Optional, Any

try:
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, ScrollableContainer
    from textual.reactive import reactive
    from textual.widget import Widget
    from textual.widgets import Label
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False

from agents.god.agent import GodAgent
from providers.registry import get_registry, create_provider
from configs.llm_config import get_llm_config, reload_llm_config
from tui.controller import TUIController
from tui.models import TUIMessage
from tui.widgets.chat_input import ChatInput
from tui.widgets.chat_message import ChatMessage
from tui.widgets.provider_config_modal import ProviderConfigModal


class ChatScreen(Widget):
    """
    Chat widget for interacting with the God Agent.
    
    Features:
    - Message history display
    - Chat input with commands
    - Auto-scrolling
    - Message selection and copy-paste
    """
    
    # Bindings for message navigation and copy
    BINDINGS = [
        Binding(key="shift+up", action="select_previous_message", description="Select previous message"),
        Binding(key="shift+down", action="select_next_message", description="Select next message"),
        Binding(key="ctrl+c", action="copy_selected_message", description="Copy selected message"),
        Binding(key="escape", action="clear_selection", description="Clear selection"),
    ]
    
    DEFAULT_CSS = """
    ChatScreen {
        layout: vertical;
        width: 100%;
        height: 1fr;
        background: #1e1e1e;
    }
    
    ChatScreen .messages-container {
        width: 100%;
        height: 1fr;
        background: #121212;
        padding: 1;
        overflow-y: auto;
    }
    
    ChatScreen .input-container {
        width: 100%;
        height: auto;
        dock: bottom;
        background: #2d2d2d;
        padding: 0 1;
    }
    
    ChatScreen .welcome-message {
        color: #9e9e9e;
        text-style: italic;
        padding: 1;
    }
    
    ChatScreen ChatInput {
        height: 3;
    }
    
    ChatScreen ChatMessage {
        width: 100%;
        height: auto;
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
        
        # Messages
        self._messages: List[TUIMessage] = []
        # Selection state
        self.selected_message_index: Optional[int] = None
        # Store message widgets for selection management
        self._message_widgets: List[ChatMessage] = []
    
    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        # Input container (docked at bottom, must be first in compose)
        with Container(classes="input-container"):
            yield ChatInput(
                on_submit=self._on_message_submit,
                id="chat-input"
            )
        
        # Messages container (takes remaining space)
        with ScrollableContainer(classes="messages-container", id="messages-container"):
            yield Label(
                "Welcome to Harness TUI! Type /help for available commands.",
                classes="welcome-message"
            )
    
    def on_mount(self) -> None:
        """Called after the widget is mounted."""
        # Register for message updates
        self.controller.on_messages_updated(self._on_messages_updated)
        
        # Load initial messages
        self._on_messages_updated(self._messages)
    
    def on_unmount(self) -> None:
        """Called when the widget is unmounted."""
        # Unregister from updates
        try:
            self.controller._on_messages_updated.remove(self._on_messages_updated)
        except (ValueError, AttributeError):
            pass
    
    def _on_messages_updated(self, messages: List[TUIMessage]) -> None:
        """Handle message updates."""
        self._messages = messages
        self._update_messages_container()
    
    def _update_messages_container(self) -> None:
        """Update the messages container with current messages."""
        container = self.query_one("#messages-container", ScrollableContainer)
        if not container:
            return
        
        # Clear existing messages (keep welcome message if it's the first)
        children = list(container.children)
        if len(children) > 1:  # Keep welcome message
            for child in children[1:]:
                child.remove()
        
        # Clear message widgets list
        self._message_widgets = []
        
        # Add new messages
        for idx, message in enumerate(self._messages):
            msg_widget = ChatMessage(message=message, on_click=self._on_message_click)
            # Check if this message is selected
            if self.selected_message_index == idx:
                msg_widget.is_selected = True
            container.mount(msg_widget)
            self._message_widgets.append(msg_widget)
        
        # Scroll to bottom
        container.scroll_end(animate=False)

    def _on_message_click(self, widget: ChatMessage) -> None:
        """Handle click on a message widget."""
        # Find the index of the clicked widget
        try:
            idx = self._message_widgets.index(widget)
            self._select_message(idx)
            # Give focus to this screen so keyboard navigation works
            self.focus()
        except (ValueError, AttributeError):
            pass
    
    def _select_message(self, index: Optional[int]) -> None:
        """Select a message by index."""
        if index is None:
            # Clear selection
            self.selected_message_index = None
        else:
            if 0 <= index < len(self._messages):
                self.selected_message_index = index
            else:
                self.selected_message_index = None
        
        # Update widget selection states
        for idx, widget in enumerate(self._message_widgets):
            widget.is_selected = (idx == self.selected_message_index)
    
    def action_select_previous_message(self) -> None:
        """Select the previous message."""
        if len(self._messages) == 0:
            return
        
        if self.selected_message_index is None:
            # Select the last message
            self._select_message(len(self._messages) - 1)
        else:
            new_index = self.selected_message_index - 1
            if new_index < 0:
                new_index = 0
            self._select_message(new_index)
        
        # Scroll to make selected message visible
        self._scroll_to_selected()
    
    def action_select_next_message(self) -> None:
        """Select the next message."""
        if len(self._messages) == 0:
            return
        
        if self.selected_message_index is None:
            # Select the first message
            self._select_message(0)
        else:
            new_index = self.selected_message_index + 1
            if new_index >= len(self._messages):
                new_index = len(self._messages) - 1
            self._select_message(new_index)
        
        # Scroll to make selected message visible
        self._scroll_to_selected()
    
    def action_copy_selected_message(self) -> None:
        """Copy the selected message content to clipboard."""
        if self.selected_message_index is not None and 0 <= self.selected_message_index < len(self._messages):
            message = self._messages[self.selected_message_index]
            # Format: [sender] content
            copy_text = f"[{message.sender_display}] {message.content}"
            
            try:
                # Use Textual's clipboard
                if hasattr(self.app, 'clipboard'):
                    self.app.clipboard = copy_text
                else:
                    # Fallback: try pyperclip
                    try:
                        import pyperclip
                        pyperclip.copy(copy_text)
                    except ImportError:
                        # Last resort: show info in chat
                        self.add_message(self._create_info_message(f"Message to copy: {copy_text[:150]}{'...' if len(copy_text) > 150 else ''}"))
            except Exception as e:
                self.add_message(self._create_error_message(f"Failed to copy: {e}"))
    
    def action_clear_selection(self) -> None:
        """Clear the current message selection."""
        self._select_message(None)
    
    def _scroll_to_selected(self) -> None:
        """Scroll to the selected message."""
        if self.selected_message_index is not None and self._message_widgets:
            try:
                widget = self._message_widgets[self.selected_message_index]
                widget.scroll_visible()
            except Exception:
                pass
    
    def _scroll_to_bottom(self) -> None:
        """Scroll messages container to bottom."""
        try:
            container = self.query_one("#messages-container", ScrollableContainer)
            if container:
                container.scroll_end(animate=False)
        except Exception:
            pass
    
    def _create_info_message(self, content: str) -> "TUIMessage":
        """Create an info message."""
        from tui.models import create_god_response_message
        return create_god_response_message(content, msg_type="info")
    
    def _create_error_message(self, content: str) -> "TUIMessage":
        """Create an error message."""
        from tui.models import create_error_message
        return create_error_message(content, "")
    
    async def _on_message_submit(self, text: str) -> None:
        """Handle message submission with streaming support."""
        if not text:
            return
        
        # Handle /quit command
        if text.strip() == "/quit":
            self.app.exit()
            return
        
        # Handle special command for provider modal
        if text.strip() == "/provider open":
            await self._open_provider_modal()
            return
        
        # Add user message immediately
        from tui.models import create_task_submission_message
        user_msg = create_task_submission_message(text, text)
        self.add_message(user_msg)
        
        # Show typing indicator
        typing_indicator = Label("GodAgent est en train de réfléchir...", classes="typing-indicator")
        messages_container = self.query_one("#messages-container", ScrollableContainer)
        messages_container.mount(typing_indicator)
        self._scroll_to_bottom()
        
        try:
            # Get response stream from controller
            response_stream = self.controller.chat_stream(text)
            
            # Create placeholder for response
            full_response = ""
            first_chunk = True
            response_widget = None
            response_msg = None
            
            async for chunk in response_stream:
                if first_chunk:
                    # Remove typing indicator
                    try:
                        messages_container.query(".typing-indicator").remove()
                    except:
                        pass
                    
                    # Create response message widget with empty content
                    from tui.models import create_god_response_message, TUIMessage
                    response_msg = create_god_response_message("", msg_type="result")
                    response_widget = ChatMessage(message=response_msg)
                    messages_container.mount(response_widget)
                    first_chunk = False
                
                # Append chunk to full response
                full_response += chunk
                
                # Update widget content directly (no flickering)
                if response_widget and response_msg:
                    # Update the message object's content (reactive property will trigger refresh)
                    response_msg.content = full_response + "▌"  # Blinking cursor indicator
                    # Force refresh the widget
                    response_widget.refresh()
                
                # Auto-scroll
                self._scroll_to_bottom()
                
                # Small delay to allow UI to update
                await asyncio.sleep(0.01)
            
            # Remove the cursor indicator and finalize
            if response_msg:
                response_msg.content = full_response
                if response_widget:
                    response_widget.refresh()
            
            # Add to message history
            from tui.models import create_god_response_message
            final_msg = create_god_response_message(full_response, msg_type="result")
            self._messages.append(final_msg)
            
        except Exception as e:
            # Remove typing indicator
            try:
                messages_container.query(".typing-indicator").remove()
            except:
                pass
            
            # Add error message
            from tui.models import create_error_message
            error_msg = create_error_message(str(e), "")
            self.add_message(error_msg)
        
        # Clean up any remaining typing indicator
        try:
            messages_container.query(".typing-indicator").remove()
        except:
            pass
    
    def add_message(self, message: TUIMessage) -> None:
        """Add a message to the chat."""
        self._messages.append(message)
        self._update_messages_container()
    
    def clear_messages(self) -> None:
        """Clear all messages."""
        self._messages = []
        self._update_messages_container()
    
    async def _open_provider_modal(self) -> None:
        """Open the provider configuration modal."""
        try:
            config = get_llm_config()
            
            # Extract current provider info
            current_provider = config.default_provider or "Ollama"
            current_model = ""
            
            # Try to extract model from provider string
            if "/" in current_provider:
                parts = current_provider.split("/")
                current_provider = parts[0]
                current_model = parts[1] if len(parts) > 1 else ""
            elif hasattr(config, 'ollama_model') and config.ollama_model:
                current_model = config.ollama_model
            
            # Create the modal
            modal = ProviderConfigModal(
                current_provider=current_provider,
                current_model=current_model or "smollm:135m",
                on_save=self._on_provider_save,
                on_cancel=self._on_provider_cancel,
            )
            
            # Mount the modal
            self.mount(modal)
            modal.focus()
            
        except Exception as e:
            from tui.widgets.chat_message import ChatMessage
            from tui.models import create_error_message
            self.add_message(create_error_message(f"Error opening config: {e}", ""))
    
    async def _on_provider_save(
        self, 
        provider: str, 
        model: str, 
        base_url: str, 
        api_key: str
    ) -> None:
        """Handle provider configuration save."""
        try:
            # Update .env file
            self._update_env_file(provider, model, base_url, api_key)
            
            # Reload configuration
            reload_llm_config()
            
            # Recreate provider in registry
            registry = get_registry()
            registry.clear()
            
            # Create the provider string
            if provider.lower() == "ollama":
                provider_str = f"ollama/{model}"
            else:
                provider_str = f"{provider}/{model}" if model else provider
            
            # Create provider based on type
            from providers.base import LLMConfig, ProviderType
            from providers.openai_compatible import OpenAICompatibleProvider
            
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
                # Map provider name to ProviderType
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
                new_provider = create_provider(llm_config)
            
            if new_provider:
                registry.register(provider_str, new_provider, is_default=True)
            
            # Add success message - use call_later to ensure it's processed after modal closes
            from tui.models import create_god_response_message
            msg = create_god_response_message(
                f"✅ Provider changed to: {provider_str}",
                msg_type="info"
            )
            # Schedule message addition after a brief delay to avoid DOM conflicts
            self.call_later(self._add_provider_message, msg)
            
        except Exception as e:
            from tui.models import create_error_message
            error_msg = create_error_message(f"Error saving config: {e}", "")
            self.call_later(self._add_provider_message, error_msg)
    
    def _add_provider_message(self, message: "TUIMessage") -> None:
        """Add a message to chat, called via call_later to avoid timing issues."""
        self.add_message(message)
    
    async def _on_provider_cancel(self) -> None:
        """Handle provider configuration cancel."""
        pass  # Just close the modal
    
    def _update_env_file(
        self, 
        provider: str, 
        model: str, 
        base_url: str, 
        api_key: str
    ) -> None:
        """Update the .env file with new configuration."""
        import os
        from pathlib import Path
        
        env_path = Path(".env")
        if not env_path.exists():
            env_path = Path(".env.example")
        
        # Read current .env
        lines = []
        if env_path.exists():
            with open(env_path, "r") as f:
                lines = f.readlines()
        
        # Update or add configuration lines
        updated_lines = []
        config_key = "DEFAULT_LLM_PROVIDER"
        model_key = "OLLAMA_MODEL"
        url_key = "OLLAMA_BASE_URL"
        
        # Mapping of provider to config
        provider_map = {
            "Ollama": f"ollama/{model}",
        }
        
        provider_str = provider_map.get(provider, f"{provider}/{model}" if model else provider)
        
        # Update existing keys or add new ones
        found_provider = False
        found_model = False
        found_url = False
        
        for line in lines:
            stripped = line.strip()
            
            if stripped.startswith(config_key + "="):
                updated_lines.append(f"{config_key}={provider_str}\n")
                found_provider = True
            elif stripped.startswith(model_key + "="):
                if provider.lower() == "ollama":
                    updated_lines.append(f"{model_key}={model}\n")
                found_model = True
            elif stripped.startswith(url_key + "="):
                if provider.lower() == "ollama" and base_url:
                    updated_lines.append(f"{url_key}={base_url}\n")
                found_url = True
            elif stripped.startswith("#") or not stripped:
                updated_lines.append(line)
            else:
                updated_lines.append(line)
        
        # Add missing keys
        if not found_provider:
            updated_lines.append(f"{config_key}={provider_str}\n")
        
        if provider.lower() == "ollama":
            if not found_model:
                updated_lines.append(f"{model_key}={model}\n")
            if not found_url and base_url:
                updated_lines.append(f"{url_key}={base_url}\n")
        
        # Write back to .env
        with open(".env", "w") as f:
            f.writelines(updated_lines)
