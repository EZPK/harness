/**
 * Result Aggregator
 * 
 * Aggregates results from multiple agents into a unified response.
 */

import { type TaskResult } from '@/configs/schemas';
import { incrementMetric } from '@/core/monitoring/metrics';

// =============================================================================
// Types
// =============================================================================

/**
 * Aggregation strategy
 */
export type AggregationStrategy = 
  | 'concatenate'
  | 'merge'
  | 'vote'
  | 'weighted'
  | 'first'
  | 'custom';

/**
 * Aggregation options
 */
export interface AggregationOptions {
  strategy?: AggregationStrategy;
  delimiter?: string;
  weights?: Record<string, number>;
  customAggregator?: (results: TaskResult[]) => any;
}

/**
 * Aggregation result
 */
export interface AggregationResult {
  results: TaskResult[];
  aggregated: any;
  strategy: AggregationStrategy;
  conflicts: boolean;
}

// =============================================================================
// Aggregation Strategies
// =============================================================================

/**
 * Concatenate strategy
 * Joins results with a delimiter
 */
function concatenateStrategy(results: TaskResult[], options: AggregationOptions): any {
  const delimiter = options.delimiter || '\n\n';
  const texts = results
    .filter(r => r.result && typeof r.result.text === 'string')
    .map(r => r.result.text);
  
  if (texts.length === 0) {
    return results.map(r => r.result).join(delimiter);
  }
  
  return texts.join(delimiter);
}

/**
 * Merge strategy
 * Combines results into an object
 */
function mergeStrategy(results: TaskResult[], _options: AggregationOptions): any {
  const merged: Record<string, any> = {};
  
  for (let i = 0; i < results.length; i++) {
    const result = results[i];
    const agentName = result.result?.agentName || `agent_${i}`;
    merged[agentName] = result.result;
  }
  
  return merged;
}

/**
 * Vote strategy
 * Selects the most common result
 */
function voteStrategy(results: TaskResult[], _options: AggregationOptions): any {
  if (results.length === 0) return undefined;
  if (results.length === 1) return results[0].result;

  const resultMap: Map<string, { value: any; count: number }> = new Map();
  
  for (const result of results) {
    const key = JSON.stringify(result.result);
    if (!resultMap.has(key)) {
      resultMap.set(key, { value: result.result, count: 0 });
    }
    resultMap.get(key)!.count++;
  }
  
  // Find the most common result
  let maxEntry: { value: any; count: number } | undefined;
  for (const entry of resultMap.values()) {
    if (!maxEntry || entry.count > maxEntry.count) {
      maxEntry = entry;
    }
  }
  
  return maxEntry?.value;
}

/**
 * Weighted strategy
 * Combines results with weights
 */
function weightedStrategy(results: TaskResult[], options: AggregationOptions): any {
  const weights = options.weights || {};
  const weightedResults = results.map((result, index) => ({
    result,
    weight: weights[result.result?.agentName || `agent_${index}`] || 1,
  }));

  // Simple weighted average for numeric results
  const numericResults = weightedResults.filter(wr => typeof wr.result.result === 'number');
  if (numericResults.length > 0) {
    const sum = numericResults.reduce((acc, wr) => acc + (wr.result.result as number) * wr.weight, 0);
    const totalWeight = numericResults.reduce((acc, wr) => acc + wr.weight, 0);
    return sum / totalWeight;
  }

  // For non-numeric results, use weighted concatenation
  return weightedResults.map(wr => wr.result.result).join(' ');
}

/**
 * First strategy
 * Returns the first result
 */
function firstStrategy(results: TaskResult[], _options: AggregationOptions): any {
  return results[0]?.result;
}

/**
 * Custom strategy
 * Uses a custom aggregator function
 */
function customStrategy(results: TaskResult[], options: AggregationOptions): any {
  if (options.customAggregator) {
    return options.customAggregator(results);
  }
  return firstStrategy(results, options);
}

// =============================================================================
// Strategy Registry
// =============================================================================

const STRATEGIES: Record<AggregationStrategy, (results: TaskResult[], options: AggregationOptions) => any> = {
  concatenate: concatenateStrategy,
  merge: mergeStrategy,
  vote: voteStrategy,
  weighted: weightedStrategy,
  first: firstStrategy,
  custom: customStrategy,
};

// =============================================================================
// Result Aggregator Class
// =============================================================================

/**
 * Result Aggregator
 * 
 * Responsible for combining results from multiple agents into a unified response.
 */
export class ResultAggregator {
  private defaultStrategy: AggregationStrategy = 'merge';
  private defaultOptions: AggregationOptions = {};

  /**
   * Set the default aggregation strategy
   */
  setDefaultStrategy(strategy: AggregationStrategy): void {
    this.defaultStrategy = strategy;
  }

  /**
   * Set default aggregation options
   */
  setDefaultOptions(options: AggregationOptions): void {
    this.defaultOptions = { ...this.defaultOptions, ...options };
  }

  /**
   * Aggregate results
   */
  aggregate(
    results: TaskResult[],
    options: AggregationOptions = {}
  ): AggregationResult {
    const span = { name: 'ResultAggregator.aggregate', startTime: Date.now() };

    try {
      const strategy = options.strategy || this.defaultStrategy;
      const mergedOptions = { ...this.defaultOptions, ...options };

      const strategyImpl = STRATEGIES[strategy];
      if (!strategyImpl) {
        throw new Error(`Unknown aggregation strategy: ${strategy}`);
      }

      const aggregated = strategyImpl(results, mergedOptions);

      // Check for conflicts (different results from different agents)
      const conflicts = this.checkForConflicts(results);

      incrementMetric('aggregator.results.aggregated', 1, {
        strategy,
        resultCount: String(results.length),
        conflicts: String(conflicts),
      });

      return {
        results,
        aggregated,
        strategy,
        conflicts,
      };
    } finally {
      const duration = Date.now() - (span as any).startTime;
      incrementMetric('aggregator.duration', duration);
    }
  }

  /**
   * Check if results conflict
   */
  private checkForConflicts(results: TaskResult[]): boolean {
    if (results.length <= 1) return false;

    const firstResult = results[0].result;
    for (let i = 1; i < results.length; i++) {
      if (JSON.stringify(results[i].result) !== JSON.stringify(firstResult)) {
        return true;
      }
    }
    return false;
  }

  /**
   * Aggregate with a specific strategy
   */
  aggregateWithStrategy(
    results: TaskResult[],
    strategy: AggregationStrategy,
    options: AggregationOptions = {}
  ): AggregationResult {
    return this.aggregate(results, { ...options, strategy });
  }

  /**
   * Simple aggregation that concatenates text results
   */
  simpleAggregate(results: TaskResult[]): string {
    return concatenateStrategy(results, { delimiter: '\n\n' });
  }

  /**
   * Get aggregation statistics
   */
  getStats() {
    return {
      defaultStrategy: this.defaultStrategy,
      availableStrategies: Object.keys(STRATEGIES) as AggregationStrategy[],
    };
  }
}
