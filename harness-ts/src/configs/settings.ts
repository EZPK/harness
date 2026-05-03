/**
 * Settings Management
 * 
 * Loads and manages configuration from various sources:
 * - Environment variables (via dotenv)
 * - Configuration files
 * - Command-line arguments
 */

import { config } from 'dotenv';
import { readFileSync } from 'fs';
import { resolve } from 'path';
import {
  GodAgentConfigSchema,
  LLMConfigSchema,
  type GodAgentConfig,
  type LLMConfig,
  DEFAULT_GOD_AGENT_CONFIG,
  DEFAULT_LLM_CONFIG,
} from './schemas';

// Load environment variables from .env file
config();

// =============================================================================
// Environment Variable Mapping
// =============================================================================

const ENV_MAPPINGS = {
  // LLM Configuration
  llm: {
    provider: 'DEFAULT_LLM_PROVIDER',
    model: 'DEFAULT_LLM_MODEL',
    apiKey: (provider: string) => `${provider.toUpperCase()}_API_KEY`,
    baseUrl: (provider: string) => `${provider.toUpperCase()}_BASE_URL`,
    temperature: 'DEFAULT_LLM_TEMPERATURE',
    maxTokens: 'DEFAULT_LLM_MAX_TOKENS',
    timeout: 'DEFAULT_LLM_TIMEOUT',
  },
  
  // GodAgent Configuration
  godAgent: {
    routingStrategy: 'ROUTING_STRATEGY',
    decompositionStrategy: 'DECOMPOSITION_STRATEGY',
  },
  
  // Monitoring
  monitoring: {
    enabled: 'MONITORING_ENABLED',
    metricsPort: 'METRICS_PORT',
    tracingEnabled: 'TRACING_ENABLED',
  },
  
  // Sandbox
  sandbox: {
    enabled: 'SANDBOX_ENABLED',
    timeout: 'SANDBOX_TIMEOUT',
    maxMemory: 'SANDBOX_MAX_MEMORY',
  },
} as const;

// =============================================================================
// Configuration Loading
// =============================================================================

/**
 * Load LLM configuration from environment variables
 */
export function loadLLMConfigFromEnv(): Partial<LLMConfig> {
  const result: Partial<LLMConfig> = {};
  
  // Provider
  if (process.env.DEFAULT_LLM_PROVIDER) {
    result.provider = process.env.DEFAULT_LLM_PROVIDER as any;
  }
  
  // Model
  if (process.env.DEFAULT_LLM_MODEL) {
    result.model = process.env.DEFAULT_LLM_MODEL;
  }
  
  // Temperature
  if (process.env.DEFAULT_LLM_TEMPERATURE) {
    result.temperature = parseFloat(process.env.DEFAULT_LLM_TEMPERATURE);
  }
  
  // Timeout
  if (process.env.DEFAULT_LLM_TIMEOUT) {
    result.timeout = parseInt(process.env.DEFAULT_LLM_TIMEOUT, 10);
  }
  
  // Max tokens
  if (process.env.DEFAULT_LLM_MAX_TOKENS) {
    result.maxTokens = parseInt(process.env.DEFAULT_LLM_MAX_TOKENS, 10);
  }
  
  // API key and base URL for specific provider
  const provider = result.provider || DEFAULT_LLM_CONFIG.provider;
  const apiKeyEnv = ENV_MAPPINGS.llm.apiKey(provider as string);
  const baseUrlEnv = ENV_MAPPINGS.llm.baseUrl(provider as string);
  
  if (process.env[apiKeyEnv]) {
    result.apiKey = process.env[apiKeyEnv];
  }
  
  if (process.env[baseUrlEnv]) {
    result.baseUrl = process.env[baseUrlEnv];
  }
  
  return result;
}

/**
 * Load GodAgent configuration from environment variables
 */
