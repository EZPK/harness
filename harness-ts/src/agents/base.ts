/**
 * Base Agent
 * 
 * The foundational agent class that all other agents inherit from.
 * Uses pi-mono's @mariozechner/pi-agent-core as the underlying agent runtime.
 */

import {
  Agent as PiAgent,
  type AgentMessage,
  type AgentContext,
  type AgentLoopConfig,
  agentLoop,
} from '@mariozechner/pi-agent-core';
import { type Model as PiModel, type Message } from '@mariozechner/pi-ai';
import { v4 as uuidv4 } from 'uuid';

import {
  type AgentID,
  type TaskID,
  type AgentState,
  type AgentConfig,
  type AgentStatus,
  type TaskContext,
  type TaskResult,
  AgentStateSchema,
} from '../configs/schemas';

import { incrementMetric } from '@/core/monitoring/metrics';
import { startSpan as startBasicSpan, endSpan as endBasicSpan } from '@/core/monitoring/tracing';

// =============================================================================
// Type Definitions
// =============================================================================

/**
 * Agent capability with metadata
 */
export interface AgentCapabilityInfo {
  name: string;
  description?: string;
  level: string;
  version: string;
  dependsOn: string[];
}

/**
 * Task assignment for an agent
 */
export interface TaskAssignment {
  taskId: TaskID;
  agentId: AgentID;
  task: any;
  context: TaskContext;
  priority: number;
  assignedAt: Date;
}

/**
 * Agent error with context
 */
export class AgentError extends Error {
  constructor(
    message: string,
    public readonly agentId: AgentID,
    public readonly taskId?: TaskID,
    public readonly originalError?: Error
  ) {
    super(message);
    this.name = 'AgentError';
  }
}

/**
 * Task error with context
 */
export class TaskError extends Error {
  constructor(
    message: string,
    public readonly taskId: TaskID,
    public readonly agentId: AgentID,
    public readonly originalError?: Error
  ) {
    super(message);
    this.name = 'TaskError';
  }
}

// =============================================================================
// Message Type Extensions
// =============================================================================

/**
 * Extend AgentMessage with Harness-specific types
 */
declare module '@mariozechner/pi-agent-core' {
  interface CustomAgentMessages {
    system: { role: 'system'; content: string; timestamp: number };
    notification: { role: 'notification'; content: string; timestamp: number };
  }
}

// =============================================================================
// Type Aliases for pi-ai
// =============================================================================

/** Model type that works with pi-ai */
export type Model = PiModel<any>;

/** Message type that works with pi-ai */
export type LLMMessage = Message;

// Re-export types for convenience
export type { TaskContext, TaskResult };

// =============================================================================
// Base Agent Class
// =============================================================================

/**
 * Base agent class that all specialist agents inherit from.
 * Wraps pi-agent-core's Agent with Harness-specific functionality.
 */
export abstract class BaseAgent {
  // Identification
  readonly id: AgentID;
  readonly name: string;
  description: string;

  // State management
  state: AgentState = AgentStateSchema.parse('uninitialized');
  status: AgentStatus;

  // Capabilities
  capabilities: string[] = [];
  capabilityInfo: Map<string, AgentCapabilityInfo> = new Map();

  // Internal pi-agent-core agent
  protected piAgent: PiAgent | null = null;
  protected llmModel: Model | null = null;

  // Task tracking
  private activeTasks: Map<TaskID, TaskAssignment> = new Map();
  private taskCount: number = 0;
  private errorCount: number = 0;

  constructor(name: string, config: Partial<AgentConfig> = {}) {
    this.id = uuidv4();
    this.name = name;
    this.description = config.description || '';

    // Initialize capabilities
    if (config.capabilities) {
      for (const cap of config.capabilities) {
        this.capabilities.push(cap.name);
        this.capabilityInfo.set(cap.name, {
          name: cap.name,
          description: cap.description,
          level: cap.level,
          version: cap.version,
          dependsOn: cap.dependsOn,
        });
      }
    }

    // Initialize status
    this.status = {
      state: this.state,
      message: `Agent ${name} created`,
      timestamp: new Date(),
      taskCount: 0,
      errorCount: 0,
      activeTasks: 0,
    };
  }

