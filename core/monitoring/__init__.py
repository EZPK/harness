"""
Monitoring Module.

Provides observability for the harness: metrics, tracing, and alerts.
This is a critical component (Part of the 98.4% harness infrastructure).
"""

from .metrics import (
    MetricsCollector,
    Metric,
    MetricType,
    Counter,
    Gauge,
    Histogram,
    Summary,
    get_metrics_collector,
    increment_metric,
    record_metric,
    get_metrics,
)
from .tracing import (
    Tracer,
    Span,
    SpanContext,
    TraceStatus,
    get_tracer,
    start_span,
    trace_function,
    trace_method,
)
from .alerts import (
    AlertManager,
    Alert,
    AlertSeverity,
    AlertStatus,
    get_alert_manager,
    raise_alert,
    resolve_alert,
)

__all__ = [
    # Metrics
    "MetricsCollector",
    "Metric",
    "MetricType",
    "Counter",
    "Gauge",
    "Histogram",
    "Summary",
    "get_metrics_collector",
    "increment_metric",
    "record_metric",
    "get_metrics",
    # Tracing
    "Tracer",
    "Span",
    "SpanContext",
    "TraceStatus",
    "get_tracer",
    "start_span",
    "trace_function",
    "trace_method",
    # Alerts
    "AlertManager",
    "Alert",
    "AlertSeverity",
    "AlertStatus",
    "get_alert_manager",
    "raise_alert",
    "resolve_alert",
]
