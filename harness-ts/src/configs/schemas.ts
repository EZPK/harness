/**
 * Configuration Schemas
 * 
 * Defines all configuration types using zod for runtime validation.
 * This replaces the Python pydantic schemas.
 */

import { z } from 'zod';

// =============================================================================
// Basic Types
// =============================================================================

/** Unique task identifier */
export type TaskID = string;

/** Unique agent identifier */
export type AgentID = string;

// =============================================================================
// Agent Capabilities
// =============================================================================

export const CapabilityLevelSchema = z.enum([
  'basic',
  'standard',
  'advanced',
  'expert',
]);

export type CapabilityLevel = z.infer<typeof CapabilityLevelSchema>;

export const AgentCapabilitySchema = z.object({
  name: z.string().describe('Name of the capability'),
  description: z.string().describe('Description of what the capability enables'),
  level: CapabilityLevelSchema.default('standard'),
  version: z.string().default('1.0'),
  dependsOn: z.array(z.string()).default([]).describe('Dependencies for this capability'),
});

export type AgentCapability = z.infer<typeof AgentCapabilitySchema>;

// =============================================================================
// Agent Configuration
// =============================================================================

export const AgentStateSchema = z.enum([
  'uninitialized',
  'initializing',
  'idle',
  'busy',
  'paused',
  'error',
  'shutdown',
  'checkpointing',
  'restoring',
]);

export type AgentState = z.infer<typeof AgentStateSchema>;

/**
 * Agent status information
 */
export interface AgentStatus {
  state: AgentState;
  message: string;
  timestamp: Date;
  taskCount: number;
  errorCount: number;
  activeTasks: number;
}

export const AgentRuntimeConfigSchema = z.object({
  timeout: z.number().int().positive().default(60).describe('Task timeout in seconds'),
  maxRetries: z.number().int().nonnegative().default(3).describe('Maximum retry attempts'),
  maxConcurrentTasks: z.number().int().positive().default(5).describe('Maximum concurrent tasks'),
});

export type AgentRuntimeConfig = z.infer<typeof AgentRuntimeConfigSchema>;

export const AgentConfigSchema = z.object({
  id: z.string().describe('Unique agent identifier'),
  name: z.string().describe('Human-readable agent name'),
  description: z.string().default('').describe('Agent description'),
  capabilities: z.array(AgentCapabilitySchema).default([]),
  runtime: AgentRuntimeConfigSchema.default({}),
});

export type AgentConfig = z.infer<typeof AgentConfigSchema>;

// =============================================================================
// LLM Configuration
// =============================================================================

export const ProviderNameSchema = z.enum([
  'openai',
  'anthropic',
  'google',
  'mistral',
  'ollama',
  'local',
  'azure',
  'groq',
  'cerebras',
  'deepseek',
]);

export type ProviderName = z.infer<typeof ProviderNameSchema>;

export const LLMConfigSchema = z.object({
  provider: ProviderNameSchema.default('ollama').describe('LLM provider name'),
  model: z.string().default('llama-3.1-8b').describe('Model identifier'),
  apiKey: z.string().optional().describe('API key for the provider'),
  baseUrl: z.string().url().optional().describe('Base URL for the provider API'),
  temperature: z.number().min(0).max(2).default(0.7).describe('Sampling temperature'),
  maxTokens: z.number().int().positive().optional().describe('Maximum tokens to generate'),
  timeout: z.number().int().positive().default(120).describe('Request timeout in seconds'),
});

export type LLMConfig = z.infer<typeof LLMConfigSchema>;

// =============================================================================
// Routing Strategies
// =============================================================================

export const RoutingStrategySchema = z.enum([
  'keyword',
  'capability',
  'hybrid',
  'round_robin',
  'priority',
  'learned',
]);

export type RoutingStrategy = z.infer<typeof RoutingStrategySchema>;

export const DecompositionStrategySchema = z.enum([
  'template',
  'semantic',
  'hybrid',
  'recursive',
]);

export type DecompositionStrategy = z.infer<typeof DecompositionStrategySchema>;

// =============================================================================
// Task Types
// =============================================================================

