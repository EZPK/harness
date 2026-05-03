"""
Theme for Harness TUI.

Custom color scheme and styling for the TUI.
"""

try:
    from textual.css.stylesheet import Stylesheet
    from textual.color import Color
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


# Custom color palette
COLORS = {
    "primary": "#1e88e5",
    "primary-dark": "#1565c0",
    "primary-light": "#7986cb",
    "accent": "#ffc107",
    "accent-dark": "#ff8f00",
    "accent-light": "#ffe082",
    "success": "#4caf50",
    "warning": "#ff9800",
    "error": "#f44336",
    "info": "#2196f3",
    "background": "#121212",
    "panel": "#1e1e1e",
    "surface": "#2d2d2d",
    "surface-hover": "#3d3d3d",
    "text": "#e0e0e0",
    "text-muted": "#9e9e9e",
    "text-disabled": "#757575",
    "border": "#424242",
    "border-light": "#616161",
}


# Custom CSS
CUSTOM_CSS = """
/* Base colors */

/* Screen styling */
Screen {
    background: #121212;
    color: #e0e0e0;
}

/* Containers */
Container {
    background: #1e1e1e;
    color: #e0e0e0;
}

/* Buttons */
Button {
    background: #1e88e5;
    color: white;
    text-style: bold;
}

Button:hover {
    background: #1e88e5-dark;
}

Button:pressed {
    background: #1e88e5-light;
}

/* Input */
Input {
    background: #2d2d2d;
    color: #e0e0e0;
    border: solid #424242;
}

Input:focus {
    border: solid #1e88e5;
}

/* Labels */
Label {
    color: #e0e0e0;
}

Label.dim {
    color: #9e9e9e;
}

/* Status colors */
.status-idle {
    color: #4caf50;
}

.status-busy {
    color: #ff9800;
}

.status-error {
    color: #f44336;
}

.status-paused {
    color: #ffc107;
}

.status-completed {
    color: #4caf50;
}

.status-failed {
    color: #f44336;
}

.status-running {
    color: #2196f3;
}

/* Priority colors */
.priority-critical {
    color: #f44336;
    text-style: bold;
}

.priority-high {
    color: #ff9800;
    text-style: bold;
}

.priority-medium {
    color: #e0e0e0;
}

.priority-low {
    color: #9e9e9e;
}

/* Scrollbar */
Scrollbar {
    background: #424242;
    background-hover: #424242-light;
    color: #1e88e5;
    color-hover: #1e88e5-light;
}

/* Tabbed content */
TabbedContent {
    background: #1e1e1e;
    color: #e0e0e0;
}

Tab {
    background: #1e1e1e;
    color: #9e9e9e;
    text-style: bold;
}

Tab:hover {
    color: #e0e0e0;
    background: #2d2d2d;
}

Tab.active {
    color: #1e88e5;
    background: #2d2d2d;
    border-bottom: solid #1e88e5;
}

/* Cards */
.card {
    border: round #424242;
    background: #2d2d2d;
    padding: 1;
}

.card:hover {
    background: #3d3d3d;
}

/* Badges */
.badge {
    background: #1e88e5;
    color: white;
    padding: 0 1;
    border-radius: 1;
    text-style: bold;
}

.badge-success {
    background: #4caf50;
}

.badge-warning {
    background: #ff9800;
}

.badge-error {
    background: #f44336;
}

.badge-info {
    background: #2196f3;
}
"""


if HAS_TEXTUAL:
    # Create a stylesheet with the custom CSS
    custom_stylesheet = Stylesheet()
    custom_stylesheet.add_source(CUSTOM_CSS)


# Helper functions for color access
def get_color(name: str) -> str:
    """Get a color by name."""
    return COLORS.get(name, "#ffffff")


def get_css() -> str:
    """Get the custom CSS."""
    return CUSTOM_CSS
