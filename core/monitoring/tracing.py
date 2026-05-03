"""
Tracing Module.

Provides distributed tracing for the harness.
This is a critical observability component (Part of the 98.4% harness infrastructure).
"""

import asyncio
import threading
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TypeVar, Union

from configs.settings import get_config


# =============================================================================
# Type Definitions
# =============================================================================

T = TypeVar('T')

TraceID = str  # UUID string for trace
SpanID = str   # UUID string for span


class TraceStatus(str, Enum):
    """Status of a trace/span."""
    
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


# =============================================================================
# Span Context
# =============================================================================

@dataclass
class SpanContext:
    """
    Context for a span within a trace.
    
    Contains the identifiers and baggage that propagate through the trace.
    """
    
    trace_id: TraceID
    span_id: SpanID
    parent_span_id: Optional[SpanID] = None
    is_sampled: bool = True
    baggage: Dict[str, str] = field(default_factory=dict)
    
    def to_headers(self) -> Dict[str, str]:
        """Convert to HTTP headers for propagation."""
        headers = {
            "traceparent": f"00-{self.trace_id}-{self.span_id}-{int(self.is_sampled)}",
        }
        if self.parent_span_id:
            # Add parent span ID if available
            pass
        if self.baggage:
            baggage_items = ",".join(f"{k}={v}" for k, v in self.baggage.items())
            headers["tracestate"] = baggage_items
        return headers
    
    @classmethod
    def from_headers(cls, headers: Dict[str, str]) -> Optional['SpanContext']:
        """Create SpanContext from HTTP headers."""
        traceparent = headers.get('traceparent', '')
        
        if not traceparent:
            return None
        
        # Parse traceparent header: version-trace_id-parent_span_id-sampled
        parts = traceparent.split('-')
        if len(parts) < 4:
            return None
        
        version = parts[0]
        trace_id = parts[1]
        parent_span_id = parts[2]
        sampled = parts[3] == '1'
        
        return cls(
            trace_id=trace_id,
            span_id=parent_span_id,
            parent_span_id=None,  # Will be set when creating child spans
            is_sampled=sampled,
        )
    
    @classmethod
    def new_root(cls) -> 'SpanContext':
        """Create a new root span context."""
        return cls(
            trace_id=str(uuid.uuid4()),
            span_id=str(uuid.uuid4()),
            parent_span_id=None,
            is_sampled=True,
        )
    
    def new_child(self) -> 'SpanContext':
        """Create a new child span context."""
        return cls(
            trace_id=self.trace_id,
            span_id=str(uuid.uuid4()),
            parent_span_id=self.span_id,
            is_sampled=self.is_sampled,
            baggage=self.baggage.copy(),
        )


# =============================================================================
# Span
# =============================================================================