  // ===========================================================================
  // Lifecycle Methods
  // ===========================================================================

  /**
   * Initialize the agent
   */
  async initialize(): Promise<void> {
    const span = startBasicSpan(`${this.name}.initialize`);

    try {
      this.state = AgentStateSchema.parse('initializing');
      this.updateStatus('Initializing agent...');

      // Initialize the underlying pi-agent-core Agent
      this.piAgent = new PiAgent({
        initialState: {
          systemPrompt: this.getSystemPrompt(),
          model: this.getModel(),
          messages: [],
          tools: this.getTools(),
          thinkingLevel: this.getThinkingLevel(),
        },
        convertToLlm: this.convertToLlm.bind(this),
        transformContext: this.transformContext.bind(this),
        toolExecution: 'parallel',
      });

      // Subscribe to agent events
      this.setupEventSubscriptions();

      this.state = AgentStateSchema.parse('idle');
      this.updateStatus('Agent ready');

      incrementMetric('agents.initialized', 1, { agent: this.name });
    } catch (error) {
      this.state = AgentStateSchema.parse('error');
      this.updateStatus(`Initialization failed: ${error}`);
      throw new AgentError(`Failed to initialize agent ${this.name}`, this.id, undefined, error as Error);
    } finally {
      endBasicSpan(span);
    }
  }

  /**
   * Setup event subscriptions for the pi-agent
   */
  private setupEventSubscriptions(): void {
    if (!this.piAgent) return;

    this.piAgent.subscribe((event) => {
      switch (event.type) {
        case 'agent_start':
          this.handleAgentStart(event);
          break;
        case 'agent_end':
          this.handleAgentEnd(event);
          break;
        case 'turn_start':
          this.handleTurnStart(event);
          break;
        case 'turn_end':
          this.handleTurnEnd(event);
          break;
        case 'message_start':
          this.handleMessageStart(event);
          break;
        case 'message_end':
          this.handleMessageEnd(event);
          break;
        case 'tool_execution_start':
          this.handleToolExecutionStart(event);
          break;
        case 'tool_execution_end':
          this.handleToolExecutionEnd(event);
          break;
      }
    });
  }

  /**
   * Shutdown the agent
   */
  async shutdown(): Promise<void> {
    const span = startBasicSpan(`${this.name}.shutdown`);

    try {
      this.state = AgentStateSchema.parse('shutdown');
      this.updateStatus('Shutting down agent...');

      // Abort any active tasks
      if (this.piAgent) {
        this.piAgent.abort();
      }

      // Clear active tasks
      this.activeTasks.clear();

      this.state = AgentStateSchema.parse('shutdown');
      this.updateStatus('Agent shut down');

      incrementMetric('agents.shutdown', 1, { agent: this.name });
    } finally {
      endBasicSpan(span);
    }
  }

  // ===========================================================================
  // Abstract Methods (must be implemented by subclasses)
  // ===========================================================================

  /**
   * Get the system prompt for this agent
   */
  abstract getSystemPrompt(): string;

  /**
   * Get the LLM model for this agent
   */
  abstract getModel(): Model;

  /**
   * Get the tools available to this agent
   */
  abstract getTools(): any[];

  /**
   * Execute a task (internal implementation)
   */
  protected abstract _executeTask(task: any, context: TaskContext): Promise<any>;

  // ===========================================================================
  // Task Execution
  // ===========================================================================

