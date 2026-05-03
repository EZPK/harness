/**
 * Task Decomposer
 * 
 * Decomposes complex tasks into smaller, manageable subtasks.
 */

import { type TaskType, type DecompositionStrategy, type TaskID, type TaskContext } from '@/configs/schemas';
import { type AgentRegistry } from '@/agents/registry';
import { incrementMetric } from '@/core/monitoring/metrics';

// =============================================================================
// Types
// =============================================================================

/**
 * Decomposed task result
 */
export interface DecomposedTask {
  id: TaskID;
  parentId: TaskID;
  type: TaskType;
  description: string;
  priority: number;
  dependencies: TaskID[];
}

/**
 * Decomposition result
 */
export interface DecompositionResult {
  tasks: DecomposedTask[];
  isDecomposed: boolean;
  strategy: DecompositionStrategy;
}

/**
 * Decomposition template
 */
interface DecompositionTemplate {
  match: (task: any) => boolean;
  decompose: (task: any) => DecomposedTask[];
}

// =============================================================================
// Decomposition Templates
// =============================================================================

const TEMPLATES: DecompositionTemplate[] = [
  {
    match: (task) => task.type === 'implement_feature',
    decompose: (task) => [
      {
        id: `${task.id}-plan`,
        parentId: task.id,
        type: 'analyze',
        description: `Analyze requirements for feature: ${task.description}`,
        priority: 1,
        dependencies: [],
      },
      {
        id: `${task.id}-design`,
        parentId: task.id,
        type: 'analyze',
        description: `Design implementation for feature: ${task.description}`,
        priority: 1,
        dependencies: [`${task.id}-plan`],
      },
      {
        id: `${task.id}-implement`,
        parentId: task.id,
        type: 'implement_feature',
        description: `Implement feature: ${task.description}`,
        priority: 2,
        dependencies: [`${task.id}-design`],
      },
      {
        id: `${task.id}-test`,
        parentId: task.id,
        type: 'write_tests',
        description: `Write tests for feature: ${task.description}`,
        priority: 2,
        dependencies: [`${task.id}-implement`],
      },
    ],
  },
  {
    match: (task) => task.type === 'fix_bug',
    decompose: (task) => [
      {
        id: `${task.id}-reproduce`,
        parentId: task.id,
        type: 'debug_test',
        description: `Reproduce bug: ${task.description}`,
        priority: 1,
        dependencies: [],
      },
      {
        id: `${task.id}-analyze`,
        parentId: task.id,
        type: 'analyze',
        description: `Analyze bug cause: ${task.description}`,
        priority: 1,
        dependencies: [`${task.id}-reproduce`],
      },
      {
        id: `${task.id}-fix`,
        parentId: task.id,
        type: 'fix_bug',
        description: `Fix bug: ${task.description}`,
        priority: 2,
        dependencies: [`${task.id}-analyze`],
      },
      {
        id: `${task.id}-verify`,
        parentId: task.id,
        type: 'run_tests',
        description: `Verify bug fix: ${task.description}`,
        priority: 2,
        dependencies: [`${task.id}-fix`],
      },
    ],
  },
  {
    match: (task) => task.type === 'code_review',
    decompose: (task) => [
      {
        id: `${task.id}-static`,
        parentId: task.id,
        type: 'analyze',
        description: `Static analysis for code review: ${task.description}`,
        priority: 1,
        dependencies: [],
      },
      {
        id: `${task.id}-review`,
        parentId: task.id,
        type: 'code_review',
        description: `Manual code review: ${task.description}`,
        priority: 2,
        dependencies: [`${task.id}-static`],
      },
      {
        id: `${task.id}-feedback`,
        parentId: task.id,
        type: 'analyze',
        description: `Compile review feedback: ${task.description}`,
        priority: 2,
        dependencies: [`${task.id}-review`],
      },
    ],
  },
];

// =============================================================================
// Decomposition Strategies
// =============================================================================

/**
 * Template-based decomposition
 * Uses predefined templates for known task types
 */
const templateStrategy = (
  task: any,
  context: TaskContext,
  _registry: AgentRegistry
): DecompositionResult => {
  for (const template of TEMPLATES) {
    if (template.match(task)) {
      const tasks = template.decompose(task);
      return {
        tasks,
        isDecomposed: true,
        strategy: 'template',
      };
    }
  }

  // No matching template - return original task
  const parentId = context?.taskId || task.id;
  return {
    tasks: [{
      id: task.id,
      parentId,
      type: task.type || 'general',
      description: task.description,
      priority: 1,
      dependencies: [],
    }],
    isDecomposed: false,
    strategy: 'template',
  };
};

/**
 * Semantic decomposition
 * Uses LLM to decompose complex tasks (placeholder - would need LLM integration)
 */
