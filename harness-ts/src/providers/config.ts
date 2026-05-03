/**
 * Provider Configuration Utilities
 * 
 * Helper functions for managing provider configurations.
 */

import {
  type ProviderName,
  type LLMConfig,
  DEFAULT_LLM_CONFIG,
} from '../configs/schemas';
import { providerRegistry } from './registry';

// =============================================================================
// Provider-specific Configuration
// =============================================================================

/**
 * Configuration for OpenAI-compatible providers
 */
export interface OpenAICompatibleConfig {
  baseUrl?: string;
  apiKey?: string;
  model: string;
}

/**
 * Configuration for Ollama
 */
export interface OllamaConfig extends OpenAICompatibleConfig {
  baseUrl?: string; // Default: http://localhost:11434/v1
}

/**
 * Configuration for Mistral
 */
export interface MistralConfig {
  apiKey: string;
  model?: string;
}

/**
 * Configuration for OpenAI
 */
export interface OpenAIConfig {
  apiKey: string;
  model?: string;
  baseUrl?: string; // For custom deployments
}

/**
 * Configuration for Anthropic
 */
export interface AnthropicConfig {
  apiKey: string;
  model?: string;
}

/**
 * Union type for all provider configurations
 */
export type ProviderSpecificConfig =
  | OllamaConfig
  | MistralConfig
  | OpenAIConfig
  | AnthropicConfig;

// =============================================================================
// Configuration Helpers
// =============================================================================

/**
 * Create an LLMConfig from a provider name and model
 */
export function createLLMConfig(
  provider: ProviderName,
  model: string,
  apiKey?: string,
  baseUrl?: string
): LLMConfig {
  return {
    provider,
    model,
    apiKey,
    baseUrl,
    temperature: DEFAULT_LLM_CONFIG.temperature,
    timeout: DEFAULT_LLM_CONFIG.timeout,
  };
}

/**
 * Create an LLMConfig for Ollama
 */
export function createOllamaConfig(
  model: string = 'llama-3.1-8b',
  baseUrl: string = 'http://localhost:11434/v1'
): LLMConfig {
  return createLLMConfig('ollama', model, undefined, baseUrl);
}

/**
 * Create an LLMConfig for Mistral
 */
export function createMistralConfig(apiKey: string, model: string = 'mistral-large'): LLMConfig {
  return createLLMConfig('mistral', model, apiKey);
}

/**
 * Create an LLMConfig for OpenAI
 */
export function createOpenAIConfig(apiKey: string, model: string = 'gpt-4o-mini'): LLMConfig {
  return createLLMConfig('openai', model, apiKey);
}

/**
 * Create an LLMConfig for Anthropic
 */
export function createAnthropicConfig(
  apiKey: string,
  model: string = 'claude-3-5-sonnet-20241022'
): LLMConfig {
  return createLLMConfig('anthropic', model, apiKey);
}

/**
 * Register Ollama provider with custom configuration
 */
export function registerOllama(
  baseUrl: string = 'http://localhost:11434/v1',
  defaultModel: string = 'llama-3.1-8b'
): void {
  providerRegistry.register({ name: 'ollama', baseUrl, defaultModel });
}

/**
 * Register Mistral provider
 */
export function registerMistral(apiKey: string, defaultModel?: string): void {
  providerRegistry.register({ name: 'mistral', apiKey, defaultModel });
}

/**
 * Register OpenAI provider
 */
export function registerOpenAI(apiKey: string, baseUrl?: string, defaultModel?: string): void {
  providerRegistry.register({ name: 'openai', apiKey, baseUrl, defaultModel });
}

/**
 * Register Anthropic provider
 */
export function registerAnthropic(apiKey: string, defaultModel?: string): void {
  providerRegistry.register({ name: 'anthropic', apiKey, defaultModel });
}

/**
 * Initialize providers from environment variables
 */
export function initializeProvidersFromEnv(): void {
  // Ollama
  if (process.env.OLLAMA_BASE_URL || process.env.OLLAMA_MODEL) {
    registerOllama(
      process.env.OLLAMA_BASE_URL || 'http://localhost:11434/v1',
      process.env.OLLAMA_MODEL || 'llama-3.1-8b'
    );
  }

  // Mistral
  if (process.env.MISTRAL_API_KEY) {
    registerMistral(process.env.MISTRAL_API_KEY);
  }

  // OpenAI
  if (process.env.OPENAI_API_KEY) {
    registerOpenAI(process.env.OPENAI_API_KEY);
  }

  // Anthropic
  if (process.env.ANTHROPIC_API_KEY) {
    registerAnthropic(process.env.ANTHROPIC_API_KEY);
  }
}

/**
 * Get the recommended model for a provider
 */
export function getRecommendedModel(provider: ProviderName): string {
  const recommended: Record<ProviderName, string> = {
    ollama: 'llama-3.1-8b',
    mistral: 'mistral-large',
    openai: 'gpt-4o-mini',
    anthropic: 'claude-3-5-sonnet-20241022',
    google: 'gemini-2.5-flash',
    azure: 'gpt-4o-mini',
    groq: 'llama-3.1-70b-versatile',
    cerebras: 'gpt-oss-120b',
    deepseek: 'deepseek-chat',
    local: 'llama-3.1-8b',
  };
  return recommended[provider] || 'llama-3.1-8b';
}

/**
 * Get provider name from model ID (best effort)
 */
export function getProviderFromModel(modelId: string): ProviderName | undefined {
  const patterns: Record<string, ProviderName> = {
    'gpt-': 'openai',
    'claude-': 'anthropic',
    'gemini-': 'google',
    'mistral-': 'mistral',
    'llama-': 'ollama',
    'llava-': 'ollama',
    'phi-': 'ollama',
    'qwen-': 'ollama',
    'vicuna-': 'ollama',
  };

  for (const [pattern, provider] of Object.entries(patterns)) {
    if (modelId.toLowerCase().includes(pattern)) {
      return provider as ProviderName;
    }
  }

  return undefined;
}
