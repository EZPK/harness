/**
 * God Agent
 * 
 * The central orchestrator that delegates tasks to specialist agents.
 * This is the heart of the Harness Agentic Framework.
 */

import { type AgentID, type TaskID, type GodAgentConfig, type TaskType, type TaskPriority, type TaskStatus, type TaskContext, type TaskResult, AgentStateSchema } from '@/configs/schemas';

import { BaseAgent } from '@/agents/base';
import { LLMAgent, createLLMAgent, type LLMTask } from '@/agents/specialists/llm';
import { AgentRegistry, getAgentRegistry, registerAgent } from '@/agents/registry';
import { TaskRouter } from '@/agents/god/router';
import { TaskDecomposer } from '@/agents/god/decomposer';
import { ResultAggregator } from '@/agents/god/aggregator';
import { loadConfig } from '@/configs/settings';
import { initializeProvidersFromEnv } from '@/providers';
import { incrementMetric } from '@/core/monitoring/metrics';
import { raiseAlert } from '@/core/monitoring/alerts';
import { startSpan, endSpan } from '@/core/monitoring/tracing';

// =============================================================================
// Task Types
// =============================================================================

/**
 * GodAgent task
 */
export interface GodAgentTask {
  id: TaskID;
  type: TaskType;
  description: string;
  content?: string;
  priority: TaskPriority;
  metadata?: Record<string, any>;
  parentTaskId?: TaskID;
  workflowId?: string;
  createdAt: Date;
}

/**
 * Workflow step
 */
export interface WorkflowStep {
  id: string;
  name: string;
  type: TaskType;
  description: string;
  agentId?: AgentID;
  dependsOn?: string[];
  status: TaskStatus;
}

/**
 * Workflow definition
 */
export interface WorkflowDefinition {
  id: string;
  name: string;
  description: string;
  steps: WorkflowStep[];
  createdAt: Date;
  status: TaskStatus;
}

// =============================================================================
// Task Status Update
// =============================================================================

export interface TaskStatusUpdate {
  taskId: TaskID;
  status: TaskStatus;
  message?: string;
  progress?: number; // 0-100
  result?: any;
  error?: Error;
  timestamp: Date;
}

// =============================================================================
// God Agent Configuration
// =============================================================================

export interface GodAgentOptions {
  config?: Partial<GodAgentConfig>;
  autoInitialize?: boolean;
}

// =============================================================================
// God Agent Class
// =============================================================================

/**
 * GodAgent - The central orchestrator
 * 
 * Responsibilities:
 * - Receive and validate incoming tasks
 * - Decompose complex tasks into subtasks
 * - Route tasks to appropriate specialist agents
 * - Aggregate results from multiple agents
 * - Manage workflows
 * - Track task status
 */
export class GodAgent extends BaseAgent {
  // Configuration
  private config: GodAgentConfig;

  // Components
  private registry: AgentRegistry;
  private router: TaskRouter;
  private decomposer: TaskDecomposer;
  private aggregator: ResultAggregator;

  // Task tracking
  private tasks: Map<TaskID, GodAgentTask> = new Map();
  private taskStatus: Map<TaskID, TaskStatusUpdate[]> = new Map();
  private workflows: Map<string, WorkflowDefinition> = new Map();

  // LLMAgent for orchestration
  private llmAgent: LLMAgent;

  // Auto-initialization
  private initialized: boolean = false;