  /**
   * Execute a task
   */
  async executeTask(task: any, context: TaskContext): Promise<TaskResult> {
    const span = startBasicSpan(`${this.name}.executeTask`, { taskId: context.taskId });

    try {
      // Validate state
      if (this.state !== 'idle' && this.state !== 'busy') {
        throw new AgentError(
          `Agent ${this.name} cannot execute tasks in state: ${this.state}`,
          this.id,
          context.taskId
        );
      }

      // Track task
      const assignment: TaskAssignment = {
        taskId: context.taskId,
        agentId: this.id,
        task,
        context,
        priority: 0,
        assignedAt: new Date(),
      };
      this.activeTasks.set(context.taskId, assignment);
      this.updateTaskCounts();

      this.state = AgentStateSchema.parse('busy');
      this.updateStatus(`Executing task: ${context.taskId}`);

      // Execute the task
      const result = await this._executeTask(task, context);

      // Success
      this.taskCount++;
      incrementMetric('agents.tasks.completed', 1, { agent: this.name });

      return {
        taskId: context.taskId,
        result,
        timestamp: new Date(),
      };
    } catch (error) {
      this.errorCount++;
      this.state = AgentStateSchema.parse('error');
      this.updateStatus(`Error executing task: ${error}`);

      incrementMetric('agents.tasks.failed', 1, { agent: this.name });

      return {
        taskId: context.taskId,
        error: error as Error,
        timestamp: new Date(),
      };
    } finally {
      // Cleanup
      this.activeTasks.delete(context.taskId);
      this.updateTaskCounts();

      if (this.activeTasks.size === 0) {
        this.state = AgentStateSchema.parse('idle');
        this.updateStatus('Task completed');
      }

      endBasicSpan(span);
    }
  }

  /**
   * Execute multiple tasks in parallel
   */
  async executeTasksParallel(tasks: Array<{ task: any; context: TaskContext }>): Promise<TaskResult[]> {
    return Promise.all(tasks.map(({ task, context }) => this.executeTask(task, context)));
  }

  /**
   * Execute multiple tasks sequentially
   */
  async executeTasksSequential(tasks: Array<{ task: any; context: TaskContext }>): Promise<TaskResult[]> {
    const results: TaskResult[] = [];
    for (const { task, context } of tasks) {
      const result = await this.executeTask(task, context);
      results.push(result);
    }
    return results;
  }

  // ===========================================================================
  // Capability Management
  // ===========================================================================

  /**
   * Add a capability to this agent
   */
  addCapability(name: string, info: Partial<AgentCapabilityInfo> = {}): void {
    if (!this.capabilities.includes(name)) {
      this.capabilities.push(name);
    }
    this.capabilityInfo.set(name, {
      ...info,
      name,
      level: info.level || 'standard',
      version: info.version || '1.0',
      dependsOn: info.dependsOn || [],
    });
  }

  /**
   * Remove a capability from this agent
   */
  removeCapability(name: string): void {
    const index = this.capabilities.indexOf(name);
    if (index !== -1) {
      this.capabilities.splice(index, 1);
    }
    this.capabilityInfo.delete(name);
  }

  /**
   * Check if this agent has a capability
   */
  hasCapability(capability: string): boolean {
    return this.capabilities.includes(capability);
  }

  /**
   * Get capability level
   */
  getCapabilityLevel(capability: string): string | undefined {
    const info = this.capabilityInfo.get(capability);
    return info?.level;
  }

  /**
   * Get all capabilities with info
   */
  getCapabilities(): AgentCapabilityInfo[] {
    return Array.from(this.capabilityInfo.values());
  }

  // ===========================================================================
  // Message Handling
  // ===========================================================================

  /**
   * Send a message to this agent and get a response
   */
  async sendMessage(message: string, _context: TaskContext): Promise<string> {
    if (!this.piAgent) {
      throw new AgentError('Agent not initialized', this.id);
    }

    // Add message to context
    const agentContext: AgentContext = {
      systemPrompt: this.getSystemPrompt(),
      messages: [
        ...(this.piAgent.state.messages || []),
        { role: 'user', content: message, timestamp: Date.now() },
      ],
      tools: this.getTools(),
    };

    // Get response using agentLoop
    const config: AgentLoopConfig = {
      model: this.getModel(),
      convertToLlm: this.convertToLlm.bind(this),
      toolExecution: 'parallel',
    };

    let fullResponse = '';
    for await (const event of agentLoop([agentContext.messages[agentContext.messages.length - 1]], agentContext, config)) {
      if (event.type === 'message_update' && event.assistantMessageEvent.type === 'text_delta') {
        fullResponse += event.assistantMessageEvent.delta;
      }
    }

    return fullResponse;
  }