export function loadGodAgentConfigFromEnv(): any {
  const result: any = {};
  
  // Routing strategy
  if (process.env.ROUTING_STRATEGY) {
    result.routingStrategy = process.env.ROUTING_STRATEGY as any;
  }
  
  // Decomposition strategy
  if (process.env.DECOMPOSITION_STRATEGY) {
    result.decompositionStrategy = process.env.DECOMPOSITION_STRATEGY as any;
  }
  
  // LLM config
  result.llm = loadLLMConfigFromEnv();
  
  // Monitoring
  if (process.env.MONITORING_ENABLED !== undefined) {
    result.monitoring = {
      ...result.monitoring,
      enabled: process.env.MONITORING_ENABLED === 'true',
    };
  }
  
  if (process.env.METRICS_PORT) {
    result.monitoring = {
      ...result.monitoring,
      metricsPort: parseInt(process.env.METRICS_PORT, 10),
    };
  }
  
  if (process.env.TRACING_ENABLED !== undefined) {
    result.monitoring = {
      ...result.monitoring,
      tracingEnabled: process.env.TRACING_ENABLED === 'true',
    };
  }
  
  // Sandbox
  if (process.env.SANDBOX_ENABLED !== undefined) {
    result.sandbox = {
      ...result.sandbox,
      enabled: process.env.SANDBOX_ENABLED === 'true',
    };
  }
  
  if (process.env.SANDBOX_TIMEOUT) {
    result.sandbox = {
      ...result.sandbox,
      timeout: parseInt(process.env.SANDBOX_TIMEOUT, 10),
    };
  }
  
  if (process.env.SANDBOX_MAX_MEMORY) {
    result.sandbox = {
      ...result.sandbox,
      maxMemory: parseInt(process.env.SANDBOX_MAX_MEMORY, 10),
    };
  }
  
  return result;
}

/**
 * Load configuration from a JSON file
 */
export function loadConfigFromFile(path: string): Partial<GodAgentConfig> {
  try {
    const fullPath = resolve(path);
    const content = readFileSync(fullPath, 'utf-8');
    const config = JSON.parse(content);
    return GodAgentConfigSchema.partial().parse(config);
  } catch {
    return {};
  }
}

/**
 * Default configuration paths
 */
export const DEFAULT_CONFIG_PATHS = [
  './harness.config.json',
  './config/harness.config.json',
  '/etc/harness/config.json',
];

// =============================================================================
// Configuration Manager
// =============================================================================

class ConfigurationManager {
  private config: GodAgentConfig;
  private loaded: boolean = false;

  constructor() {
    this.config = { ...DEFAULT_GOD_AGENT_CONFIG };
  }

  /**
   * Load configuration from all sources
   */
  load(): GodAgentConfig {
    if (this.loaded) {
      return this.config;
    }

    // Step 1: Load from environment variables
    const envConfig = loadGodAgentConfigFromEnv();
    this.config = { ...this.config, ...envConfig };

    // Step 2: Try to load from config files
    for (const path of DEFAULT_CONFIG_PATHS) {
      const fileConfig = loadConfigFromFile(path);
      if (Object.keys(fileConfig).length > 0) {
        this.config = { ...this.config, ...fileConfig };
        break; // Use first found config file
      }
    }

    // Step 3: Validate and finalize
    this.config = GodAgentConfigSchema.parse(this.config);
    this.loaded = true;

    return this.config;
  }

  /**
   * Get the current configuration
   */
  get(): GodAgentConfig {
    if (!this.loaded) {
      this.load();
    }
    return this.config;
  }

  /**
   * Update configuration
   */
  update(partial: Partial<GodAgentConfig>): GodAgentConfig {
    this.config = GodAgentConfigSchema.parse({ ...this.config, ...partial });
    return this.config;
  }

  /**
   * Get LLM configuration
   */
  getLLMConfig(): LLMConfig {
    return this.config.llm;
  }

  /**
   * Set LLM configuration
   */
  setLLMConfig(llmConfig: Partial<LLMConfig>): LLMConfig {
    this.config.llm = LLMConfigSchema.parse({ ...this.config.llm, ...llmConfig });
    return this.config.llm;
  }

  /**
   * Reset to defaults
   */
  reset(): void {
    this.config = { ...DEFAULT_GOD_AGENT_CONFIG };
    this.loaded = false;
  }
}

// Singleton instance
export const configManager = new ConfigurationManager();

/**
 * Get the global configuration
 */
export function getConfig(): GodAgentConfig {
  return configManager.get();
}

/**
 * Load and get the global configuration
 */
export function loadConfig(): GodAgentConfig {
  return configManager.load();
}

/**
 * Update the global configuration
 */
export function updateConfig(partial: Partial<GodAgentConfig>): GodAgentConfig {
  return configManager.update(partial);
}

/**
 * Get LLM configuration from global config
 */
export function getLLMConfig(): LLMConfig {
  return configManager.getLLMConfig();
}

/**
 * Set LLM configuration in global config
 */
export function setLLMConfig(llmConfig: Partial<LLMConfig>): LLMConfig {
  return configManager.setLLMConfig(llmConfig);
}

/**
 * Reset configuration to defaults
 */
export function resetConfig(): void {
  configManager.reset();
}

// Re-export types for convenience
export type { GodAgentConfig, LLMConfig } from './schemas';
