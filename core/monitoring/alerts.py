"""
Alerts Module.

Provides alert management for the harness.
This is a critical observability component (Part of the 98.4% harness infrastructure).
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union

from configs.settings import get_config


# =============================================================================
# Alert Types
# =============================================================================

class AlertSeverity(str, Enum):
    """Severity levels for alerts."""
    
    CRITICAL = "critical"    # System is down or severely degraded
    HIGH = "high"            # Major functionality is impaired
    MEDIUM = "medium"        # Partial degradation or potential issues
    LOW = "low"              # Minor issues or informational
    INFO = "info"            # Informational alerts


class AlertStatus(str, Enum):
    """Status of an alert."""
    
    FIRING = "firing"        # Alert is currently active
    RESOLVED = "resolved"    # Alert has been resolved
    SHELVED = "shelved"      # Alert is temporarily suppressed
    ACKNOWLEDGED = "acknowledged"  # Alert has been acknowledged


# =============================================================================
# Alert Definition
# =============================================================================

@dataclass
class Alert:
    """Represents an alert in the system."""
    
    alert_id: str
    name: str
    severity: AlertSeverity
    message: str
    status: AlertStatus = AlertStatus.FIRING
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    description: str = ""
    
    # Context
    source: str = "harness"
    component: str = ""
    tags: List[str] = field(default_factory=list)
    
    # Related data
    metric_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    
    # Additional data
    data: Dict[str, Any] = field(default_factory=dict)
    
    # Tracking
    occurrences: int = 1
    last_occurrence: datetime = field(default_factory=datetime.utcnow)
    
    # Resolution
    resolution: Optional[str] = None
    resolved_by: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "name": self.name,
            "severity": self.severity.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "message": self.message,
            "description": self.description,
            "source": self.source,
            "component": self.component,
            "tags": self.tags,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "data": self.data,
            "occurrences": self.occurrences,
            "last_occurrence": self.last_occurrence.isoformat(),
            "resolution": self.resolution,
            "resolved_by": self.resolved_by,
        }
    
    def is_active(self) -> bool:
        """Check if the alert is currently active (firing)."""
        return self.status == AlertStatus.FIRING
    
    def is_resolved(self) -> bool:
        """Check if the alert is resolved."""
        return self.status == AlertStatus.RESOLVED
    
    def is_shelved(self) -> bool:
        """Check if the alert is shelved."""
        return self.status == AlertStatus.SHELVED


# =============================================================================
# Alert Rule
# =============================================================================

@dataclass
class AlertRule:
    """Definition of an alert rule."""
    
    name: str
    description: str = ""
    
    # Condition
    condition: str = ""  # Expression to evaluate (e.g., "metric > threshold")
    metric_name: str = ""
    threshold: float = 0.0
    
    # Severity
    severity: AlertSeverity = AlertSeverity.MEDIUM
    
    # Duration
    for_duration: Optional[int] = None  # Alert only after N seconds
    
    # Cooldown
    cooldown_seconds: int = 300  # Don't re-alert for N seconds after resolution
    
    # Tags
    tags: List[str] = field(default_factory=list)
    
    # Message templates
    message_template: str = "Alert: {{name}}"
    description_template: str = ""
    
    # Enabled
    enabled: bool = True
    
    def evaluate(self, metric_value: float) -> bool:
        """Evaluate if the alert should fire based on metric value."""
        if not self.enabled:
            return False
        
        # Simple threshold evaluation
        if self.condition == ">":
            return metric_value > self.threshold
        elif self.condition == "<":
            return metric_value < self.threshold
        elif self.condition == ">=":
            return metric_value >= self.threshold
        elif self.condition == "<=":
            return metric_value <= self.threshold
        elif self.condition == "==":
            return metric_value == self.threshold
        elif self.condition == "!=":
            return metric_value != self.threshold
        
        return False


# =============================================================================
# Alert Manager
# =============================================================================

class AlertManager:
    """
    Manages alerts for the harness.
    
    Provides:
    - Alert creation and management
    - Alert rule evaluation
    - Alert notifications
    - Alert lifecycle management
    """
    
    def __init__(self):
        """Initialize the alert manager."""
        self._alerts: Dict[str, Alert] = {}
        self._rules: Dict[str, AlertRule] = {}
        self._handlers: List[Callable[[Alert], None]] = []
        self._lock = threading.Lock()
        self._enabled = True
        self._cooldowns: Dict[str, datetime] = {}  # alert_id -> cooldown end time
    
    def enable(self) -> None:
        """Enable alert management."""
        self._enabled = True
    
    def disable(self) -> None:
        """Disable alert management."""
        self._enabled = False
    
    @property
    def is_enabled(self) -> bool:
        """Check if alert management is enabled."""
        return self._enabled
    
    # Alert management
    def create_alert(
        self,
        name: str,
        message: str,
        severity: AlertSeverity = AlertSeverity.MEDIUM,
        description: str = "",
        source: str = "harness",
        component: str = "",
        tags: Optional[List[str]] = None,
        metric_name: Optional[str] = None,
        metric_value: Optional[float] = None,
        threshold: Optional[float] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Alert:
        """
        Create a new alert.
        
        Args:
            name: Alert name
            message: Alert message
            severity: Alert severity
            description: Detailed description
            source: Source of the alert
            component: Component that generated the alert
            tags: Tags for categorization
            metric_name: Related metric name
            metric_value: Current metric value
            threshold: Threshold that was crossed
            data: Additional data
            
        Returns:
            The created alert
        """
        import uuid
        
        alert_id = str(uuid.uuid4())
        now = datetime.utcnow()
        
        # Check cooldown
        if alert_id in self._cooldowns:
            if now < self._cooldowns[alert_id]:
                # Still in cooldown, don't create new alert
                return None
            else:
                # Cooldown expired, remove it
                del self._cooldowns[alert_id]
        
        alert = Alert(
            alert_id=alert_id,
            name=name,
            message=message,
            severity=severity,
            description=description,
            source=source,
            component=component,
            tags=tags or [],
            metric_name=metric_name,
            metric_value=metric_value,
            threshold=threshold,
            data=data or {},
        )
        
        with self._lock:
            self._alerts[alert_id] = alert
        
        # Notify handlers
        self._notify_handlers(alert)
        
        return alert
    
    def raise_alert(self, alert: Alert) -> None:
        """Raise an existing alert (update and notify)."""
        with self._lock:
            alert.status = AlertStatus.FIRING
            alert.updated_at = datetime.utcnow()
            alert.occurrences += 1
            alert.last_occurrence = datetime.utcnow()
            
            if alert.alert_id in self._alerts:
                # Update existing alert
                existing = self._alerts[alert.alert_id]
                existing.status = alert.status
                existing.updated_at = alert.updated_at
                existing.occurrences = alert.occurrences
                existing.last_occurrence = alert.last_occurrence
                existing.message = alert.message
                existing.data.update(alert.data)
            else:
                # Add new alert
                self._alerts[alert.alert_id] = alert
        
        # Notify handlers
        self._notify_handlers(alert)
    
    def resolve_alert(
        self,
        alert_id: str,
        resolution: Optional[str] = None,
        resolved_by: Optional[str] = None,
    ) -> Optional[Alert]:
        """
        Resolve an alert.
        
        Args:
            alert_id: ID of the alert to resolve
            resolution: Resolution message
            resolved_by: Who resolved the alert
            
        Returns:
            The resolved alert, or None if not found
        """
        with self._lock:
            alert = self._alerts.get(alert_id)
            if alert is None:
                return None
            
            alert.status = AlertStatus.RESOLVED
            alert.updated_at = datetime.utcnow()
            alert.resolved_at = datetime.utcnow()
            alert.resolution = resolution
            alert.resolved_by = resolved_by
            
            # Set cooldown
            rule = self._get_rule_for_alert(alert)
            if rule:
                self._cooldowns[alert_id] = datetime.utcnow() + timedelta(
                    seconds=rule.cooldown_seconds
                )
        
        # Notify handlers
        self._notify_handlers(alert)
        
        return alert
    
    def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: Optional[str] = None,
    ) -> Optional[Alert]:
        """
        Acknowledge an alert.
        
        Args:
            alert_id: ID of the alert to acknowledge
            acknowledged_by: Who acknowledged the alert
            
        Returns:
            The acknowledged alert, or None if not found
        """
        with self._lock:
            alert = self._alerts.get(alert_id)
            if alert is None:
                return None
            
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.updated_at = datetime.utcnow()
            alert.acknowledged_at = datetime.utcnow()
        
        return alert
    
    def shelf_alert(
        self,
        alert_id: str,
        shelved_by: Optional[str] = None,
    ) -> Optional[Alert]:
        """
        Shelf (suppress) an alert.
        
        Args:
            alert_id: ID of the alert to shelf
            shelved_by: Who shelved the alert
            
        Returns:
            The shelved alert, or None if not found
        """
        with self._lock:
            alert = self._alerts.get(alert_id)
            if alert is None:
                return None
            
            alert.status = AlertStatus.SHELVED
            alert.updated_at = datetime.utcnow()
        
        return alert
    
    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get an alert by ID."""
        with self._lock:
            return self._alerts.get(alert_id)
    
    def get_all_alerts(self) -> List[Alert]:
        """Get all alerts."""
        with self._lock:
            return list(self._alerts.values())
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active (firing) alerts."""
        return [a for a in self.get_all_alerts() if a.is_active()]
    
    def get_unacknowledged_alerts(self) -> List[Alert]:
        """Get all unacknowledged alerts."""
        return [
            a for a in self.get_all_alerts()
            if a.is_active() and a.status != AlertStatus.ACKNOWLEDGED
        ]
    
    def delete_alert(self, alert_id: str) -> bool:
        """
        Delete an alert.
        
        Args:
            alert_id: ID of the alert to delete
            
        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            if alert_id in self._alerts:
                del self._alerts[alert_id]
                return True
            return False
    
    def clear_all_alerts(self) -> int:
        """
        Clear all alerts.
        
        Returns:
            Number of alerts cleared
        """
        with self._lock:
            count = len(self._alerts)
            self._alerts.clear()
            return count
    
    # Alert rule management
    def register_rule(self, rule: AlertRule) -> None:
        """Register an alert rule."""
        with self._lock:
            self._rules[rule.name] = rule
    
    def unregister_rule(self, name: str) -> bool:
        """Unregister an alert rule."""
        with self._lock:
            if name in self._rules:
                del self._rules[name]
                return True
            return False
    
    def get_rule(self, name: str) -> Optional[AlertRule]:
        """Get an alert rule by name."""
        with self._lock:
            return self._rules.get(name)
    
    def get_all_rules(self) -> List[AlertRule]:
        """Get all alert rules."""
        with self._lock:
            return list(self._rules.values())
    
    def evaluate_rules(self, metric_name: str, metric_value: float) -> List[Alert]:
        """
        Evaluate all alert rules for a metric.
        
        Args:
            metric_name: Name of the metric
            metric_value: Current value of the metric
            
        Returns:
            List of alerts that should be firing
        """
        alerts = []
        
        for rule in self.get_all_rules():
            if not rule.enabled:
                continue
            if rule.metric_name != metric_name:
                continue
            
            if rule.evaluate(metric_value):
                # Check if there's already an active alert for this rule
                existing = self._get_alert_by_rule(rule)
                if existing and existing.is_active():
                    # Update existing alert
                    existing.updated_at = datetime.utcnow()
                    existing.metric_value = metric_value
                    existing.occurrences += 1
                    existing.last_occurrence = datetime.utcnow()
                    alerts.append(existing)
                else:
                    # Create new alert
                    alert = self.create_alert(
                        name=rule.name,
                        message=rule.message_template.format(
                            name=rule.name,
                            value=metric_value,
                            threshold=rule.threshold,
                        ),
                        severity=rule.severity,
                        description=rule.description_template.format(
                            name=rule.name,
                            value=metric_value,
                            threshold=rule.threshold,
                        ) if rule.description_template else rule.description,
                        metric_name=metric_name,
                        metric_value=metric_value,
                        threshold=rule.threshold,
                        tags=rule.tags,
                    )
                    if alert:
                        alerts.append(alert)
        
        return alerts
    
    def _get_rule_for_alert(self, alert: Alert) -> Optional[AlertRule]:
        """Get the alert rule that generated this alert."""
        for rule in self.get_all_rules():
            if rule.name == alert.name:
                return rule
        return None
    
    def _get_alert_by_rule(self, rule: AlertRule) -> Optional[Alert]:
        """Get an alert by its rule name."""
        for alert in self.get_all_alerts():
            if alert.name == rule.name:
                return alert
        return None
    
    # Alert handlers
    def add_handler(self, handler: Callable[[Alert], None]) -> None:
        """
        Add an alert handler.
        
        Args:
            handler: Function to call when an alert is raised
        """
        self._handlers.append(handler)
    
    def remove_handler(self, handler: Callable[[Alert], None]) -> bool:
        """
        Remove an alert handler.
        
        Args:
            handler: Handler to remove
            
        Returns:
            True if removed, False if not found
        """
        if handler in self._handlers:
            self._handlers.remove(handler)
            return True
        return False
    
    def clear_handlers(self) -> None:
        """Clear all alert handlers."""
        self._handlers.clear()
    
    def _notify_handlers(self, alert: Alert) -> None:
        """Notify all handlers about an alert."""
        for handler in self._handlers:
            try:
                handler(alert)
            except Exception:
                # Don't let handler errors propagate
                pass
    
    # Utility methods
    def export_json(self) -> List[Dict[str, Any]]:
        """Export all alerts as JSON-serializable list."""
        return [alert.to_dict() for alert in self.get_all_alerts()]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about alerts."""
        alerts = self.get_all_alerts()
        active = self.get_active_alerts()
        
        by_severity = defaultdict(int)
        by_status = defaultdict(int)
        by_source = defaultdict(int)
        
        for alert in alerts:
            by_severity[alert.severity.value] += 1
            by_status[alert.status.value] += 1
            by_source[alert.source] += 1
        
        return {
            "total": len(alerts),
            "active": len(active),
            "by_severity": dict(by_severity),
            "by_status": dict(by_status),
            "by_source": dict(by_source),
            "rules": len(self.get_all_rules()),
        }


# =============================================================================
# Predefined Alert Rules for Harness
# =============================================================================

class HarnessAlertRules:
    """Predefined alert rules for the harness."""
    
    # Agent alerts
    AGENT_TASK_FAILURE_RATE = AlertRule(
        name="agent_task_failure_rate",
        description="Alert when agent task failure rate is high",
        condition=">",
        metric_name="harness_agent_tasks_failed_total",
        threshold=5.0,  # 5 failures
        severity=AlertSeverity.HIGH,
        cooldown_seconds=300,
        tags=["agent", "tasks", "failure"],
        message_template="High task failure rate for {name}",
    )
    
    AGENT_TASK_TIMEOUT_RATE = AlertRule(
        name="agent_task_timeout_rate",
        description="Alert when many agent tasks timeout",
        condition=">",
        metric_name="harness_agent_tasks_failed_total",
        threshold=3.0,  # 3 timeouts
        severity=AlertSeverity.MEDIUM,
        cooldown_seconds=600,
        tags=["agent", "tasks", "timeout"],
        message_template="High task timeout rate for {name}",
    )
    
    # Sandbox alerts
    SANDBOX_VIOLATION = AlertRule(
        name="sandbox_violation",
        description="Alert when sandbox security violations occur",
        condition=">",
        metric_name="harness_sandbox_violations_total",
        threshold=1.0,  # Any violation
        severity=AlertSeverity.CRITICAL,
        cooldown_seconds=60,
        tags=["sandbox", "security", "violation"],
        message_template="Sandbox security violation detected",
    )
    
    # ACI alerts
    ACI_VALIDATION_ERROR_RATE = AlertRule(
        name="aci_validation_error_rate",
        description="Alert when ACI validation errors are frequent",
        condition=">",
        metric_name="harness_aci_validation_errors_total",
        threshold=10.0,  # 10 errors
        severity=AlertSeverity.MEDIUM,
        cooldown_seconds=300,
        tags=["aci", "validation", "errors"],
        message_template="High ACI validation error rate",
    )
    
    # Performance alerts
    AGENT_EXECUTION_SLOW = AlertRule(
        name="agent_execution_slow",
        description="Alert when agent execution is slow",
        condition=">",
        metric_name="harness_agent_execution_time_seconds",
        threshold=30.0,  # 30 seconds
        severity=AlertSeverity.LOW,
        cooldown_seconds=300,
        tags=["agent", "performance", "slow"],
        message_template="Agent execution is slow: {value}s > {threshold}s",
    )


# =============================================================================
# Global Alert Manager Instance
# =============================================================================

_alert_manager: Optional[AlertManager] = None

def get_alert_manager() -> AlertManager:
    """Get the global alert manager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
        # Register harness alert rules
        _register_harness_rules(_alert_manager)
    return _alert_manager