  /**
   * Convert Harness messages to LLM format
   */
  protected convertToLlm(messages: AgentMessage[]): LLMMessage[] {
    return messages
      .filter((m) => ['user', 'assistant', 'toolResult', 'system'].includes(m.role))
      .map((m) => ({
        role: m.role as 'user' | 'assistant' | 'toolResult' | 'system',
        content: m.content,
        timestamp: m.timestamp,
      })) as LLMMessage[];
  }

  /**
   * Transform context before sending to LLM
   */
  protected async transformContext(messages: AgentMessage[]): Promise<AgentMessage[]> {
    // Default: no transformation
    return messages;
  }

  // ===========================================================================
  // Thinking Level
  // ===========================================================================

  /**
   * Get the thinking level for this agent
   */
  protected getThinkingLevel(): 'off' | 'minimal' | 'low' | 'medium' | 'high' | 'xhigh' {
    return 'off';
  }

  // ===========================================================================
  // Task Management
  // ===========================================================================

  /**
   * Get active tasks
   */
  getActiveTasks(): TaskAssignment[] {
    return Array.from(this.activeTasks.values());
  }

  /**
   * Get task count
   */
  getTaskCount(): number {
    return this.taskCount;
  }

  /**
   * Get error count
   */
  getErrorCount(): number {
    return this.errorCount;
  }

  /**
   * Update task counts in status
   */
  private updateTaskCounts(): void {
    this.status = {
      ...this.status,
      taskCount: this.taskCount,
      errorCount: this.errorCount,
      activeTasks: this.activeTasks.size,
    };
  }

  // ===========================================================================
  // Status Management
  // ===========================================================================

  /**
   * Update agent status
   */
  protected updateStatus(message: string): void {
    this.status = {
      ...this.status,
      state: this.state,
      message: message,
      timestamp: new Date(),
    };
  }

  /**
   * Get current status
   */
  getStatus(): AgentStatus {
    return { ...this.status };
  }

  // ===========================================================================
  // Event Handlers
  // ===========================================================================

  protected handleAgentStart(_event: any): void {
    incrementMetric('agents.events.start', 1, { agent: this.name });
  }

  protected handleAgentEnd(_event: any): void {
    incrementMetric('agents.events.end', 1, { agent: this.name });
  }

  protected handleTurnStart(_event: any): void {
    incrementMetric('agents.events.turn_start', 1, { agent: this.name });
  }

  protected handleTurnEnd(_event: any): void {
    incrementMetric('agents.events.turn_end', 1, { agent: this.name });
  }

  protected handleMessageStart(_event: any): void {
    incrementMetric('agents.events.message_start', 1, { agent: this.name });
  }

  protected handleMessageEnd(_event: any): void {
    incrementMetric('agents.events.message_end', 1, { agent: this.name });
  }

  protected handleToolExecutionStart(event: any): void {
    incrementMetric('agents.events.tool_start', 1, { agent: this.name, tool: event.toolName });
  }

  protected handleToolExecutionEnd(event: any): void {
    incrementMetric('agents.events.tool_end', 1, { agent: this.name, tool: event.toolName });
  }

  // ===========================================================================
  // Utility Methods
  // ===========================================================================

  /**
   * Check if agent is available to handle tasks
   */
  isAvailable(): boolean {
    return this.state === 'idle' || this.state === 'busy';
  }

  /**
   * Check if agent is currently busy
   */
  isBusy(): boolean {
    return this.state === 'busy';
  }

  /**
   * Get agent info
   */
  getInfo() {
    return {
      id: this.id,
      name: this.name,
      description: this.description,
      state: this.state,
      capabilities: this.capabilities,
      taskCount: this.taskCount,
      errorCount: this.errorCount,
      activeTasks: this.activeTasks.size,
    };
  }
}