  constructor(config: Partial<GodAgentConfig> = {}, options: GodAgentOptions = {}) {
    super('GodAgent', {
      description: 'Central orchestrator that delegates tasks to specialist agents',
      capabilities: [
        { name: 'orchestration', description: 'Coordinate multiple agents', level: 'expert' as any, version: '1.0', dependsOn: [] },
        { name: 'routing', description: 'Route tasks to appropriate agents', level: 'expert' as any, version: '1.0', dependsOn: [] },
        { name: 'decomposition', description: 'Break down complex tasks', level: 'expert' as any, version: '1.0', dependsOn: [] },
        { name: 'aggregation', description: 'Combine results from multiple agents', level: 'expert' as any, version: '1.0', dependsOn: [] },
        { name: 'workflow', description: 'Manage multi-step workflows', level: 'expert' as any, version: '1.0', dependsOn: [] },
      ],
    });

    // Load configuration
    this.config = { ...loadConfig(), ...config };

    // Initialize components
    this.registry = getAgentRegistry();
    this.router = new TaskRouter(this.registry, this.config.routingStrategy);
    this.decomposer = new TaskDecomposer(this.registry, this.config.decompositionStrategy);
    this.aggregator = new ResultAggregator();

    // Initialize LLMAgent with orchestration config
    this.llmAgent = createLLMAgent(
      'GodAgent_LLM',
      this.config.llm.provider as any,
      this.config.llm.model
    );

    // Register self
    this.registerSelf();

    // Initialize providers from environment
    initializeProvidersFromEnv();

    // Auto-initialize if requested
    if (options.autoInitialize !== false) {
      this.initialize().catch(console.error);
    }
  }

  // ===========================================================================
  // Initialization
  // ===========================================================================

  getSystemPrompt(): string {
    return `You are the God Agent, the central orchestrator of the Harness Agentic Framework multi-agent system.
    
    Your responsibilities:
    1. Analyze incoming tasks and determine the best approach
    2. Decompose complex tasks into manageable subtasks when needed
    3. Route tasks to the most appropriate specialist agent(s)
    4. Coordinate parallel execution when beneficial
    5. Aggregate and validate results from multiple agents
    6. Handle errors and retry when appropriate
    7. Maintain workflow state and context
    
    Guidelines:
    - Always consider the task type and required capabilities
    - Use decomposition for complex, multi-step tasks
    - Prefer specialist agents over general agents when possible
    - Aggregate results thoughtfully, resolving conflicts when they arise
    - Maintain clear communication about task progress
    - Handle errors gracefully and provide useful error messages
    
    Available routing strategies: ${Object.values(this.config.routingStrategy).join(', ')}
    Available decomposition strategies: ${Object.values(this.config.decompositionStrategy).join(', ')}`;
  }

  getModel(): any {
    return this.llmAgent.getModel();
  }

