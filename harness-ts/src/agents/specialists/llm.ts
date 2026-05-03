/**
 * LLMAgent
 * 
 * A specialist agent for LLM-powered tasks: text generation, analysis, reasoning.
 * This is the primary agent for general LLM interactions.
 */

import { type Model, type Message, complete, stream } from '@mariozechner/pi-ai';

import { BaseAgent } from '@/agents/base';
import { type TaskContext, type TaskResult, type ProviderName } from '@/configs/schemas';
import { getLLMConfig, type LLMConfig } from '@/configs/settings';
import { providerRegistry } from '@/providers/registry';
import { incrementMetric } from '@/core/monitoring/metrics';
import { startSpan, endSpan } from '@/core/monitoring/tracing';

// =============================================================================
// Task Types
// =============================================================================

/**
 * Types of tasks the LLMAgent can handle
 */
export type LLMTaskType = 
  | 'text_generation'
  | 'analysis'
  | 'summarization'
  | 'reasoning'
  | 'explanation'
  | 'question_answering'
  | 'code_generation'
  | 'translation'
  | 'general';

/**
 * LLMAgent task
 */
export interface LLMTask {
  type: LLMTaskType;
  prompt: string;
  content?: string;
  context?: Record<string, any>;
  options?: LLMOptions;
}

/**
 * LLMAgent options
 */
export interface LLMOptions {
  temperature?: number;
  maxTokens?: number;
  topP?: number;
  stop?: string[];
  stream?: boolean;
}

// =============================================================================
// Response Types
// =============================================================================



/**
 * Streaming LLMAgent response
 */
export interface LLMStreamResponse {
  chunks: string[];
  fullText: string;
  usage?: {
    inputTokens: number;
    outputTokens: number;
    totalTokens: number;
  };
  stopReason?: string;
}

// =============================================================================
// LLMAgent Class
// =============================================================================

/**
 * LLMAgent - The primary LLM-powered agent
 * 
 * Handles all general LLM tasks including:
 * - Text generation
 * - Analysis and reasoning
 * - Summarization
 * - Question answering
 * - Code generation
 * - Translation
 */
export class LLMAgent extends BaseAgent {
  // Provider and model configuration
  private provider: ProviderName;
  private modelId: string;
  private llmConfig: LLMConfig;

  // Default options
  private defaultOptions: LLMOptions = {
    temperature: 0.7,
    maxTokens: 4096,
  };

  constructor(name: string = 'LLMAgent') {
    super(name, {
      description: 'LLM-powered agent for text generation, analysis, reasoning, and general AI tasks',
      capabilities: [
        { name: 'llm', description: 'General LLM capabilities', level: 'expert', version: '1.0', dependsOn: [] },
        { name: 'reasoning', description: 'Logical reasoning and problem solving', level: 'expert', version: '1.0', dependsOn: [] },
        { name: 'text_generation', description: 'Generate human-like text', level: 'expert', version: '1.0', dependsOn: [] },
        { name: 'analysis', description: 'Analyze and interpret information', level: 'expert', version: '1.0', dependsOn: [] },
        { name: 'summarization', description: 'Condense information into summaries', level: 'expert', version: '1.0', dependsOn: [] },
        { name: 'question_answering', description: 'Answer questions based on information', level: 'expert', version: '1.0', dependsOn: [] },
        { name: 'code_generation', description: 'Generate and complete code', level: 'expert', version: '1.0', dependsOn: [] },
        { name: 'translation', description: 'Translate between languages', level: 'expert', version: '1.0', dependsOn: [] },
      ],
    });

    // Initialize with default configuration
    this.llmConfig = getLLMConfig();
    this.provider = this.llmConfig.provider;
    this.modelId = this.llmConfig.model;
  }

  // ===========================================================================
  // Configuration
  // ===========================================================================

  /**
   * Set the provider and model
   */
  setProvider(provider: ProviderName, modelId: string): void {
    this.provider = provider;
    this.modelId = modelId;
    this.llmConfig = {
      ...this.llmConfig,
      provider,
      model: modelId,
    };
  }

  /**
   * Set the LLM configuration
   */
  setLLMConfig(config: Partial<LLMConfig>): void {
    this.llmConfig = { ...this.llmConfig, ...config };
    this.provider = this.llmConfig.provider;
    this.modelId = this.llmConfig.model;
  }

