/**
 * Task Router
 * 
 * Routes tasks to appropriate agents based on capability matching and routing strategy.
 */

import { type AgentID, type TaskID, type TaskContext, type RoutingStrategy } from '@/configs/schemas';
import { type AgentRegistry } from '@/agents/registry';
import { type BaseAgent } from '@/agents/base';
import { incrementMetric } from '@/core/monitoring/metrics';

// =============================================================================
// Types
// =============================================================================

/**
 * Task routing result
 */
export interface TaskRouting {
  taskId: TaskID;
  agentId: AgentID;
  task: any;
  score: number; // Matching score (0-1)
  reason: string;
}

/**
 * Routing strategy implementation
 */
export interface RoutingStrategyImpl {
  (task: any, context: TaskContext, registry: AgentRegistry): Promise<TaskRouting[]>;
}

// =============================================================================
// Routing Strategies
// =============================================================================

/**
 * Keyword-based routing
 * Matches task keywords to agent names and descriptions
 */
const keywordStrategy: RoutingStrategyImpl = async (task, context, registry) => {
  const agents = registry.getAllAgents();
  const taskText = (task.description || '') + (task.content || '') + (task.type || '');
  const taskKeywords = extractKeywords(taskText);

  const routings: TaskRouting[] = [];

  for (const agent of agents) {
    const agentKeywords = [
      agent.name.toLowerCase(),
      agent.description.toLowerCase(),
      ...agent.capabilities,
    ].join(' ');

    const matches = taskKeywords.filter(kw => agentKeywords.includes(kw));
    const score = matches.length / Math.max(1, taskKeywords.length);

    if (score > 0) {
      routings.push({
        taskId: context.taskId,
        agentId: agent.id,
        task,
        score,
        reason: `Keyword match: ${matches.join(', ')}`,
      });
    }
  }

  // Sort by score descending
  return routings.sort((a, b) => b.score - a.score);
};

/**
 * Capability-based routing
 * Matches required capabilities to agent capabilities
 */
const capabilityStrategy: RoutingStrategyImpl = async (task, context, registry) => {
  const agents = registry.getAllAgents();
  const requiredCapabilities = extractCapabilitiesFromTask(task);

  if (requiredCapabilities.length === 0) {
    // No specific capabilities required - return all agents
    return agents.map(agent => ({
      taskId: context.taskId,
      agentId: agent.id,
      task,
      score: 0.5,
      reason: 'No specific capabilities required',
    }));
  }

  const routings: TaskRouting[] = [];

  for (const agent of agents) {
    const matches = requiredCapabilities.filter(cap => agent.hasCapability(cap));
    const score = matches.length / requiredCapabilities.length;

    if (score > 0) {
      routings.push({
        taskId: context.taskId,
        agentId: agent.id,
        task,
        score,
        reason: `Capability match: ${matches.join(', ')}`,
      });
    }
  }

  // Sort by score descending, then by capability level
  return routings.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    const aAgent = registry.getAgent(a.agentId);
    const bAgent = registry.getAgent(b.agentId);
    if (!aAgent || !bAgent) return 0;
    return bAgent.getTaskCount() - aAgent.getTaskCount(); // Prefer less busy
  });
};

/**
 * Hybrid routing
 * First tries capability matching, then falls back to keyword matching
 */
const hybridStrategy: RoutingStrategyImpl = async (task, context, registry) => {
  // Try capability routing first
  const capabilityRoutings = await capabilityStrategy(task, context, registry);
  
  if (capabilityRoutings.length > 0) {
    return capabilityRoutings;
  }

  // Fall back to keyword routing
  return keywordStrategy(task, context, registry);
};

/**
 * Round-robin routing
 * Distributes tasks evenly among capable agents
 */
const roundRobinStrategy: RoutingStrategyImpl = async (task, context, registry) => {
  const agents = registry.getAvailableAgents();
  
  if (agents.length === 0) return [];

  // Simple round-robin based on task count
  const sorted = [...agents].sort((a, b) => a.getTaskCount() - b.getTaskCount());
  const selected = sorted[0];

  return [{
    taskId: context.taskId,
    agentId: selected.id,
    task,
    score: 1,
    reason: 'Round-robin selection',
  }];
};

/**
 * Priority routing
 * Routes to highest-priority capable agent
 */
const priorityStrategy: RoutingStrategyImpl = async (task, context, registry) => {
  const requiredCapabilities = extractCapabilitiesFromTask(task);
  const agents = registry.getAllAgents();

  const routings: TaskRouting[] = [];

  for (const agent of agents) {
    const matches = requiredCapabilities.filter(cap => agent.hasCapability(cap));
    if (matches.length === requiredCapabilities.length) {
      // Agent has all required capabilities
      const priority = getAgentPriority(agent);
      routings.push({
        taskId: context.taskId,
        agentId: agent.id,
        task,
        score: priority,
        reason: `Priority ${priority} with all capabilities`,
      });
    }
  }

  return routings.sort((a, b) => b.score - a.score);
};

/**
 * Learned routing
 * Uses historical performance data (placeholder - would need learning system)
 */
