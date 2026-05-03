/**
 * Provider Registry
 * 
 * Manages LLM providers using pi-mono's @mariozechner/pi-ai package.
 * This replaces the Python providers/ module.
 */

import {
  getModel as getModelFromPiAi,
  getProviders,
  type Model,
} from '@mariozechner/pi-ai';
import {
  type ProviderName,
  type LLMConfig,
} from '../configs/schemas';

// =============================================================================
// Provider Configuration
// =============================================================================

export interface ProviderConfig {
  name: ProviderName;
  apiKey?: string;
  baseUrl?: string;
  defaultModel?: string;
  models?: string[];
}

// =============================================================================
// Model Cache
// =============================================================================

interface ModelCacheEntry {
  model: Model<any>;
  lastUsed: number;
}

// =============================================================================
// Provider Registry Class
// =============================================================================

export class ProviderRegistry {
  private providers: Map<ProviderName, ProviderConfig> = new Map();
  private modelCache: Map<string, ModelCacheEntry> = new Map();
  private initialized: boolean = false;

  constructor() {
    this.initialize();
  }

  /**
   * Initialize the registry with default providers
   */
  private initialize(): void {
    if (this.initialized) return;

    const allProviders = getProviders();
    
    for (const providerName of allProviders) {
      const name = providerName as ProviderName;
      this.providers.set(name, {
        name,
        models: this.getProviderModelsList(name),
      });
    }

    this.initialized = true;
  }

  /**
   * Get all models for a provider
   */
  private getProviderModelsList(provider: ProviderName): string[] {
    const config = this.providers.get(provider);
    return config?.models || [];
  }

  /**
   * Register a new provider configuration
   */
  register(config: ProviderConfig): void {
    this.providers.set(config.name, config);
  }

  /**
   * Get a list of all registered provider names
   */
  getAllProviderNames(): ProviderName[] {
    return Array.from(this.providers.keys());
  }

  /**
   * Get provider configuration
   */
  getProviderConfig(name: ProviderName): ProviderConfig | undefined {
    return this.providers.get(name);
  }

  /**
   * Get all models for a provider
   */
  getProviderModels(provider: ProviderName): string[] {
    return this.getProviderModelsList(provider);
  }

  /**
   * Get all models across all providers
   */
  getAllModels(): string[] {
    const allModels: string[] = [];
    for (const provider of this.providers.keys()) {
      allModels.push(...this.getProviderModels(provider));
    }
    return [...new Set(allModels)];
  }

  /**
   * Get a specific model from a provider
   */
  getModel(provider: ProviderName, modelId: string): Model<any> {
    const cacheKey = `${provider}:${modelId}`;
    
    // Check cache
    const cached = this.modelCache.get(cacheKey);
    if (cached) {
      // Update last used timestamp
      cached.lastUsed = Date.now();
      return cached.model;
    }

    // Get from pi-ai
    const model = getModelFromPiAi(provider as any, modelId) as Model<any>;
    
    // Cache it
    this.modelCache.set(cacheKey, {
      model,
      lastUsed: Date.now(),
    });

    return model;
  }

  /**
   * Get API key for a provider
   */
  getApiKey(provider: ProviderName): string | undefined {
    const config = this.providers.get(provider);
    return config?.apiKey || process.env[`${provider.toUpperCase()}_API_KEY`];
  }

  /**
   * Get base URL for a provider
   */
  getBaseUrl(provider: ProviderName): string | undefined {
    const config = this.providers.get(provider);
    return config?.baseUrl;
  }

  /**
   * Clear the model cache
   */
  clearCache(): void {
    this.modelCache.clear();
  }

  /**
   * Get a model from LLMConfig
   */
  getModelFromConfig(config: LLMConfig): Model<any> {
    return this.getModel(config.provider, config.model);
  }
}

// =============================================================================
// Singleton Instance
// =============================================================================

export const providerRegistry = new ProviderRegistry();

// =============================================================================
// Convenience Functions
// =============================================================================

export function getProviderRegistry(): ProviderRegistry {
  return providerRegistry;
}

export function getProvidersList(): ProviderName[] {
  return providerRegistry.getAllProviderNames();
}

export function getProvider(name: ProviderName): ProviderConfig | undefined {
  return providerRegistry.getProviderConfig(name);
}

export function getModelsList(provider: ProviderName): string[] {
  return providerRegistry.getProviderModels(provider);
}

export function getModel(provider: ProviderName, modelId: string): Model<any> {
  return providerRegistry.getModel(provider, modelId);
}
