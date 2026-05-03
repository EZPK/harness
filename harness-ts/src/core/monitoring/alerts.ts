/**
 * Alert System
 * 
 * Simple alert system for monitoring and notifications.
 */

import { v4 as uuidv4 } from 'uuid';
import { type Span } from './tracing';

// =============================================================================
// Types
// =============================================================================

export type AlertSeverity = 'critical' | 'error' | 'warning' | 'info' | 'debug';

export interface Alert {
  id: string;
  severity: AlertSeverity;
  message: string;
  description?: string;
  timestamp: Date;
  context?: Record<string, any>;
  span?: Span;
  resolved: boolean;
  resolvedAt?: Date;
  resolvedBy?: string;
}

export interface AlertHandler {
  (alert: Alert): void;
}

export interface AlertCondition {
  metric: string;
  threshold: number;
  comparison: 'gt' | 'gte' | 'lt' | 'lte' | 'eq' | 'neq';
  severity: AlertSeverity;
  message: string;
  period: number; // in milliseconds
}

// =============================================================================
// Alert Manager
// =============================================================================

export class AlertManager {
  private alerts: Map<string, Alert> = new Map();
  private handlers: AlertHandler[] = [];
  private conditions: AlertCondition[] = [];
  private enabled: boolean = true;

  /**
   * Enable or disable alerts
   */
  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
  }

  /**
   * Register an alert handler
   */
  addHandler(handler: AlertHandler): void {
    this.handlers.push(handler);
  }

  /**
   * Remove an alert handler
   */
  removeHandler(handler: AlertHandler): void {
    const index = this.handlers.indexOf(handler);
    if (index !== -1) {
      this.handlers.splice(index, 1);
    }
  }

  /**
   * Add an alert condition for automatic alert generation
   */
  addCondition(condition: AlertCondition): void {
    this.conditions.push(condition);
  }

  /**
   * Raise an alert
   */
  raise(
    severity: AlertSeverity,
    message: string,
    description?: string,
    context?: Record<string, any>,
    span?: Span
  ): Alert {
    if (!this.enabled) {
      return this.createAlert(severity, message, description, context, span, true);
    }

    const alert = this.createAlert(severity, message, description, context, span, false);
    this.alerts.set(alert.id, alert);

    // Notify handlers
    for (const handler of this.handlers) {
      try {
        handler(alert);
      } catch (error) {
        console.error('Alert handler error:', error);
      }
    }

    return alert;
  }

  /**
   * Resolve an alert
   */
  resolve(alertId: string, resolvedBy?: string): Alert | undefined {
    const alert = this.alerts.get(alertId);
    if (!alert) return undefined;

    alert.resolved = true;
    alert.resolvedAt = new Date();
    alert.resolvedBy = resolvedBy;

    return alert;
  }

  /**
   * Get an alert by ID
   */
  getAlert(alertId: string): Alert | undefined {
    return this.alerts.get(alertId);
  }

  /**
   * Get all alerts
   */
  getAllAlerts(): Alert[] {
    return Array.from(this.alerts.values());
  }

  /**
   * Get active (unresolved) alerts
   */
  getActiveAlerts(): Alert[] {
    return Array.from(this.alerts.values()).filter((a) => !a.resolved);
  }

  /**
   * Get alerts by severity
   */
  getAlertsBySeverity(severity: AlertSeverity): Alert[] {
    return Array.from(this.alerts.values()).filter((a) => a.severity === severity);
  }

  /**
   * Clear all alerts
   */
  clear(): void {
    this.alerts.clear();
  }

  /**
   * Clear alerts by severity
   */
  clearBySeverity(severity: AlertSeverity): void {
    for (const [id, alert] of this.alerts.entries()) {
      if (alert.severity === severity) {
        this.alerts.delete(id);
      }
    }
  }

  /**
   * Check conditions and raise alerts automatically
   */
  checkConditions(metrics: Record<string, number>): void {
    if (!this.enabled) return;

    for (const condition of this.conditions) {
      const value = metrics[condition.metric];
      if (value === undefined) continue;

      let shouldAlert = false;
      switch (condition.comparison) {
        case 'gt':
          shouldAlert = value > condition.threshold;
          break;
        case 'gte':
          shouldAlert = value >= condition.threshold;
          break;
        case 'lt':
          shouldAlert = value < condition.threshold;
          break;
        case 'lte':
          shouldAlert = value <= condition.threshold;
          break;
        case 'eq':
          shouldAlert = value === condition.threshold;
          break;
        case 'neq':
          shouldAlert = value !== condition.threshold;
          break;
      }

      if (shouldAlert) {
        this.raise(
          condition.severity,
          condition.message,
          `${condition.metric} ${condition.comparison} ${condition.threshold} (current: ${value})`
        );
      }
    }
  }

  /**
   * Create a new alert
   */
  private createAlert(
    severity: AlertSeverity,
    message: string,
    description?: string,
    context?: Record<string, any>,
    span?: Span,
    resolved: boolean = false
  ): Alert {
    return {
      id: uuidv4(),
      severity,
      message,
      description,
      timestamp: new Date(),
      context,
      span,
      resolved,
    };
  }
}

// =============================================================================
// Global Instance
// =============================================================================

export const alertManager = new AlertManager();

// =============================================================================
// Public API
// =============================================================================

/**
 * Get the global alert manager
 */
export function getAlertManager(): AlertManager {
  return alertManager;
}

/**
 * Raise an alert
 */
export function raiseAlert(
  severity: AlertSeverity,
  message: string,
  description?: string,
  context?: Record<string, any>,
  span?: Span
): Alert {
  return alertManager.raise(severity, message, description, context, span);
}

/**
 * Resolve an alert
 */
export function resolveAlert(alertId: string, resolvedBy?: string): Alert | undefined {
  return alertManager.resolve(alertId, resolvedBy);
}

/**
 * Get all alerts
 */
export function getAllAlerts(): Alert[] {
  return alertManager.getAllAlerts();
}

/**
 * Get active alerts
 */
export function getActiveAlerts(): Alert[] {
  return alertManager.getActiveAlerts();
}

/**
 * Get alerts by severity
 */
export function getAlertsBySeverity(severity: AlertSeverity): Alert[] {
  return alertManager.getAlertsBySeverity(severity);
}

/**
 * Add an alert handler
 */
export function onAlert(handler: AlertHandler): void {
  alertManager.addHandler(handler);
}

/**
 * Add an alert condition
 */
export function addAlertCondition(condition: AlertCondition): void {
  alertManager.addCondition(condition);
}