const learnedStrategy: RoutingStrategyImpl = async (task, context, registry) => {
  // For now, fall back to hybrid
  return hybridStrategy(task, context, registry);
};

// =============================================================================
// Routing Strategy Factory
// =============================================================================

const STRATEGIES: Record<RoutingStrategy, RoutingStrategyImpl> = {
  keyword: keywordStrategy,
  capability: capabilityStrategy,
  hybrid: hybridStrategy,
  round_robin: roundRobinStrategy,
  priority: priorityStrategy,
  learned: learnedStrategy,
};

// =============================================================================
// Utility Functions
// =============================================================================

/**
 * Extract keywords from text
 */
function extractKeywords(text: string): string[] {
  if (!text) return [];

  return text
    .toLowerCase()
    .split(/\W+/)
    .filter(word => word.length > 2 && word.length < 30)
    .reduce((unique: string[], word) => {
      if (!unique.includes(word)) {
        unique.push(word);
      }
      return unique;
    }, []);
}

/**
 * Extract capabilities from a task
 */
function extractCapabilitiesFromTask(task: any): string[] {
  const capabilities: string[] = [];

  // Check task type
  if (task.type) {
    const typeMapping: Record<string, string[]> = {
      implement_feature: ['coding', 'implementation'],
      fix_bug: ['debugging', 'coding'],
      refactor_code: ['coding', 'review'],
      optimize: ['analysis', 'optimization'],
      code_review: ['review', 'analysis'],
      architecture_review: ['review', 'architecture'],
      security_audit: ['security', 'analysis'],
      write_tests: ['testing', 'coding'],
      run_tests: ['testing'],
      debug_test: ['debugging', 'testing'],
      analyze: ['analysis'],
      summarize: ['summarization', 'analysis'],
      explain: ['explanation', 'analysis'],
      text_generation: ['text_generation', 'llm'],
      reasoning: ['reasoning', 'llm'],
    };
    capabilities.push(...(typeMapping[task.type] || []));
  }

  // Check for explicit capabilities in metadata
  if (task.metadata?.capabilities) {
    capabilities.push(...task.metadata.capabilities);
  }

  return [...new Set(capabilities)];
}

/**
 * Get agent priority (placeholder - would be configurable)
 */
function getAgentPriority(agent: BaseAgent): number {
  const priorities: Record<string, number> = {
    llm: 1,
    coder: 2,
    reviewer: 3,
    tester: 4,
    planner: 5,
    debugger: 6,
    researcher: 7,
    documenter: 8,
  };

  for (const cap of agent.capabilities) {
    if (priorities[cap]) {
      return priorities[cap];
    }
  }

  return 0;
}

// =============================================================================
// Task Router Class
// =============================================================================

/**
 * Task Router
 * 
 * Responsible for routing tasks to appropriate agents based on the configured strategy.
 */
export class TaskRouter {
  private registry: AgentRegistry;
  private strategy: RoutingStrategy;

  constructor(registry: AgentRegistry, strategy: RoutingStrategy = 'hybrid') {
    this.registry = registry;
    this.strategy = strategy;
  }

  /**
   * Set the routing strategy
   */
  setStrategy(strategy: RoutingStrategy): void {
    this.strategy = strategy;
  }

  /**
   * Get the current routing strategy
   */
  getStrategy(): RoutingStrategy {
    return this.strategy;
  }

  /**
   * Route a task to appropriate agents
   */
  async route(task: any, context: TaskContext = { taskId: '' }): Promise<TaskRouting[]> {
    const span = { name: 'TaskRouter.route', startTime: Date.now() };

    try {
      // Get the strategy implementation
      const strategyImpl = STRATEGIES[this.strategy];
      if (!strategyImpl) {
        throw new Error(`Unknown routing strategy: ${this.strategy}`);
      }

      // Execute the strategy
      const routings = await strategyImpl(task, context, this.registry);

      // Log the routing decision
      incrementMetric('router.tasks.routed', 1, { strategy: this.strategy });
      for (const routing of routings) {
        incrementMetric('router.agents.selected', 1, {
          strategy: this.strategy,
          agent: this.registry.getAgent(routing.agentId)?.name || 'unknown',
        });
      }

      return routings;
    } finally {
      const duration = Date.now() - (span as any).startTime;
      incrementMetric('router.duration', duration, { strategy: this.strategy });
    }
  }

  /**
   * Route a task to a specific agent
   */
  routeToAgent(task: any, agentId: AgentID, context: TaskContext): TaskRouting {
    return {
      taskId: context.taskId,
      agentId,
      task,
      score: 1,
      reason: 'Direct routing',
    };
  }

  /**
   * Find the best agent for a task
   */
  async findBestAgent(task: any, context: TaskContext): Promise<TaskRouting | undefined> {
    const routings = await this.route(task, context);
    return routings[0]; // Return the highest-scored routing
  }

  /**
   * Get routing statistics
   */
  getStats() {
    return {
      strategy: this.strategy,
      availableAgents: this.registry.getAvailableAgents().length,
      totalAgents: this.registry.getAgentCount(),
    };
  }
}