  /**
   * Get the current LLM configuration
   */
  getLLMConfig(): LLMConfig {
    return { ...this.llmConfig };
  }

  /**
   * Set default options
   */
  setDefaultOptions(options: LLMOptions): void {
    this.defaultOptions = { ...this.defaultOptions, ...options };
  }

  // ===========================================================================
  // Base Agent Implementation
  // ===========================================================================

  getSystemPrompt(): string {
    return `You are an AI assistant specialized in text generation, analysis, reasoning, and general AI tasks.
    You are part of the Harness Agentic Framework multi-agent system.
    
    Guidelines:
    - Be concise and accurate in your responses
    - Think step by step before answering complex questions
    - When asked to perform analysis, provide structured and well-reasoned responses
    - When generating code, include comments and follow best practices
    - When summarizing, capture the key points without losing important details
    - Always consider the context and previous messages in the conversation
    
    Your capabilities include:
    - Text generation and creative writing
    - Logical reasoning and problem solving
    - Information analysis and interpretation
    - Summarization and condensation
    - Question answering
    - Code generation and completion
    - Translation between languages`;
  }

  getModel(): Model<any> {
    return providerRegistry.getModel(this.provider, this.modelId);
  }

  getTools(): any[] {
    // LLM agent doesn't have external tools - it IS the tool
    return [];
  }

  // ===========================================================================
  // Task Execution
  // ===========================================================================

  /**
   * Execute an LLM task
   */
  protected async _executeTask(task: LLMTask, context: TaskContext): Promise<any> {
    const span = startSpan(`${this.name}.executeTask`, { taskId: context.taskId, taskType: task.type });

    try {
      const model = this.getModel();
      const options = { ...this.defaultOptions, ...task.options };
      
      // Build messages
      const messages = this.buildMessages(task, context);
      
      // Call LLM
      const response = await this.callLLM(model, messages, options);
      
      incrementMetric('llm.tasks.completed', 1, { 
        agent: this.name, 
        taskType: task.type,
        provider: this.provider,
        model: this.modelId
      });
      
      return response;
    } finally {
      endSpan(span);
    }
  }

  /**
   * Build messages for the LLM
   */
  private buildMessages(task: LLMTask, context: TaskContext): Message[] {
    const messages: Message[] = [];

    // Add system prompt
    messages.push({
      role: 'user' as const,
      content: this.getSystemPrompt(),
      timestamp: Date.now(),
    });

    // Add context if available
    if (context.metadata?.previousMessages) {
      for (const msg of context.metadata.previousMessages) {
        messages.push({
          role: msg.role || 'user',
          content: msg.content,
          timestamp: msg.timestamp || Date.now(),
        });
      }
    }

    // Add task-specific context
    if (task.context) {
      messages.push({
        role: 'user' as const,
        content: `Context: ${JSON.stringify(task.context)}`,
        timestamp: Date.now(),
      });
    }

    // Add the main prompt
    messages.push({
      role: 'user',
      content: this.formatPrompt(task),
      timestamp: Date.now(),
    });

    return messages;
  }

  /**
   * Format the prompt based on task type
   */
  private formatPrompt(task: LLMTask): string {
    const prefixes: Record<LLMTaskType, string> = {
      text_generation: 'Generate the following text:',
      analysis: 'Analyze the following:',
      summarization: 'Summarize the following:',
      reasoning: 'Reason through the following problem:',
      explanation: 'Explain the following:',
      question_answering: 'Answer the following question:',
      code_generation: 'Write code for the following:',
      translation: 'Translate the following:',
      general: '',
    };

    const prefix = prefixes[task.type] || '';
    const content = task.content || task.prompt;
    
    return prefix ? `${prefix}\n\n${content}` : content;
  }

