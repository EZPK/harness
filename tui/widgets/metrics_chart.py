"""
Metrics Chart Widget for TUI.

Displays simple ASCII/Unicode charts for metrics visualization.
"""

from typing import List, Dict, Optional, Tuple

try:
    from textual.app import ComposeResult
    from textual.reactive import reactive
    from textual.widget import Widget
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


class MetricsChart(Widget):
    """
    Widget that displays metrics as simple charts.
    
    Supports bar charts, line charts, and progress bars.
    """
    
    DEFAULT_CSS = """
    MetricsChart {
        width: 100%;
        height: auto;
        background: #1e1e1e;
        padding: 1;
    }
    """
    
    # Chart type
    chart_type: str = reactive("bar")  # bar, line, progress
    
    # Data
    labels: List[str] = reactive([], init=False)
    values: List[float] = reactive([], init=False)
    colors: List[str] = reactive([], init=False)
    
    # Styling
    bar_char: str = "█"
    empty_char: str = "░"
    width: int = 40
    height: int = 5
    
    # Title
    title: str = ""
    
    def __init__(
        self,
        chart_type: str = "bar",
        title: str = "",
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ):
        super().__init__(name=name, id=id, classes=classes)
        self.chart_type = chart_type
        self.title = title
    
    def compose(self) -> ComposeResult:
        yield from super().compose()
    
    def render(self) -> str:
        """Render the chart."""
        if not self.labels or not self.values:
            return "[dim]No data[/]"
        
        if self.title:
            lines = [f"[bold white]{self.title}[/]"]
        else:
            lines = []
        
        if self.chart_type == "bar":
            lines.extend(self._render_bar_chart())
        elif self.chart_type == "line":
            lines.extend(self._render_line_chart())
        elif self.chart_type == "progress":
            lines.extend(self._render_progress_bars())
        
        return "\n".join(lines)
    
    def _render_bar_chart(self) -> List[str]:
        """Render a horizontal bar chart."""
        max_value = max(self.values) if self.values else 1
        lines = []
        
        for label, value, color in zip(self.labels, self.values, self.colors):
            bar_length = int((value / max_value) * self.width) if max_value > 0 else 0
            bar = self.bar_char * bar_length
            padding = self.empty_char * (self.width - bar_length)
            
            color_code = color if color else "white"
            lines.append(f"[{color_code}]{bar}[/{color_code}][dim]{padding}[/] {label}: {value:.1f}")
        
        return lines
    
    def _render_line_chart(self) -> List[str]:
        """Render a simple line chart (vertical)."""
        if not self.values:
            return []
        
        max_value = max(self.values)
        min_value = min(self.values)
        value_range = max_value - min_value
        
        lines = []
        for y in range(self.height, 0, -1):
            line_parts = []
            value_at_y = min_value + (value_range * (y - 1) / (self.height - 1)) if self.height > 1 else max_value
            
            for value in self.values:
                if value >= value_at_y:
                    line_parts.append(self.bar_char)
                else:
                    line_parts.append(self.empty_char)
            
            lines.append("".join(line_parts))
        
        # Add labels
        if self.labels:
            lines.append(" ".join(self.labels[:len(self.labels)]))
        
        return lines
    
    def _render_progress_bars(self) -> List[str]:
        """Render progress bars for each value."""
        lines = []
        
        for label, value, color in zip(self.labels, self.values, self.colors):
            # Value is 0-100 for progress
            if value > 1:
                value = value / 100  # Assume 0-100 scale
            
            bar_length = int(value * self.width)
            bar = self.bar_char * bar_length
            padding = self.empty_char * (self.width - bar_length)
            
            color_code = color if color else "green"
            percent = value * 100
            lines.append(f"[{color_code}]{bar}[/{color_code}][dim]{padding}[/] {label}: {percent:.0f}%")
        
        return lines
    
    def set_data(
        self,
        labels: List[str],
        values: List[float],
        colors: Optional[List[str]] = None,
    ) -> None:
        """Set the chart data."""
        self.labels = labels
        self.values = values
        self.colors = colors or ["white"] * len(labels)
    
    def set_bar_data(
        self,
        data: Dict[str, float],
        colors: Optional[Dict[str, str]] = None,
    ) -> None:
        """Set data from a dictionary."""
        labels = list(data.keys())
        values = list(data.values())
        color_list = [colors.get(k, "white") for k in labels] if colors else None
        self.set_data(labels, values, color_list)
    
    def set_progress_data(
        self,
        items: List[Tuple[str, float, str]],
    ) -> None:
        """Set progress data (name, value, color)."""
        labels, values, colors = zip(*items) if items else ([], [], [])
        self.set_data(list(labels), list(values), list(colors))
        self.chart_type = "progress"


# Helper class for simple ASCII charts without Textual
class SimpleMetricsChart:
    """
    Simple ASCII chart generator (no Textual dependency).
    
    Useful for displaying charts in non-TUI contexts.
    """
    
    BAR_CHAR = "█"
    EMPTY_CHAR = "░"
    
    @classmethod
    def bar_chart(
        cls,
        data: Dict[str, float],
        width: int = 40,
        colors: Optional[Dict[str, str]] = None,
    ) -> str:
        """Generate a simple bar chart."""
        if not data:
            return "No data"
        
        max_value = max(data.values())
        lines = []
        
        for label, value in data.items():
            bar_length = int((value / max_value) * width) if max_value > 0 else 0
            bar = cls.BAR_CHAR * bar_length
            padding = cls.EMPTY_CHAR * (width - bar_length)
            lines.append(f"{bar}{padding} {label}: {value:.1f}")
        
        return "\n".join(lines)
    
    @classmethod
    def progress_bars(
        cls,
        items: List[Tuple[str, float]],
        width: int = 40,
    ) -> str:
        """Generate progress bars."""
        lines = []
        
        for label, value in items:
            # Value is 0-100
            if value > 1:
                value = value / 100
            
            bar_length = int(value * width)
            bar = cls.BAR_CHAR * bar_length
            padding = cls.EMPTY_CHAR * (width - bar_length)
            percent = value * 100
            lines.append(f"{bar}{padding} {label}: {percent:.0f}%")
        
        return "\n".join(lines)
