"""
Metrics Module.

Provides metrics collection and reporting for the harness.
This is a critical observability component (Part of the 98.4% harness infrastructure).
"""

import asyncio
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, TypeVar, Union

from configs.settings import get_config


# =============================================================================
# Metric Types
# =============================================================================

class MetricType(str, Enum):
    """Types of metrics."""
    
    COUNTER = "counter"      # Increasing counter (tasks completed, errors, etc.)
    GAUGE = "gauge"          # Current value (active tasks, memory usage, etc.)
    HISTOGRAM = "histogram"  # Distribution of values (execution times, etc.)
    SUMMARY = "summary"      # Like histogram but with calculated quantiles


# =============================================================================
# Metric Definitions
# =============================================================================

@dataclass
class Metric:
    """Definition of a metric."""
    
    name: str
    metric_type: MetricType
    description: str
    labels: List[str] = field(default_factory=list)
    unit: str = ""
    
    def __hash__(self):
        return hash((self.name, self.metric_type, tuple(self.labels)))


@dataclass
class Counter:
    """A counter metric (monotonically increasing)."""
    
    name: str
    description: str
    labels: List[str] = field(default_factory=list)
    unit: str = ""
    value: float = 0.0
    
    def increment(self, amount: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment the counter."""
        self.value += amount
    
    def reset(self) -> None:
        """Reset the counter to zero."""
        self.value = 0.0


@dataclass
class Gauge:
    """A gauge metric (can go up and down)."""
    
    name: str
    description: str
    labels: List[str] = field(default_factory=list)
    unit: str = ""
    value: float = 0.0
    
    def set(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set the gauge to a specific value."""
        self.value = value
    
    def increment(self, amount: float = 1.0) -> None:
        """Increment the gauge."""
        self.value += amount
    
    def decrement(self, amount: float = 1.0) -> None:
        """Decrement the gauge."""
        self.value -= amount


@dataclass
class Histogram:
    """A histogram metric for tracking distributions."""
    
    name: str
    description: str
    labels: List[str] = field(default_factory=list)
    unit: str = ""
    buckets: List[float] = field(default_factory=lambda: [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, float('inf')])
    values: List[float] = field(default_factory=list)
    counts: List[int] = field(default_factory=list)
    
    def __post_init__(self):
        # Initialize counts for each bucket
        if not self.counts:
            self.counts = [0] * len(self.buckets)
    
    def record(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a value in the histogram."""
        self.values.append(value)
        
        # Find the appropriate bucket
        for i, bucket in enumerate(self.buckets):
            if value <= bucket:
                self.counts[i] += 1
                break
    
    def get_bucket_counts(self) -> Dict[str, int]:
        """Get counts for each bucket."""
        return {
            f"{self.buckets[i]}": count 
            for i, count in enumerate(self.counts)
        }
    
    def get_sum(self) -> float:
        """Get the sum of all recorded values."""
        return sum(self.values)
    
    def get_count(self) -> int:
        """Get the total count of recorded values."""
        return len(self.values)
    
    def get_average(self) -> float:
        """Get the average of recorded values."""
        if not self.values:
            return 0.0
        return self.get_sum() / self.get_count()


@dataclass
class Summary:
    """A summary metric with quantiles."""
    
    name: str
    description: str
    labels: List[str] = field(default_factory=list)
    unit: str = ""
    values: List[float] = field(default_factory=list)
    quantiles: List[float] = field(default_factory=lambda: [0.5, 0.9, 0.95, 0.99])
    
    def record(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a value in the summary."""
        self.values.append(value)
    
    def get_quantiles(self) -> Dict[str, float]:
        """Calculate and return quantile values."""
        if not self.values:
            return {f"{q}": 0.0 for q in self.quantiles}
        
        sorted_values = sorted(self.values)
        n = len(sorted_values)
        
        result = {}
        for q in self.quantiles:
            if q <= 0:
                result[f"{q}"] = sorted_values[0]
            elif q >= 1:
                result[f"{q}"] = sorted_values[-1]
            else:
                index = q * (n - 1)
                lower = int(index)
                upper = lower + 1
                if upper >= n:
                    result[f"{q}"] = sorted_values[lower]
                else:
                    weight = index - lower
                    result[f"{q}"] = sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
        
        return result
    
    def get_sum(self) -> float:
        """Get the sum of all recorded values."""
        return sum(self.values)
    
    def get_count(self) -> int:
        """Get the total count of recorded values."""
        return len(self.values)
    
    def get_average(self) -> float:
        """Get the average of recorded values."""
        if not self.values:
            return 0.0
        return self.get_sum() / self.get_count()


# =============================================================================
# Metrics Collector
# =============================================================================

T = TypeVar('T')


@dataclass
class MetricData:
    """Data for a single metric instance (with labels)."""
    
    metric: Metric
    labels: Dict[str, str]
    counter: Optional[Counter] = None
    gauge: Optional[Gauge] = None
    histogram: Optional[Histogram] = None
    summary: Optional[Summary] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class MetricsCollector:
    """
    Collects and manages metrics for the harness.
    
    Provides:
    - Registration of metrics
    - Recording of metric values
    - Querying of metric data
    - Export to various formats (Prometheus, JSON, etc.)
    """
    
    def __init__(self):
        """Initialize the metrics collector."""
        self._metrics: Dict[str, Metric] = {}
        self._metric_data: Dict[Tuple[str, str], MetricData] = {}
        self._lock = threading.Lock()
        self._enabled = True
    
    def enable(self) -> None:
        """Enable metrics collection."""
        self._enabled = True
    
    def disable(self) -> None:
        """Disable metrics collection."""
        self._enabled = False
    
    @property
    def is_enabled(self) -> bool:
        """Check if metrics collection is enabled."""
        return self._enabled
    
    def register_metric(self, metric: Metric) -> None:
        """Register a new metric."""
        with self._lock:
            self._metrics[metric.name] = metric
    
    def register_counter(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
        unit: str = "",
    ) -> Counter:
        """Register a counter metric and return it."""
        metric = Metric(
            name=name,
            metric_type=MetricType.COUNTER,
            description=description,
            labels=labels or [],
            unit=unit,
        )
        self.register_metric(metric)
        
        counter = Counter(
            name=name,
            description=description,
            labels=labels or [],
            unit=unit,
        )
        return counter
    
    def register_gauge(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
        unit: str = "",
    ) -> Gauge:
        """Register a gauge metric and return it."""
        metric = Metric(
            name=name,
            metric_type=MetricType.GAUGE,
            description=description,
            labels=labels or [],
            unit=unit,
        )
        self.register_metric(metric)
        
        gauge = Gauge(
            name=name,
            description=description,
            labels=labels or [],
            unit=unit,
        )
        return gauge
    
    def register_histogram(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
        unit: str = "",
        buckets: Optional[List[float]] = None,
    ) -> Histogram:
        """Register a histogram metric and return it."""
        metric = Metric(
            name=name,
            metric_type=MetricType.HISTOGRAM,
            description=description,
            labels=labels or [],
            unit=unit,
        )
        self.register_metric(metric)
        
        histogram = Histogram(
            name=name,
            description=description,
            labels=labels or [],
            unit=unit,
            buckets=buckets or [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, float('inf')],
        )
        return histogram
    
    def register_summary(
        self,
        name: str,
        description: str,
        labels: Optional[List[str]] = None,
        unit: str = "",
        quantiles: Optional[List[float]] = None,
    ) -> Summary:
        """Register a summary metric and return it."""
        metric = Metric(
            name=name,
            metric_type=MetricType.SUMMARY,
            description=description,
            labels=labels or [],
            unit=unit,
        )
        self.register_metric(metric)
        
        summary = Summary(
            name=name,
            description=description,
            labels=labels or [],
            unit=unit,
            quantiles=quantiles or [0.5, 0.9, 0.95, 0.99],
        )
        return summary
    
    def increment(
        self,
        name: str,
        amount: float = 1.0,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Increment a counter metric."""
        if not self._enabled:
            return
        
        labels = labels or {}
        key = (name, self._serialize_labels(labels))
        
        with self._lock:
            if key not in self._metric_data:
                metric = self._metrics.get(name)
                if metric and metric.metric_type != MetricType.COUNTER:
                    raise ValueError(f"Metric '{name}' is not a counter")
                
                counter = Counter(
                    name=name,
                    description=metric.description if metric else "",
                    labels=metric.labels if metric else [],
                )
                self._metric_data[key] = MetricData(
                    metric=metric,
                    labels=labels,
                    counter=counter,
                )
            
            self._metric_data[key].counter.increment(amount)
            self._metric_data[key].updated_at = datetime.utcnow()
    
    def record(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a value for a metric (gauge, histogram, or summary)."""
        if not self._enabled:
            return
        
        labels = labels or {}
        key = (name, self._serialize_labels(labels))
        
        with self._lock:
            if key not in self._metric_data:
                metric = self._metrics.get(name)
                if not metric:
                    raise ValueError(f"Metric '{name}' not registered")
                
                if metric.metric_type == MetricType.GAUGE:
                    gauge = Gauge(
                        name=name,
                        description=metric.description,
                        labels=metric.labels,
                    )
                    gauge.set(value)
                    self._metric_data[key] = MetricData(
                        metric=metric,
                        labels=labels,
                        gauge=gauge,
                    )
                elif metric.metric_type == MetricType.HISTOGRAM:
                    histogram = Histogram(
                        name=name,
                        description=metric.description,
                        labels=metric.labels,
                        buckets=metric.buckets if hasattr(metric, 'buckets') else None,
                    )
                    histogram.record(value)
                    self._metric_data[key] = MetricData(
                        metric=metric,
                        labels=labels,
                        histogram=histogram,
                    )
                elif metric.metric_type == MetricType.SUMMARY:
                    summary = Summary(
                        name=name,
                        description=metric.description,
                        labels=metric.labels,
                        quantiles=metric.quantiles if hasattr(metric, 'quantiles') else None,
                    )
                    summary.record(value)
                    self._metric_data[key] = MetricData(
                        metric=metric,
                        labels=labels,
                        summary=summary,
                    )
                else:
                    raise ValueError(f"Cannot record value for metric type: {metric.metric_type}")
            else:
                data = self._metric_data[key]
                if data.counter:
                    data.counter.increment(value)
                elif data.gauge:
                    data.gauge.set(value)
                elif data.histogram:
                    data.histogram.record(value)
                elif data.summary:
                    data.summary.record(value)
            
            self._metric_data[key].updated_at = datetime.utcnow()
    
    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Set a gauge metric to a specific value."""
        self.record(name, value, labels)
    
    def get_metric(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[MetricData]:
        """Get metric data for a specific metric and labels."""
        labels = labels or {}
        key = (name, self._serialize_labels(labels))
        return self._metric_data.get(key)
    
    def get_all_metrics(self) -> List[MetricData]:
        """Get all collected metric data."""
        with self._lock:
            return list(self._metric_data.values())
    
    def reset_metric(self, name: str, labels: Optional[Dict[str, str]] = None) -> None:
        """Reset a metric (counter, histogram, or summary)."""
        labels = labels or {}
        key = (name, self._serialize_labels(labels))
        
        with self._lock:
            if key in self._metric_data:
                data = self._metric_data[key]
                if data.counter:
                    data.counter.reset()
                elif data.histogram:
                    data.histogram.values.clear()
                    data.histogram.counts = [0] * len(data.histogram.buckets)
                elif data.summary:
                    data.summary.values.clear()
    
    def reset_all(self) -> None:
        """Reset all metrics."""
        with self._lock:
            for data in self._metric_data.values():
                if data.counter:
                    data.counter.reset()
                elif data.histogram:
                    data.histogram.values.clear()
                    data.histogram.counts = [0] * len(data.histogram.buckets)
                elif data.summary:
                    data.summary.values.clear()
                elif data.gauge:
                    data.gauge.value = 0.0
    
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = []
        
        with self._lock:
            for data in self._metric_data.values():
                if data.counter:
                    labels_str = self._format_labels(data.labels)
                    lines.append(f"# HELP {data.counter.name} {data.counter.description}")
                    lines.append(f"# TYPE {data.counter.name} counter")
                    lines.append(f"{data.counter.name}{labels_str} {data.counter.value}")
                
                elif data.gauge:
                    labels_str = self._format_labels(data.labels)
                    lines.append(f"# HELP {data.gauge.name} {data.gauge.description}")
                    lines.append(f"# TYPE {data.gauge.name} gauge")
                    lines.append(f"{data.gauge.name}{labels_str} {data.gauge.value}")
                
                elif data.histogram:
                    labels_str = self._format_labels(data.labels)
                    lines.append(f"# HELP {data.histogram.name} {data.histogram.description}")
                    lines.append(f"# TYPE {data.histogram.name} histogram")
                    
                    bucket_counts = data.histogram.get_bucket_counts()
                    for bucket, count in bucket_counts.items():
                        if bucket == 'inf':
                            lines.append(f"{data.histogram.name}_bucket{labels_str} +Inf {count}")
                        else:
                            lines.append(f"{data.histogram.name}_bucket{labels_str} {bucket} {count}")
                    
                    lines.append(f"{data.histogram.name}_sum{labels_str} {data.histogram.get_sum()}")
                    lines.append(f"{data.histogram.name}_count{labels_str} {data.histogram.get_count()}")
                
                elif data.summary:
                    labels_str = self._format_labels(data.labels)
                    lines.append(f"# HELP {data.summary.name} {data.summary.description}")
                    lines.append(f"# TYPE {data.summary.name} summary")
                    
                    quantiles = data.summary.get_quantiles()
                    for q, value in quantiles.items():
                        lines.append(f"{data.summary.name}_quantile{labels_str} {q} {value}")
                    
                    lines.append(f"{data.summary.name}_sum{labels_str} {data.summary.get_sum()}")
                    lines.append(f"{data.summary.name}_count{labels_str} {data.summary.get_count()}")
        
        return '\n'.join(lines)
    
    def export_json(self) -> Dict[str, Any]:
        """Export metrics as a JSON-serializable dictionary."""
        result = {}
        
        with self._lock:
            for data in self._metric_data.values():
                metric_key = data.metric.name
                if metric_key not in result:
                    result[metric_key] = {}
                
                if data.labels:
                    labels_key = self._serialize_labels(data.labels)
                    result[metric_key][labels_key] = self._serialize_metric_data(data)
                else:
                    result[metric_key]["_no_labels"] = self._serialize_metric_data(data)
        
        return result
    
    def _serialize_labels(self, labels: Dict[str, str]) -> str:
        """Serialize labels to a string key."""
        if not labels:
            return ""
        return ":".join(f"{k}={v}" for k, v in sorted(labels.items()))
    
    def _format_labels(self, labels: Dict[str, str]) -> str:
        """Format labels for Prometheus output."""
        if not labels:
            return ""
        return "{" + ",".join(f'{k}="{v}"' for k, v in labels.items()) + "}"
    
    def _serialize_metric_data(self, data: MetricData) -> Dict[str, Any]:
        """Serialize metric data to a dictionary."""
        result = {
            "type": data.metric.metric_type.value,
            "description": data.metric.description,
            "unit": data.metric.unit,
            "labels": data.labels,
        }
        
        if data.counter:
            result["value"] = data.counter.value
        elif data.gauge:
            result["value"] = data.gauge.value
        elif data.histogram:
            result["count"] = data.histogram.get_count()
            result["sum"] = data.histogram.get_sum()
            result["average"] = data.histogram.get_average()
            result["buckets"] = data.histogram.get_bucket_counts()
        elif data.summary:
            result["count"] = data.summary.get_count()
            result["sum"] = data.summary.get_sum()
            result["average"] = data.summary.get_average()
            result["quantiles"] = data.summary.get_quantiles()
        
        return result


# =============================================================================
# Predefined Metrics for Harness
# =============================================================================

class HarnessMetrics:
    """Predefined metrics for the harness."""
    
    # Agent metrics
    AGENT_TASKS_ASSIGNED = Metric(
        name="harness_agent_tasks_assigned_total",
        metric_type=MetricType.COUNTER,
        description="Total number of tasks assigned to agents",
        labels=["agent_type"],
    )
    
    AGENT_TASKS_COMPLETED = Metric(
        name="harness_agent_tasks_completed_total",
        metric_type=MetricType.COUNTER,
        description="Total number of tasks completed by agents",
        labels=["agent_type", "status"],
    )
    
    AGENT_TASKS_FAILED = Metric(
        name="harness_agent_tasks_failed_total",
        metric_type=MetricType.COUNTER,
        description="Total number of tasks failed by agents",
        labels=["agent_type", "error_type"],
    )
    
    AGENT_ACTIVE_TASKS = Metric(
        name="harness_agent_active_tasks",
        metric_type=MetricType.GAUGE,
        description="Current number of active tasks per agent",
        labels=["agent_type"],
    )
    
    AGENT_EXECUTION_TIME = Metric(
        name="harness_agent_execution_time_seconds",
        metric_type=MetricType.HISTOGRAM,
        description="Time taken to execute tasks",
        labels=["agent_type", "task_type"],
        buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0],
    )
    
    # Tool metrics
    TOOL_EXECUTIONS = Metric(
        name="harness_tool_executions_total",
        metric_type=MetricType.COUNTER,
        description="Total number of tool executions",
        labels=["tool_name", "status"],
    )
    
    TOOL_EXECUTION_TIME = Metric(
        name="harness_tool_execution_time_seconds",
        metric_type=MetricType.HISTOGRAM,
        description="Time taken to execute tools",
        labels=["tool_name"],
        buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
    )
    
    # Sandbox metrics
    SANDBOX_EXECUTIONS = Metric(
        name="harness_sandbox_executions_total",
        metric_type=MetricType.COUNTER,
        description="Total number of sandbox executions",
        labels=["mode", "status"],
    )
    
    SANDBOX_VIOLATIONS = Metric(
        name="harness_sandbox_violations_total",
        metric_type=MetricType.COUNTER,
        description="Total number of sandbox security violations",
        labels=["violation_type"],
    )
    
    # ACI metrics
    ACI_MESSAGES_SENT = Metric(
        name="harness_aci_messages_sent_total",
        metric_type=MetricType.COUNTER,
        description="Total number of ACI messages sent",
        labels=["message_type"],
    )
    
    ACI_MESSAGES_RECEIVED = Metric(
        name="harness_aci_messages_received_total",
        metric_type=MetricType.COUNTER,
        description="Total number of ACI messages received",
        labels=["message_type"],
    )
    
    ACI_VALIDATION_ERRORS = Metric(
        name="harness_aci_validation_errors_total",
        metric_type=MetricType.COUNTER,
        description="Total number of ACI validation errors",
        labels=["error_type"],
    )
    
    # System metrics
    SYSTEM_UPTIME = Metric(
        name="harness_system_uptime_seconds",
        metric_type=MetricType.GAUGE,
        description="Time since the harness started",
    )
    
    SYSTEM_MEMORY_USAGE = Metric(
        name="harness_system_memory_usage_bytes",
        metric_type=MetricType.GAUGE,
        description="Current memory usage",
    )
    
    SYSTEM_CPU_USAGE = Metric(
        name="harness_system_cpu_usage",
        metric_type=MetricType.GAUGE,
        description="Current CPU usage",
    )


# =============================================================================
# Global Metrics Collector Instance
# =============================================================================

_metrics_collector: Optional[MetricsCollector] = None

def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
        # Register harness metrics
        _register_harness_metrics(_metrics_collector)
    return _metrics_collector


def _register_harness_metrics(collector: MetricsCollector) -> None:
    """Register all harness metrics with the collector."""
    metrics = HarnessMetrics()
    
    for attr_name in dir(metrics):
        attr = getattr(metrics, attr_name)
        if isinstance(attr, Metric):
            collector.register_metric(attr)


# Convenience functions
def increment_metric(name: str, amount: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
    """Increment a counter metric (convenience function)."""
    get_metrics_collector().increment(name, amount, labels)


def record_metric(name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
    """Record a value for a metric (convenience function)."""
    get_metrics_collector().record(name, value, labels)


def get_metrics() -> List[MetricData]:
    """Get all collected metrics (convenience function)."""
    return get_metrics_collector().get_all_metrics()