  /**
   * Call the LLM
   */
  private async callLLM(
    model: Model<any>,
    messages: Message[],
    options: LLMOptions
  ): Promise<any> {
    const span = startSpan(`${this.name}.callLLM`, {
      provider: this.provider,
      model: this.modelId
    });

    try {
      const apiKey = providerRegistry.getApiKey(this.provider);
      const baseUrl = providerRegistry.getBaseUrl(this.provider);

      // Build complete options
      const completeOptions: any = {
        apiKey,
        baseUrl,
        temperature: options.temperature,
        maxTokens: options.maxTokens,
        topP: options.topP,
        stop: options.stop,
      };

      // Call LLM
      const response = await complete(model, { messages }, completeOptions);
      
      incrementMetric('llm.calls.completed', 1, {
        provider: this.provider,
        model: this.modelId
      });
      
      if (response.usage) {
        incrementMetric('llm.tokens.input', response.usage.input, {
          provider: this.provider,
          model: this.modelId
        });
        incrementMetric('llm.tokens.output', response.usage.output, {
          provider: this.provider,
          model: this.modelId
        });
      }
      
      return response;
    } finally {
      endSpan(span);
    }
  }

  /**
   * Format the LLM response
 =======
  // ======================================================================================================================================================
  // Convenience Methods
  // ===========================================================================

  /**
   * Generate text
   */
  async generateText(prompt: string, options?: LLMOptions): Promise<TaskResult> {
    const context: TaskContext = { taskId: this.generateTaskId() };
    const task: LLMTask = { type: 'text_generation', prompt, options };
    return this.executeTask(task, context);
  }

  /**
   * Analyze content
   */
  async analyze(content: string, prompt?: string, options?: LLMOptions): Promise<TaskResult> {
    const context: TaskContext = { taskId: this.generateTaskId() };
    const task: LLMTask = {
      type: 'analysis',
      prompt: prompt || 'Analyze this content',
      content,
      options
    };
    return this.executeTask(task, context);
  }

  /**
   * Summarize content
   */
  async summarize(content: string, prompt?: string, options?: LLMOptions): Promise<TaskResult> {
    const context: TaskContext = { taskId: this.generateTaskId() };
    const task: LLMTask = {
      type: 'summarization',
      prompt: prompt || 'Summarize this content',
      content,
      options
    };
    return this.executeTask(task, context);
  }

  /**
   * Answer a question
   */
  async answerQuestion(question: string, content?: string, options?: LLMOptions): Promise<TaskResult> {
    const contextObj: TaskContext = { taskId: this.generateTaskId() };
    const task: LLMTask = {
      type: 'question_answering',
      prompt: question,
      content,
      options
    };
    return this.executeTask(task, contextObj);
  }

  /**
   * Generate code
   */
  async generateCode(prompt: string, language?: string, options?: LLMOptions): Promise<TaskResult> {
    const context: TaskContext = { taskId: this.generateTaskId() };
    const fullPrompt = language ? `${prompt}\n\nLanguage: ${language}` : prompt;
    const task: LLMTask = {
      type: 'code_generation',
      prompt: fullPrompt,
      options: { ...options, maxTokens: options?.maxTokens || 8192 }
    };
    return this.executeTask(task, context);
  }

  /**
   * Stream a response
   */
  async *streamResponse(task: LLMTask, context: TaskContext): AsyncGenerator<string> {
    const model = this.getModel();
    const messages = this.buildMessages(task, context);
    const options = { ...this.defaultOptions, ...task.options };

    const apiKey = providerRegistry.getApiKey(this.provider);
    const baseUrl = providerRegistry.getBaseUrl(this.provider);

    const completeOptions: any = {
      apiKey,
      baseUrl,
      temperature: options.temperature,
      maxTokens: options.maxTokens,
    };

    for await (const event of stream(model, { messages }, completeOptions)) {
      if (event.type === 'text_delta') {
        yield event.delta;
      }
    }
  }

  // ===========================================================================
  // Utility Methods
  // ===========================================================================

  /**
   * Generate a unique task ID
   */
  private generateTaskId(): string {
    return `${this.id}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Get agent info with LLM-specific details
   */
  getInfo() {
    return {
      ...super.getInfo(),
      provider: this.provider,
      model: this.modelId,
    };
  }
}

// =============================================================================
// Factory Function
// =============================================================================

/**
 * Create an LLMAgent with the specified configuration
 */
export function createLLMAgent(
  name: string = 'LLMAgent',
  provider: ProviderName = 'ollama',
  modelId: string = 'llama-3.1-8b'
): LLMAgent {
  const agent = new LLMAgent(name);
  agent.setProvider(provider, modelId);
  return agent;
}

// =============================================================================
// Default Export
// =============================================================================

export default LLMAgent;