def _register_harness_rules(manager: AlertManager) -> None:
    """Register all harness alert rules with the manager."""
    rules = HarnessAlertRules()
    
    for attr_name in dir(rules):
        attr = getattr(rules, attr_name)
        if isinstance(attr, AlertRule):
            manager.register_rule(attr)


# Convenience functions
def raise_alert(
    name: str,
    message: str,
    severity: AlertSeverity = AlertSeverity.MEDIUM,
    description: str = "",
    source: str = "harness",
    component: str = "",
    tags: Optional[List[str]] = None,
    metric_name: Optional[str] = None,
    metric_value: Optional[float] = None,
    threshold: Optional[float] = None,
    data: Optional[Dict[str, Any]] = None,
) -> Alert:
    """Raise an alert (convenience function)."""
    return get_alert_manager().create_alert(
        name=name,
        message=message,
        severity=severity,
        description=description,
        source=source,
        component=component,
        tags=tags,
        metric_name=metric_name,
        metric_value=metric_value,
        threshold=threshold,
        data=data,
    )


def resolve_alert(
    alert_id: str,
    resolution: Optional[str] = None,
    resolved_by: Optional[str] = None,
) -> Optional[Alert]:
    """Resolve an alert (convenience function)."""
    return get_alert_manager().resolve_alert(alert_id, resolution, resolved_by)


# Import timedelta
from datetime import timedelta
