"""
Chat Input Widget for TUI.

Provides a text input area for the chat interface.
"""

import asyncio
from typing import List, Optional, Callable

try:
    from textual.app import ComposeResult
    from textual.containers import Container
    from textual.message import Message
    from textual.reactive import reactive
    from textual.widget import Widget
    from textual.widgets import Input
    from textual import events, on
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


class ChatInput(Container):
    """
    Input widget for the chat interface.
    
    Features:
    - Text input with history
    - Auto-completion
    - Command suggestions
    - Multi-line support
    """
    
    DEFAULT_CSS = """
    ChatInput {
        height: 3;
        width: 100%;
        background: #2d2d2d;
        padding: 0 1;
        layout: horizontal;
    }
    
    ChatInput Input {
        width: 1fr;
        height: 100%;
        color: #e0e0e0;
        background: #2d2d2d;
        border: none;
    }
    
    ChatInput Input:focus {
        border: none;
        outline: none;
    }
    
    ChatInput .prompt {
        width: auto;
        color: #9e9e9e;
    }
    
    ChatInput .history-nav {
        width: auto;
        height: 100%;
    }
    """
    
    # Input state
    input_text: str = reactive("", init=False)
    history: List[str] = reactive([], init=False)
    history_index: int = reactive(-1, init=False)  # -1 means new input
    
    # Completion
    completions: List[str] = reactive([], init=False)
    completion_index: int = reactive(0, init=False)
    
    # Callbacks
    on_submit: Optional[Callable[[str], None]] = None
    
    # Commands for auto-completion
    commands: List[str] = [
        "/task",
        "/agent",
        "/workflow", 
        "/metrics",
        "/provider",
        "/config",
        "/clear",
        "/help",
        "/quit",
    ]
    
    def __init__(
        self,
        on_submit: Optional[Callable[[str], None]] = None,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self.on_submit = on_submit
    
    def compose(self) -> ComposeResult:
        yield from super().compose()
        yield Input(
            placeholder="Type a message or command...",
            id="chat-input",
            classes="chat-input-field"
        )
    
    def on_mount(self) -> None:
        """Focus the input field when mounted."""
        input_widget = self.query_one("#chat-input", Input)
        if input_widget:
            input_widget.focus()
    
    def watch_input_text(self, text: str) -> None:
        """React to input text changes."""
        self._update_completions(text)
    
    def _update_completions(self, text: str) -> None:
        """Update auto-completion suggestions."""
        if text.startswith("/"):
            # Command completion
            prefix = text[1:]
            self.completions = [
                cmd for cmd in self.commands 
                if cmd.startswith(prefix)
            ]
        else:
            self.completions = []
    
    def _complete(self) -> None:
        """Apply current completion."""
        if self.completions and self.completion_index < len(self.completions):
            input_widget = self.query_one("#chat-input", Input)
            current_text = input_widget.value
            
            # Find what to replace
            if current_text.startswith("/"):
                prefix_len = len(current_text)
                completion = self.completions[self.completion_index]
                new_text = "/" + completion + " "
                input_widget.value = new_text
                input_widget.cursor_position = len(new_text)
    
    def _cycle_completion(self, forward: bool = True) -> None:
        """Cycle through completions."""
        if not self.completions:
            return
        
        if forward:
            self.completion_index = (self.completion_index + 1) % len(self.completions)
        else:
            self.completion_index = (self.completion_index - 1) % len(self.completions)
    
    def _navigate_history(self, backward: bool = True) -> None:
        """Navigate through input history."""
        input_widget = self.query_one("#chat-input", Input)
        
        if backward:
            # Go to previous (older) history item
            if self.history_index < len(self.history) - 1:
                self.history_index += 1
                if self.history_index < len(self.history):
                    input_widget.value = self.history[self.history_index]
                    self.input_text = input_widget.value
        else:
            # Go to next (newer) history item
            if self.history_index > 0:
                self.history_index -= 1
                if self.history_index < len(self.history):
                    input_widget.value = self.history[self.history_index]
                    self.input_text = input_widget.value
            elif self.history_index == 0:
                # Clear to new input
                self.history_index = -1
                input_widget.value = ""
                self.input_text = ""
    
    async def submit(self) -> None:
        """Submit the current input."""
        input_widget = self.query_one("#chat-input", Input)
        text = input_widget.value.strip()
        
        if text:
            # Add to history
            self.history = self.history + [text]
            self.history_index = -1
            
            # Call submit callback (can be async)
            if self.on_submit:
                # If callback is a coroutine, await it
                result = self.on_submit(text)
                if asyncio.iscoroutine(result):
                    await result
            
            # Clear input
            input_widget.value = ""
            self.input_text = ""
    
    def add_command(self, command: str) -> None:
        """Add a command to the auto-completion list."""
        if command not in self.commands:
            self.commands.append(command)
    
    def remove_command(self, command: str) -> None:
        """Remove a command from the auto-completion list."""
        if command in self.commands:
            self.commands.remove(command)
    
    @on(Input.Changed, "#chat-input")
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes."""
        self.input_text = event.value
        self.history_index = -1  # Reset history navigation on new input
    
    @on(Input.Submitted, "#chat-input")
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        await self.submit()


class ChatInputSubmitted(Message):
    """Message emitted when chat input is submitted."""
    
    def __init__(self, text: str):
        self.text = text
        super().__init__()
