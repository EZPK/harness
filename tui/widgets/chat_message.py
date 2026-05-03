"""
Chat Message Widget for TUI.

Displays a single chat message with sender, content, and timestamp.
"""

from typing import Optional, Callable, Any, TYPE_CHECKING

try:
    from textual.app import ComposeResult
    from textual.containers import Container
    from textual.reactive import reactive
    from textual.widget import Widget
    from textual.messages import Click
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False
    Click = Any  # type: ignore

from tui.models import TUIMessage, TUIMessageSender, TUIMessageType


class ChatMessage(Widget):
    """
    Widget that displays a chat message.
    
    Shows: sender, content, timestamp, type indicators.
    """
    
    DEFAULT_CSS = """
    ChatMessage {
        width: 100%;
        height: auto;
        padding: 0 1;
        
        &.user {
            text-style: bold;
        }
        
        &.god {
            text-style: bold;
        }
        
        &.agent {
            text-style: italic;
        }
        
        &.error {
            color: #f44336;
        }
        
        &.warning {
            color: #ff9800;
        }
        
        &.system {
            color: #9e9e9e;
            opacity: 0.7;
        }
        
        &.selected {
            background: #3a3a5a;
            color: #ffffff;
        }
        
        .sender {
            width: 12;
            dock: left;
            text-style: bold;
            padding-right: 1;
        }
        
        .timestamp {
            width: 10;
            dock: right;
            color: #9e9e9e;
            padding-left: 1;
        }
        
        .content {
            width: 1fr;
            height: auto;
        }
        
        .type-indicator {
            width: 3;
            dock: left;
            padding-right: 1;
        }
    }
    """
    
    # Message data
    message: Optional[TUIMessage] = reactive(None, init=False)
    is_selected: bool = reactive(False, init=False)
    on_click: Optional[Callable[[Any], None]] = None
    
    def __init__(
        self,
        message: Optional[TUIMessage] = None,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
        on_click: Optional[Callable[[Any], None]] = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self.message = message
        self.on_click = on_click
    
    def compose(self) -> ComposeResult:
        yield from super().compose()
    
    def watch_message(self, message: Optional[TUIMessage]) -> None:
        """React to message changes."""
        if message:
            # Update classes based on sender and type
            self.set_class(False, "user", "god", "agent", "error", "warning", "system")
            
            if message.sender == TUIMessageSender.USER:
                self.set_class(True, "user")
            elif message.sender == TUIMessageSender.GOD_AGENT:
                self.set_class(True, "god")
            elif message.sender == TUIMessageSender.AGENT:
                self.set_class(True, "agent")
            elif message.sender == TUIMessageSender.SYSTEM:
                self.set_class(True, "system")
            
            if message.message_type == TUIMessageType.ERROR:
                self.set_class(True, "error")
            elif message.message_type == TUIMessageType.WARNING:
                self.set_class(True, "warning")
    
    def watch_is_selected(self, is_selected: bool) -> None:
        """React to selection changes."""
        self.set_class(is_selected, "selected")
    
    def on_mount(self) -> None:
        """Subscribe to click events when mounted."""
        if HAS_TEXTUAL:
            self.subscribe(Click, self._handle_click)
    
    def _handle_click(self, event: Click) -> None:
        """Handle click events to select the message."""
        if self.on_click:
            self.on_click(self)
        # Stop propagation to prevent other handlers
        event.stop()
    
    def render(self) -> str:
        """Render the chat message."""
        if not self.message:
            return ""
        
        m = self.message
        
        # Get type indicator
        type_indicator = self._get_type_indicator()
        
        # Get sender display
        sender = m.sender_display
        
        # Get timestamp
        timestamp = m.formatted_timestamp
        
        # Get content with formatting
        content = self._format_content(m.content, m.is_code, m.code_language)
        
        # Build the message line
        # Format: [type] sender: content (timestamp)
        parts = []
        
        if type_indicator:
            parts.append(f"[{m.type_color}]{type_indicator}[/{m.type_color}]")
        
        parts.append(f"[{m.sender_color}]{sender}[/{m.sender_color}]:")
        parts.append(content)
        parts.append(f"[dim]({timestamp})[/]")
        
        return " ".join(parts)
    
    def _get_type_indicator(self) -> str:
        """Get the type indicator character."""
        if not self.message:
            return ""
        
        indicators = {
            TUIMessageType.TEXT: "",
            TUIMessageType.COMMAND: "/",
            TUIMessageType.TASK: "✓",
            TUIMessageType.RESULT: "→",
            TUIMessageType.ERROR: "✗",
            TUIMessageType.WARNING: "⚠",
            TUIMessageType.INFO: "ℹ",
            TUIMessageType.DEBUG: "🐛",
        }
        return indicators.get(self.message.message_type, "")
    
    def _format_content(self, content: str, is_code: bool, language: str) -> str:
        """Format the content with syntax highlighting if code."""
        if is_code:
            # Simple code formatting
            if language == "python":
                return f"[dim green]{content}[/]"
            elif language == "bash" or language == "shell":
                return f"[dim yellow]{content}[/]"
            elif language == "json":
                return f"[dim blue]{content}[/]"
            else:
                return f"[dim]{content}[/]"
        else:
            return content
    
    def set_message(self, message: TUIMessage) -> None:
        """Set the message to display."""
        self.message = message