  getTools(): any[] {
    return [
      {
        name: 'delegate_task',
        description: 'Delegate a task to a specialist agent',
        parameters: {
          type: 'object',
          properties: {
            agentName: { type: 'string', description: 'Name of the agent' },
            task: { type: 'object', description: 'Task to delegate' },
          },
          required: ['agentName', 'task'],
        },
      },
      {
        name: 'create_workflow',
        description: 'Create a new workflow from a complex task',
        parameters: {
          type: 'object',
          properties: {
            name: { type: 'string', description: 'Workflow name' },
            description: { type: 'string', description: 'Workflow description' },
            steps: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  name: { type: 'string' },
                  description: { type: 'string' },
                  agent: { type: 'string' },
                },
              },
            },
          },
          required: ['name', 'steps'],
        },
      },
    ];
  }

  // ===========================================================================
  // Task Execution
  // ===========================================================================

  /**
   * Execute a task (internal implementation)
   * This is called by the base class executeTask method
   */
  protected async _executeTask(task: GodAgentTask, context: TaskContext): Promise<any> {
    // Route and execute the task
    return this.routeAndExecute(task, context);
  }

  /**
   * Initialize the GodAgent and all registered agents
   */
  async initialize(): Promise<void> {
    if (this.initialized) return;

    const span = startSpan('GodAgent.initialize');

    try {
      this.state = AgentStateSchema.parse('initializing');
      this.updateStatus('Initializing GodAgent...');

      // Initialize LLMAgent
      await this.llmAgent.initialize();

      // Register LLMAgent
      registerAgent(this.llmAgent);

      // Initialize all registered agents
      await this.registry.initializeAll();

      this.state = AgentStateSchema.parse('idle');
      this.updateStatus('GodAgent ready');
      this.initialized = true;

      incrementMetric('god_agent.initialized', 1);
    } catch (error) {
      this.state = AgentStateSchema.parse('error');
      this.updateStatus(`Initialization failed: ${error}`);
      raiseAlert('error', 'Failed to initialize GodAgent', undefined, undefined, span);
      throw new Error(`Failed to initialize GodAgent: ${error}`);
    } finally {
      endSpan(span);
    }
  }

  /**
   * Register this agent with itself
   */
  private registerSelf(): void {
    // Don't register with the registry to avoid circular dependency
    // The GodAgent manages itself separately
  }

  // ===========================================================================
  // Task Submission
  // ===========================================================================

  /**
   * Submit a task to the GodAgent for execution
   */
  async submitTask(
    description: string,
    options: {
      type?: TaskType;
      content?: string;
      priority?: TaskPriority;
      metadata?: Record<string, any>;
      workflowId?: string;
    } = {}
  ): Promise<TaskResult> {
    const span = startSpan('GodAgent.submitTask', { taskId: options.metadata?.taskId });

    try {
      // Create task
      const task: GodAgentTask = {
        id: options.metadata?.taskId || this.generateTaskId(),
        type: options.type || 'general',
        description,
        content: options.content,
        priority: options.priority || 'medium',
        metadata: options.metadata || {},
        workflowId: options.workflowId,
        createdAt: new Date(),
      };

      // Store task
      this.tasks.set(task.id, task);
      this.updateTaskStatus(task.id, 'pending', 'Task received');

      // Create context
      const context: TaskContext = {
        taskId: task.id,
        userId: options.metadata?.userId,
        sessionId: options.metadata?.sessionId,
        parentTaskId: options.metadata?.parentTaskId,
        workflowId: task.workflowId,
        metadata: {
          ...options.metadata,
          submittedAt: new Date(),
        },
      };

      // Route and execute
      const result = await this.routeAndExecute(task, context);

      // Update status
      this.updateTaskStatus(task.id, 'completed', 'Task completed successfully', result);

      incrementMetric('god_agent.tasks.completed', 1, { type: task.type });

      return {
        taskId: task.id,
        result,
        timestamp: new Date(),
      };
    } catch (error) {
      const taskId = options.metadata?.taskId || 'unknown';
      this.updateTaskStatus(taskId, 'failed', `Task failed: ${error}`);
      incrementMetric('god_agent.tasks.failed', 1);
      raiseAlert('error', `Task failed: ${error}`, undefined, undefined, span);
      throw error;
    } finally {
      endSpan(span);
    }
  }

  // ===========================================================================
  // Task Routing and Execution
  // ===========================================================================

  /**
   * Route a task to appropriate agents and execute
   */
  private async routeAndExecute(task: GodAgentTask, context: TaskContext): Promise<any> {
    const span = startSpan('GodAgent.routeAndExecute', { taskId: task.id });

    try {
      // Step 1: Check if task is part of a workflow
      if (task.workflowId && this.workflows.has(task.workflowId)) {
        return this.executeWorkflowStep(task, context);
      }

      // Step 2: Decompose if needed
      await this.decomposer.decompose(task);

      // Step 3: Route to agents
      const routings = await this.router.route(task, context);

      // Step 4: Execute assignments
      if (routings.length === 1) {
        // Single assignment - execute directly
        return this.executeRouting(routings[0], context);
      } else if (routings.length > 1) {
        // Multiple assignments - execute in parallel and aggregate
        const results = await Promise.all(
          routings.map((r) => this.executeRouting(r, context))
        );
        return this.aggregator.aggregate(results);
      } else {
        // No assignments - try LLMAgent as fallback
        return this.executeWithLLMAgent(task, context);
      }
    } finally {
      endSpan(span);
    }
  }

  /**
   * Execute a single routing
   */
  private async executeRouting(routing: any, context: TaskContext): Promise<TaskResult> {
    const agent = this.registry.getAgent(routing.agentId);
    if (!agent) {
      throw new Error(`Agent ${routing.agentId} not found`);
    }

    return agent.executeTask(routing.task, {
      ...context,
      parentTaskId: context.taskId,
    });
  }

  /**
   * Execute with LLMAgent as fallback
   */
  private async executeWithLLMAgent(task: GodAgentTask, context: TaskContext): Promise<TaskResult> {
    const llmTask: LLMTask = {
      type: this.mapTaskTypeToLLMType(task.type),
      prompt: task.description,
      content: task.content,
      context: task.metadata,
    };

    return this.llmAgent.executeTask(llmTask, context);
  }

  /**
   * Map task type to LLM task type
   */
  private mapTaskTypeToLLMType(type: TaskType): any {
    const mapping: Record<TaskType, any> = {
      implement_feature: 'text_generation',
      fix_bug: 'text_generation',
      refactor_code: 'text_generation',
      optimize: 'analysis',
      code_review: 'analysis',
      architecture_review: 'analysis',
      security_audit: 'analysis',
      write_tests: 'text_generation',
      run_tests: 'text_generation',
      debug_test: 'analysis',
      analyze: 'analysis',
      summarize: 'summarization',
      explain: 'explanation',
      general: 'general',
      text_generation: 'text_generation',
      reasoning: 'reasoning',
    };
    return mapping[type] || 'general';
  }

  // ===========================================================================
  // Workflow Management
  // ===========================================================================

  /**
   * Create a workflow from a complex task
   */
  async createWorkflow(
    name: string,
    description: string,
    steps: Array<{ name: string; description: string; type?: TaskType }>
  ): Promise<WorkflowDefinition> {
    const workflow: WorkflowDefinition = {
      id: this.generateWorkflowId(),
      name,
      description,
      steps: steps.map((step, index) => ({
        id: `${index + 1}`,
        name: step.name,
        type: step.type || 'general',
        description: step.description,
        status: 'pending',
      })),
      createdAt: new Date(),
      status: 'pending',
    };

    this.workflows.set(workflow.id, workflow);
    return workflow;
  }

  /**
   * Execute a workflow
   */
  async executeWorkflow(workflowId: string, context?: TaskContext): Promise<any> {
    const workflow = this.workflows.get(workflowId);
    if (!workflow) {
      throw new Error(`Workflow ${workflowId} not found`);
    }

    workflow.status = 'in_progress';

    const results: any[] = [];
    for (const step of workflow.steps) {
      step.status = 'in_progress';

      const task: GodAgentTask = {
        id: this.generateTaskId(),
        type: step.type,
        description: step.description,
        priority: 'medium',
        workflowId: workflowId,
        createdAt: new Date(),
      };

      const result = await this.submitTask(task.description, {
        type: step.type,
        workflowId: workflowId,
        metadata: {
          ...context?.metadata,
          stepId: step.id,
        },
      });

      results.push(result);
      step.status = 'completed';
    }

    workflow.status = 'completed';
    return { workflowId, results };
  }

  /**
   * Execute a specific workflow step
   */
  private async executeWorkflowStep(task: GodAgentTask, context: TaskContext): Promise<any> {
    const workflow = this.workflows.get(task.workflowId!);
    if (!workflow) {
      throw new Error(`Workflow ${task.workflowId} not found`);
    }

    const step = workflow.steps.find((s) => s.id === context.metadata?.stepId);
    if (!step) {
      throw new Error(`Step ${context.metadata?.stepId} not found`);
    }

    step.status = 'in_progress';

    // Execute the step task
    const result = await this.routeAndExecute(task, context);

    step.status = 'completed';
    return result;
  }

  // ===========================================================================
  // Task Status Management
  // ===========================================================================

  /**
   * Update task status
   */
  private updateTaskStatus(
    taskId: TaskID,
    status: TaskStatus,
    message?: string,
    result?: any,
    error?: Error
  ): void {
    const update: TaskStatusUpdate = {
      taskId,
      status,
      message,
      result,
      error,
      timestamp: new Date(),
    };

    if (!this.taskStatus.has(taskId)) {
      this.taskStatus.set(taskId, []);
    }
    this.taskStatus.get(taskId)!.push(update);

    // Update task
    const task = this.tasks.get(taskId);
    if (task) {
      task.metadata = { ...task.metadata, lastStatus: status, lastUpdate: new Date() };
    }
  }

  /**
   * Get task status
   */
  getTaskStatus(taskId: TaskID): TaskStatusUpdate[] | undefined {
    return this.taskStatus.get(taskId);
  }

  /**
   * Get all tasks
   */
  getAllTasks(): GodAgentTask[] {
    return Array.from(this.tasks.values());
  }

  /**
   * Get task by ID
   */
  getTask(taskId: TaskID): GodAgentTask | undefined {
    return this.tasks.get(taskId);
  }

  /**
   * Get workflow by ID
   */
  getWorkflow(workflowId: string): WorkflowDefinition | undefined {
    return this.workflows.get(workflowId);
  }

  /**
   * Get all workflows
   */
  getAllWorkflows(): WorkflowDefinition[] {
    return Array.from(this.workflows.values());
  }

  // ===========================================================================
  // Agent Management
  // ===========================================================================

  /**
   * Register a new agent
   */
  registerAgent(agent: BaseAgent): AgentID {
    return this.registry.register(agent);
  }

  /**
   * Get an agent by ID
   */
  getAgent(agentId: AgentID): BaseAgent | undefined {
    return this.registry.getAgent(agentId);
  }

  /**
   * Get an agent by name
   */
  getAgentByName(name: string): BaseAgent | undefined {
    return this.registry.getAgentByName(name);
  }

  /**
   * Get all agents
   */
  getAllAgents(): BaseAgent[] {
    return this.registry.getAllAgents();
  }

  /**
   * Get agents by capability
   */
  getAgentsByCapability(capability: string): BaseAgent[] {
    return this.registry.getAgentsByCapability(capability);
  }

  // ===========================================================================
  // Configuration Management
  // ===========================================================================

  /**
   * Update configuration
   */
  updateConfig(partial: Partial<GodAgentConfig>): void {
    this.config = { ...this.config, ...partial };

    // Update router strategy
    this.router.setStrategy(this.config.routingStrategy);

    // Update decomposer strategy
    this.decomposer.setStrategy(this.config.decompositionStrategy);

    // Update LLMAgent if LLM config changed
    if (partial.llm) {
      this.llmAgent.setLLMConfig(partial.llm);
    }
  }

  /**
   * Get current configuration
   */
  getConfig(): GodAgentConfig {
    return { ...this.config };
  }

  // ===========================================================================
  // Statistics
  // ===========================================================================

  /**
   * Get GodAgent statistics
   */
  getStats() {
    return {
      tasks: {
        total: this.tasks.size,
        pending: this.getTasksByStatus('pending').length,
        inProgress: this.getTasksByStatus('in_progress').length,
        completed: this.getTasksByStatus('completed').length,
        failed: this.getTasksByStatus('failed').length,
      },
      workflows: {
        total: this.workflows.size,
        pending: this.getWorkflowsByStatus('pending').length,
        inProgress: this.getWorkflowsByStatus('in_progress').length,
        completed: this.getWorkflowsByStatus('completed').length,
      },
      agents: this.registry.getStats(),
    };
  }

  /**
   * Get tasks by status
   */
  private getTasksByStatus(status: TaskStatus): GodAgentTask[] {
    return Array.from(this.tasks.values()).filter((t) => 
      t.metadata?.lastStatus === status || (t.metadata?.lastStatus === undefined && status === 'pending')
    );
  }

  /**
   * Get workflows by status
   */
  private getWorkflowsByStatus(status: TaskStatus): WorkflowDefinition[] {
    return Array.from(this.workflows.values()).filter((w) => w.status === status);
  }

  // ===========================================================================
  // Utility Methods
  // ===========================================================================

  /**
   * Generate a unique task ID
   */
  private generateTaskId(): TaskID {
    return `${this.id}-task-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Generate a unique workflow ID
   */
  private generateWorkflowId(): string {
    return `${this.id}-workflow-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Get GodAgent info
   */
  getInfo() {
    return {
      ...super.getInfo(),
      config: {
        routingStrategy: this.config.routingStrategy,
        decompositionStrategy: this.config.decompositionStrategy,
      },
      stats: this.getStats(),
    };
  }
}

// =============================================================================
// Factory Function
// =============================================================================

/**
 * Create a GodAgent instance
 */
export function createGodAgent(config: Partial<GodAgentConfig> = {}): GodAgent {
  return new GodAgent(config);
}

// =============================================================================
// Default Export
// =============================================================================

export default GodAgent;