export const TaskTypeSchema = z.enum([
  // Development tasks
  'implement_feature',
  'fix_bug',
  'refactor_code',
  'optimize',
  
  // Review tasks
  'code_review',
  'architecture_review',
  'security_audit',
  
  // Testing tasks
  'write_tests',
  'run_tests',
  'debug_test',
  
  // Analysis tasks
  'analyze',
  'summarize',
  'explain',
  
  // Generic
  'general',
  'text_generation',
  'reasoning',
]);

export type TaskType = z.infer<typeof TaskTypeSchema>;

// =============================================================================
// Task Priority
// ============================================================================= 

export const TaskPrioritySchema = z.enum([
  'low',
  'medium',
  'high',
  'critical',
]);

export type TaskPriority = z.infer<typeof TaskPrioritySchema>;

// =============================================================================
// Task Status
// =============================================================================

export const TaskStatusSchema = z.enum([
  'pending',
  'assigned',
  'in_progress',
  'completed',
  'failed',
  'cancelled',
  'paused',
]);

export type TaskStatus = z.infer<typeof TaskStatusSchema>;

// =============================================================================
// Task Context and Result Types
// =============================================================================

/**
 * Task context for execution
 */
export interface TaskContext {
  taskId: TaskID;
  userId?: string;
  sessionId?: string;
  parentTaskId?: TaskID;
  workflowId?: string;
  metadata?: Record<string, any>;
}

/**
 * Result of a task execution
 */
export interface TaskResult<T = any> {
  taskId: TaskID;
  result?: T;
  error?: Error;
  metadata?: Record<string, any>;
  timestamp: Date;
}

// =============================================================================
// Workflow Types
// =============================================================================

export const WorkflowStepTypeSchema = z.enum([
  'sequential',
  'parallel',
  'conditional',
  'loop',
]);

export type WorkflowStepType = z.infer<typeof WorkflowStepTypeSchema>;

// =============================================================================
// GodAgent Configuration
// =============================================================================

export const GodAgentConfigSchema = z.object({
  // Routing configuration
  routingStrategy: RoutingStrategySchema.default('hybrid').describe(
    'Strategy for routing tasks to agents'
  ),
  
  // Decomposition configuration
  decompositionStrategy: DecompositionStrategySchema.default('hybrid').describe(
    'Strategy for decomposing complex tasks'
  ),
  
  // Agent configurations (keyed by agent name)
  agents: z.record(AgentConfigSchema).default({}),
  
  // Default LLM configuration
  llm: LLMConfigSchema.default({
    provider: 'ollama',
    model: 'llama-3.1-8b',
    temperature: 0.7,
    timeout: 120,
  }),
  
  // Monitoring configuration
  monitoring: z.object({
    enabled: z.boolean().default(true),
    metricsPort: z.number().int().positive().default(9090),
    tracingEnabled: z.boolean().default(false),
  }).default({}),
  
  // Sandbox configuration
  sandbox: z.object({
    enabled: z.boolean().default(true),
    timeout: z.number().int().positive().default(30),
    maxMemory: z.number().int().positive().default(1024), // MB
  }).default({}),
});

export type GodAgentConfig = z.infer<typeof GodAgentConfigSchema>;

// =============================================================================
// Export validation functions
// =============================================================================

export function validateAgentConfig(config: unknown): AgentConfig {
  return AgentConfigSchema.parse(config);
}

export function validateLLMConfig(config: unknown): LLMConfig {
  return LLMConfigSchema.parse(config);
}

export function validateGodAgentConfig(config: unknown): GodAgentConfig {
  return GodAgentConfigSchema.parse(config);
}

// =============================================================================
// Default configurations
// =============================================================================

export const DEFAULT_LLM_CONFIG: LLMConfig = {
  provider: 'ollama',
  model: 'llama-3.1-8b',
  temperature: 0.7,
  timeout: 120,
};

export const DEFAULT_GOD_AGENT_CONFIG: GodAgentConfig = {
  routingStrategy: 'hybrid',
  decompositionStrategy: 'hybrid',
  agents: {},
  llm: DEFAULT_LLM_CONFIG,
  monitoring: {
    enabled: true,
    metricsPort: 9090,
    tracingEnabled: false,
  },
  sandbox: {
    enabled: true,
    timeout: 30,
    maxMemory: 1024,
  },
};