@dataclass
class Span:
    """
    A span represents a single operation within a trace.
    
    Spans can be nested to represent hierarchical operations.
    """
    
    name: str
    context: SpanContext
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    status: TraceStatus = TraceStatus.OK
    status_message: Optional[str] = None
    
    # Attributes (key-value pairs)
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    # Links to other spans (for relating spans across traces)
    links: List[Tuple[TraceID, SpanID]] = field(default_factory=list)
    
    # Events (log entries with timestamps)
    events: List[Tuple[datetime, str, Dict[str, Any]]] = field(default_factory=list)
    
    # Child spans
    children: List['Span'] = field(default_factory=list)
    
    @property
    def trace_id(self) -> TraceID:
        """Get the trace ID."""
        return self.context.trace_id
    
    @property
    def span_id(self) -> SpanID:
        """Get the span ID."""
        return self.context.span_id
    
    @property
    def duration_ms(self) -> float:
        """Get the duration in milliseconds."""
        if self.end_time is None:
            return (datetime.utcnow() - self.start_time).total_seconds() * 1000
        return (self.end_time - self.start_time).total_seconds() * 1000
    
    def set_attribute(self, key: str, value: Any) -> None:
        """Set an attribute on the span."""
        self.attributes[key] = value
    
    def set_status(self, status: TraceStatus, message: Optional[str] = None) -> None:
        """Set the status of the span."""
        self.status = status
        self.status_message = message
    
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        """Add an event to the span."""
        self.events.append((
            datetime.utcnow(),
            name,
            attributes or {},
        ))
    
    def add_link(self, trace_id: TraceID, span_id: SpanID) -> None:
        """Add a link to another span."""
        self.links.append((trace_id, span_id))
    
    def add_child(self, span: 'Span') -> None:
        """Add a child span."""
        self.children.append(span)
    
    def end(self, status: TraceStatus = TraceStatus.OK, message: Optional[str] = None) -> None:
        """End the span."""
        self.end_time = datetime.utcnow()
        self.status = status
        self.status_message = message
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert span to dictionary."""
        return {
            "name": self.name,
            "context": {
                "trace_id": self.context.trace_id,
                "span_id": self.context.span_id,
                "parent_span_id": self.context.parent_span_id,
                "is_sampled": self.context.is_sampled,
            },
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "status_message": self.status_message,
            "attributes": self.attributes,
            "links": [
                {"trace_id": tid, "span_id": sid} 
                for tid, sid in self.links
            ],
            "events": [
                {
                    "time": e[0].isoformat(),
                    "name": e[1],
                    "attributes": e[2],
                } 
                for e in self.events
            ],
            "children": [child.to_dict() for child in self.children],
        }


# =============================================================================
# Tracer
# =============================================================================

class Tracer:
    """
    Tracer for creating and managing spans.
    
    Provides:
    - Creation of root and child spans
    - Context propagation
    - Span recording and storage
    - Export to various formats
    """
    
    def __init__(self, name: str = "harness"):
        """
        Initialize the tracer.
        
        Args:
            name: Name of the tracer (used in span names)
        """
        self.name = name
        self._spans: Dict[TraceID, Span] = {}
        self._current_span: Optional[Span] = None
        self._lock = threading.Lock()
        self._enabled = True
    
    def enable(self) -> None:
        """Enable tracing."""
        self._enabled = True
    
    def disable(self) -> None:
        """Disable tracing."""
        self._enabled = False
    
    @property
    def is_enabled(self) -> bool:
        """Check if tracing is enabled."""
        return self._enabled
    
    def start_span(
        self,
        name: str,
        context: Optional[SpanContext] = None,
        **kwargs
    ) -> Span:
        """
        Start a new span.
        
        Args:
            name: Name of the span
            context: Span context (created if None)
            **kwargs: Additional attributes for the span
            
        Returns:
            The new span
        """
        if not self._enabled:
            # Return a no-op span
            return Span(
                name=name,
                context=SpanContext.new_root() if context is None else context,
                attributes=kwargs,
            )
        
        if context is None:
            # Check if there's a current span
            if self._current_span is not None:
                context = self._current_span.context.new_child()
            else:
                context = SpanContext.new_root()
        
        # Extract attributes from kwargs
        attributes = kwargs
        
        span = Span(name=name, context=context, attributes=attributes)
        
        # Store the span
        with self._lock:
            self._spans[context.trace_id] = span
        
        return span
    
    @contextmanager
    def span(
        self,
        name: str,
        context: Optional[SpanContext] = None,
    ) -> Span:
        """
        Context manager for creating a span.
        
        Args:
            name: Name of the span
            context: Span context (optional)
            
        Yields:
            The span
        """
        span = self.start_span(name, context)
        
        # Set as current span
        previous = self._current_span
        self._current_span = span
        
        try:
            yield span
        except Exception as e:
            span.set_status(TraceStatus.ERROR, str(e))
            span.add_event("exception", {"type": type(e).__name__, "message": str(e)})
            raise
        finally:
            span.end()
            self._current_span = previous
    
    @asynccontextmanager
    async def async_span(
        self,
        name: str,
        context: Optional[SpanContext] = None,
    ) -> Span:
        """
        Async context manager for creating a span.
        
        Args:
            name: Name of the span
            context: Span context (optional)
            
        Yields:
            The span
        """
        span = self.start_span(name, context)
        
        # Set as current span
        previous = self._current_span
        self._current_span = span
        
        try:
            yield span
        except Exception as e:
            span.set_status(TraceStatus.ERROR, str(e))
            span.add_event("exception", {"type": type(e).__name__, "message": str(e)})
            raise
        finally:
            span.end()
            self._current_span = previous
    
    def get_current_span(self) -> Optional[Span]:
        """Get the current span."""
        return self._current_span
    
    def get_span(self, trace_id: TraceID) -> Optional[Span]:
        """Get a span by trace ID."""
        with self._lock:
            return self._spans.get(trace_id)
    
    def get_all_spans(self) -> List[Span]:
        """Get all spans."""
        with self._lock:
            return list(self._spans.values())
    
    def export_json(self) -> List[Dict[str, Any]]:
        """Export all spans as JSON-serializable list."""
        return [span.to_dict() for span in self.get_all_spans()]
    
    def export_zipkin(self) -> List[Dict[str, Any]]:
        """Export spans in Zipkin v2 format."""
        spans = []
        
        for span in self.get_all_spans():
            zipkin_span = self._span_to_zipkin(span)
            spans.append(zipkin_span)
            
            # Add child spans
            for child in span.children:
                child_span = self._span_to_zipkin(child)
                child_span["parentId"] = zipkin_span["id"]
                spans.append(child_span)
        
        return spans
    
    def _span_to_zipkin(self, span: Span) -> Dict[str, Any]:
        """Convert a span to Zipkin v2 format."""
        return {
            "traceId": span.trace_id,
            "id": span.span_id,
            "name": span.name,
            "timestamp": int(span.start_time.timestamp() * 1000000),  # microseconds
            "duration": int(span.duration_ms * 1000),  # microseconds
            "kind": "SERVER",  # or CLIENT, PRODUCER, CONSUMER
            "localEndpoint": {"serviceName": self.name},
            "tags": {
                **span.attributes,
                "status": span.status.value,
            },
            "debug": False,
            "shared": False,
        }
    
    def clear(self) -> None:
        """Clear all spans."""
        with self._lock:
            self._spans.clear()
        self._current_span = None


# =============================================================================
# Decorators
# =============================================================================

def trace_function(name: Optional[str] = None):
    """
    Decorator to trace a synchronous function.
    
    Args:
        name: Name for the span (defaults to function name)
        
    Example:
        @trace_function()
        def my_function():
            pass
        
        @trace_function("custom_name")
        def my_function():
            pass
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        span_name = name or f"{func.__module__}.{func.__qualname__}"
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            
            with tracer.span(span_name) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_status(TraceStatus.OK)
                    return result
                except Exception as e:
                    span.set_status(TraceStatus.ERROR, str(e))
                    raise
        
        return wrapper
    
    return decorator


