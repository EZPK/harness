/**
 * Distributed Tracing
 * 
 * Simple tracing implementation that can be extended to integrate with
 * OpenTelemetry, Jaeger, or Zipkin.
 */

import { v4 as uuidv4 } from 'uuid';
import { incrementMetric } from './metrics';

// =============================================================================
// Types
// =============================================================================

export interface SpanContext {
  traceId: string;
  spanId: string;
  parentSpanId?: string;
  baggage?: Record<string, string>;
}

export interface Span {
  name: string;
  context: SpanContext;
  startTime: number;
  endTime?: number;
  duration?: number;
  tags: Record<string, any>;
  logs: Array<{ timestamp: number; fields: Record<string, any> }>;
  children: Span[];
}

export interface Tracer {
  startSpan(name: string, options?: { parent?: SpanContext; tags?: Record<string, any> }): Span;
  endSpan(span: Span): void;
  getCurrentSpan(): Span | undefined;
  setCurrentSpan(span: Span | undefined): void;
  addTag(span: Span, key: string, value: any): void;
  addLog(span: Span, fields: Record<string, any>): void;
}

// =============================================================================
// Span Implementation
// =============================================================================

class BasicSpan implements Span {
  readonly name: string;
  readonly context: SpanContext;
  readonly startTime: number;
  endTime?: number;
  duration?: number;
  tags: Record<string, any> = {};
  logs: Array<{ timestamp: number; fields: Record<string, any> }> = [];
  children: Span[] = [];

  constructor(name: string, parent?: SpanContext) {
    this.name = name;
    this.startTime = Date.now();
    this.context = {
      traceId: parent?.traceId || uuidv4(),
      spanId: uuidv4(),
      parentSpanId: parent?.spanId,
    };
  }

  end(): void {
    this.endTime = Date.now();
    this.duration = this.endTime - this.startTime;
  }
}

// =============================================================================
// Tracer Implementation
// =============================================================================

class BasicTracer implements Tracer {
  private currentSpan: Span | undefined;

  startSpan(name: string, options: { parent?: SpanContext; tags?: Record<string, any> } = {}): Span {
    const span = new BasicSpan(name, options.parent);
    
    if (options.tags) {
      span.tags = { ...options.tags };
    }

    // If there's a current span, add this as a child
    if (this.currentSpan) {
      this.currentSpan.children.push(span);
      span.context.traceId = this.currentSpan.context.traceId;
    }

    return span;
  }

  endSpan(span: Span): void {
    if (span instanceof BasicSpan) {
      span.end();
      
      // Record duration metric
      if (span.duration !== undefined) {
        incrementMetric('tracing.span.duration', span.duration, {
          span: span.name,
        });
      }
    }

    // If this is the current span, clear it
    if (this.currentSpan === span) {
      this.currentSpan = undefined;
    }
  }

  getCurrentSpan(): Span | undefined {
    return this.currentSpan;
  }

  setCurrentSpan(span: Span | undefined): void {
    this.currentSpan = span;
  }

  addTag(span: Span, key: string, value: any): void {
    span.tags[key] = value;
  }

  addLog(span: Span, fields: Record<string, any>): void {
    span.logs.push({
      timestamp: Date.now(),
      fields: { ...fields },
    });
  }
}

// =============================================================================
// Global Tracer
// =============================================================================

export const tracer = new BasicTracer();

// =============================================================================
// Public API
// =============================================================================

/**
 * Get the global tracer
 */
export function getTracer(): Tracer {
  return tracer;
}

/**
 * Start a new span
 */
export function startSpan(name: string, tags: Record<string, any> = {}): Span {
  const span = tracer.startSpan(name, { tags });
  tracer.setCurrentSpan(span);
  return span;
}

/**
 * End the current span
 */
export function endSpan(span: Span): void {
  tracer.endSpan(span);
  if (tracer.getCurrentSpan() === span) {
    tracer.setCurrentSpan(undefined);
  }
}

/**
 * Add a tag to a span
 */
export function addTag(span: Span, key: string, value: any): void {
  tracer.addTag(span, key, value);
}

/**
 * Add a log entry to a span
 */
export function addLog(span: Span, fields: Record<string, any>): void {
  tracer.addLog(span, fields);
}

/**
 * Execute a function with a span
 */
export async function withSpan<T>(
  name: string,
  fn: () => Promise<T> | T,
  tags: Record<string, any> = {}
): Promise<T> {
  const span = startSpan(name, tags);
  
  try {
    const result = await fn();
    return result;
  } finally {
    endSpan(span);
  }
}

/**
 * Get the current span
 */
export function getCurrentSpan(): Span | undefined {
  return tracer.getCurrentSpan();
}
