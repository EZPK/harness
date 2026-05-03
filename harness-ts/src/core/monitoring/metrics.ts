/**
 * Metrics Collection
 * 
 * Simple metrics collection system. Can be extended to integrate with
 * Prometheus, StatsD, or other monitoring systems.
 */



// =============================================================================
// Types
// =============================================================================

export type MetricType = 'counter' | 'gauge' | 'histogram' | 'summary';

export interface MetricOptions {
  type: MetricType;
  name: string;
  description: string;
  labels?: string[];
}

export interface MetricValue {
  value: number;
  labels?: Record<string, string>;
  timestamp?: number;
}

export interface MetricData {
  name: string;
  type: MetricType;
  description: string;
  values: MetricValue[];
  total: number;
}

// =============================================================================
// Metrics Collector
// =============================================================================

export class MetricsCollector {
  private metrics: Map<string, MetricData> = new Map();
  private enabled: boolean = true;

  /**
   * Enable or disable metrics collection
   */
  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
  }

  /**
   * Increment a counter metric
   */
  increment(name: string, value: number = 1, labels: Record<string, string> = {}): void {
    if (!this.enabled) return;

    const key = this.getKey(name, labels);
    let metric = this.metrics.get(key);

    if (!metric) {
      metric = {
        name,
        type: 'counter',
        description: `Counter for ${name}`,
        values: [],
        total: 0,
      };
      this.metrics.set(key, metric);
    }

    metric.values.push({ value, labels, timestamp: Date.now() });
    metric.total += value;
  }

  /**
   * Record a gauge metric
   */
  recordGauge(name: string, value: number, labels: Record<string, string> = {}): void {
    if (!this.enabled) return;

    const key = this.getKey(name, labels);
    let metric = this.metrics.get(key);

    if (!metric) {
      metric = {
        name,
        type: 'gauge',
        description: `Gauge for ${name}`,
        values: [],
        total: 0,
      };
      this.metrics.set(key, metric);
    }

    metric.values.push({ value, labels, timestamp: Date.now() });
    metric.total = value; // Gauge stores current value
  }

  /**
   * Record a histogram metric
   */
  recordHistogram(name: string, value: number, labels: Record<string, string> = {}): void {
    if (!this.enabled) return;

    const key = this.getKey(name, labels);
    let metric = this.metrics.get(key);

    if (!metric) {
      metric = {
        name,
        type: 'histogram',
        description: `Histogram for ${name}`,
        values: [],
        total: 0,
      };
      this.metrics.set(key, metric);
    }

    metric.values.push({ value, labels, timestamp: Date.now() });
    metric.total += value;
  }

  /**
   * Get metric by name
   */
  getMetric(name: string, labels: Record<string, string> = {}): MetricData | undefined {
    const key = this.getKey(name, labels);
    return this.metrics.get(key);
  }

  /**
   * Get all metrics
   */
  getAllMetrics(): MetricData[] {
    return Array.from(this.metrics.values());
  }

  /**
   * Get metrics summary
   */
  getSummary(): Record<string, { count: number; total: number; avg: number }> {
    const summary: Record<string, { count: number; total: number; avg: number }> = {};

    for (const metric of this.metrics.values()) {
      const key = metric.name;
      if (!summary[key]) {
        summary[key] = { count: 0, total: 0, avg: 0 };
      }
      summary[key].count += metric.values.length;
      summary[key].total += metric.total;
      summary[key].avg = summary[key].total / Math.max(1, summary[key].count);
    }

    return summary;
  }

  /**
   * Reset all metrics
   */
  reset(): void {
    this.metrics.clear();
  }

  /**
   * Reset a specific metric
   */
  resetMetric(name: string, labels: Record<string, string> = {}): void {
    const key = this.getKey(name, labels);
    this.metrics.delete(key);
  }

  /**
   * Generate a unique key for a metric with labels
   */
  private getKey(name: string, labels: Record<string, string>): string {
    const labelString = Object.entries(labels)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([k, v]) => `${k}=${v}`)
      .join(',');
    return labelString ? `${name}{${labelString}}` : name;
  }

  /**
   * Export metrics to JSON
   */
  exportToJSON(): string {
    return JSON.stringify({
      metrics: this.getAllMetrics(),
      summary: this.getSummary(),
      timestamp: Date.now(),
    }, null, 2);
  }

  /**
   * Export metrics to Prometheus format
   */
  exportToPrometheus(): string {
    const lines: string[] = [];

    for (const metric of this.metrics.values()) {
      for (const value of metric.values) {
        const labels = value.labels ? Object.entries(value.labels)
          .map(([k, v]) => `${k}="${v}"`) : [];
        const labelString = labels.length > 0 ? `{${labels.join(',')}}` : '';
        
        switch (metric.type) {
          case 'counter':
          case 'gauge':
            lines.push(`${metric.name}${labelString} ${value.value}`);
            break;
          case 'histogram':
          case 'summary':
            lines.push(`${metric.name}${labelString} ${value.value}`);
            break;
        }
      }
    }

    return lines.join('\n');
  }
}

// =============================================================================
// Global Instance
// =============================================================================

export const metricsCollector = new MetricsCollector();

// =============================================================================
// Public API
// =============================================================================

/**
 * Get the global metrics collector
 */
export function getMetricsCollector(): MetricsCollector {
  return metricsCollector;
}

/**
 * Increment a counter metric
 */
export function incrementMetric(
  name: string,
  value: number = 1,
  labels: Record<string, string> = {}
): void {
  metricsCollector.increment(name, value, labels);
}

/**
 * Record a gauge metric
 */
export function recordGauge(
  name: string,
  value: number,
  labels: Record<string, string> = {}
): void {
  metricsCollector.recordGauge(name, value, labels);
}

/**
 * Record a histogram metric
 */
export function recordHistogram(
  name: string,
  value: number,
  labels: Record<string, string> = {}
): void {
  metricsCollector.recordHistogram(name, value, labels);
}

/**
 * Start a span for tracing
 */
export function startSpan(name: string, labels: Record<string, any> = {}): any {
  // Simple span implementation - just track start time
  return {
    name,
    labels,
    startTime: Date.now(),
  };
}

/**
 * End a span
 */
export function endSpan(span: any): void {
  if (span) {
    const duration = Date.now() - span.startTime;
    incrementMetric('tracing.span.duration', duration, {
      span: span.name,
      ...span.labels,
    });
  }
}

/**
 * Get all metrics
 */
export function getAllMetrics(): MetricData[] {
  return metricsCollector.getAllMetrics();
}

/**
 * Get metrics summary
 */
export function getMetricsSummary(): Record<string, { count: number; total: number; avg: number }> {
  return metricsCollector.getSummary();
}

/**
 * Reset all metrics
 */
export function resetMetrics(): void {
  metricsCollector.reset();
}