const semanticStrategy = (
  task: any,
  context: TaskContext,
  _registry: AgentRegistry
): DecompositionResult => {
  // Check if task description contains multiple clear steps
  const description = task.description || '';
  const hasMultipleSteps = description.split('\n').length > 3 ||
    description.split('.').length > 3 ||
    description.includes('first') ||
    description.includes('then') ||
    description.includes('next');

  if (hasMultipleSteps) {
    // Simple decomposition: split by sentences/paragraphs
    const sentences = description.split(/[.\n]+/).filter((s: string) => s.trim().length > 0);
    const tasks = sentences.map((sentence: string, index: number) => ({
      id: `${task.id}-step-${index + 1}`,
      parentId: task.id,
      type: 'general',
      description: sentence.trim(),
      priority: index + 1,
      dependencies: index > 0 ? [`${task.id}-step-${index}`] : [],
    }));

    return {
      tasks,
      isDecomposed: tasks.length > 1,
      strategy: 'semantic',
    };
  }

  const parentId = context?.taskId || task.id;
  return {
    tasks: [{
      id: task.id,
      parentId,
      type: task.type || 'general',
      description: task.description,
      priority: 1,
      dependencies: [],
    }],
    isDecomposed: false,
    strategy: 'semantic',
  };
};

/**
 * Hybrid decomposition
 * Tries template first, then falls back to semantic
 */
const hybridStrategy = (
  task: any,
  context: TaskContext,
  registry: AgentRegistry
): DecompositionResult => {
  const templateResult = templateStrategy(task, context, registry);
  if (templateResult.isDecomposed) {
    return templateResult;
  }
  return semanticStrategy(task, context, registry);
};

/**
 * Recursive decomposition
 * Recursively decomposes until atomic tasks
 */
const recursiveStrategy = (
  task: any,
  context: TaskContext,
  registry: AgentRegistry,
  depth: number = 0,
  maxDepth: number = 3
): DecompositionResult => {
  if (depth >= maxDepth) {
    return {
      tasks: [{
        id: task.id,
        parentId: context.taskId || task.id,
        type: task.type || 'general',
        description: task.description,
        priority: 1,
        dependencies: [],
      }],
      isDecomposed: false,
      strategy: 'recursive',
    };
  }

  // Try hybrid decomposition
  const hybridResult = hybridStrategy(task, context, registry);
  
  if (!hybridResult.isDecomposed) {
    return hybridResult;
  }

  // Recursively decompose each subtask
  const allTasks: DecomposedTask[] = [];
  for (const subtask of hybridResult.tasks) {
    const subResult = recursiveStrategy(
      { id: subtask.id, type: subtask.type, description: subtask.description },
      { taskId: subtask.parentId },
      registry,
      depth + 1,
      maxDepth
    );
    allTasks.push(...subResult.tasks);
  }

  return {
    tasks: allTasks,
    isDecomposed: true,
    strategy: 'recursive',
  };
};

// =============================================================================
// Strategy Factory
// =============================================================================

const STRATEGIES: Record<DecompositionStrategy, (task: any, context: TaskContext, registry: AgentRegistry) => DecompositionResult> = {
  template: templateStrategy,
  semantic: semanticStrategy,
  hybrid: hybridStrategy,
  recursive: (task, context, registry) => recursiveStrategy(task, context, registry),
};

// =============================================================================
// Task Decomposer Class
// =============================================================================

/**
 * Task Decomposer
 * 
 * Responsible for decomposing complex tasks into smaller subtasks.
 */
export class TaskDecomposer {
  private registry: AgentRegistry;
  private strategy: DecompositionStrategy;

  constructor(registry: AgentRegistry, strategy: DecompositionStrategy = 'hybrid') {
    this.registry = registry;
    this.strategy = strategy;
  }

  /**
   * Set the decomposition strategy
   */
  setStrategy(strategy: DecompositionStrategy): void {
    this.strategy = strategy;
  }

  /**
   * Get the current decomposition strategy
   */
  getStrategy(): DecompositionStrategy {
    return this.strategy;
  }

  /**
   * Decompose a task
   */
  decompose(task: any, context: TaskContext = { taskId: '' }): DecompositionResult {
    const span = { name: 'TaskDecomposer.decompose', startTime: Date.now() };

    try {
      const strategyImpl = STRATEGIES[this.strategy];
      if (!strategyImpl) {
        throw new Error(`Unknown decomposition strategy: ${this.strategy}`);
      }

      const result = strategyImpl(task, context, this.registry);

      incrementMetric('decomposer.tasks.decomposed', result.tasks.length, {
        strategy: this.strategy,
        decomposed: String(result.isDecomposed),
      });

      return result;
    } finally {
      const duration = Date.now() - (span as any).startTime;
      incrementMetric('decomposer.duration', duration, { strategy: this.strategy });
    }
  }

  /**
   * Check if a task should be decomposed
   */
  shouldDecompose(task: any): boolean {
    const result = this.decompose(task);
    return result.isDecomposed && result.tasks.length > 1;
  }

  /**
   * Get decomposition statistics
   */
  getStats() {
    return {
      strategy: this.strategy,
      templates: TEMPLATES.length,
    };
  }
}