def trace_method(name: Optional[str] = None):
    """
    Decorator to trace a class method.
    
    Args:
        name: Name for the span (defaults to method name)
        
    Example:
        class MyClass:
            @trace_method()
            def my_method(self):
                pass
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        span_name = name or f"{func.__module__}.{func.__qualname__}"
        
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            tracer = get_tracer()
            
            with tracer.span(span_name) as span:
                try:
                    result = func(self, *args, **kwargs)
                    span.set_status(TraceStatus.OK)
                    return result
                except Exception as e:
                    span.set_status(TraceStatus.ERROR, str(e))
                    raise
        
        return wrapper
    
    return decorator


def trace_async_function(name: Optional[str] = None):
    """
    Decorator to trace an async function.
    
    Args:
        name: Name for the span (defaults to function name)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        span_name = name or f"{func.__module__}.{func.__qualname__}"
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()
            
            async with tracer.async_span(span_name) as span:
                try:
                    result = await func(*args, **kwargs)
                    span.set_status(TraceStatus.OK)
                    return result
                except Exception as e:
                    span.set_status(TraceStatus.ERROR, str(e))
                    raise
        
        return wrapper
    
    return decorator


# =============================================================================
# Global Tracer Instance
# =============================================================================

_tracer: Optional[Tracer] = None

def get_tracer() -> Tracer:
    """Get the global tracer instance."""
    global _tracer
    if _tracer is None:
        _tracer = Tracer()
    return _tracer


def start_span(name: str, context: Optional[SpanContext] = None, **kwargs) -> Span:
    """
    Start a new span (convenience function).
    
    Args:
        name: Name of the span
        context: Optional SpanContext (deprecated: dict is treated as attributes)
        **kwargs: Additional attributes for the span
    
    Note: If context is a dict, it's treated as attributes for backward compatibility.
    """
    # Handle backward compatibility: if context is a dict, treat it as attributes
    if context is not None and isinstance(context, dict) and not isinstance(context, SpanContext):
        # context was passed as a dict of attributes (old style)
        # Convert to proper call with context=None and attributes in kwargs
        kwargs.update(context)
        context = None
    
    return get_tracer().start_span(name, context, **kwargs)

# Async context manager version
from contextlib import asynccontextmanager

@asynccontextmanager
async def async_span(name: str, context: Optional[SpanContext] = None, **kwargs) -> Span:
    """
    Async context manager for creating a span.
    
    Args:
        name: Name of the span
        context: Optional SpanContext or dict of attributes
        **kwargs: Additional attributes for the span
    
    Yields:
        The span
    """
    # Handle backward compatibility: if context is a dict, treat it as attributes
    if context is not None and isinstance(context, dict) and not isinstance(context, SpanContext):
        kwargs.update(context)
        context = None
    
    span = get_tracer().start_span(name, context, **kwargs)
    
    # Set as current span
    tracer = get_tracer()
    previous = tracer._current_span
    tracer._current_span = span
    
    try:
        yield span
    except Exception as e:
        span.set_status(TraceStatus.ERROR, str(e))
        span.add_event("exception", {"type": type(e).__name__, "message": str(e)})
        raise
    finally:
        span.end()
        tracer._current_span = previous


# =============================================================================
# Context Propagation
# =============================================================================

class ContextPropagation:
    """Utilities for propagating trace context."""
    
    @staticmethod
    def extract(context: Optional[SpanContext] = None) -> SpanContext:
        """
        Extract trace context from the current execution context.
        
        Checks:
        1. Thread-local current span
        2. Provided context
        3. Creates new root context
        """
        tracer = get_tracer()
        current = tracer.get_current_span()
        
        if current is not None:
            return current.context.new_child()
        elif context is not None:
            return context.new_child()
        else:
            return SpanContext.new_root()
    
    @staticmethod
    def inject(context: SpanContext) -> None:
        """Inject trace context into the current execution context."""
        tracer = get_tracer()
        # This would typically set thread-local or async-local storage
        # For simplicity, we just rely on the tracer's current_span mechanism
        pass


# Convenience alias
propagate = ContextPropagation()
