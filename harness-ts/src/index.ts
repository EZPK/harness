/**
 * Harness-TS - Main Entry Point
 * 
 * This is the main entry point for the Harness Agentic Framework TypeScript Edition.
 * It exports all public APIs and provides a convenient way to import the framework.
 */

// Configuration
export * from './configs/schemas';
export * from './configs/settings';

// Providers
export * from './providers/registry';
export * from './providers/config';

// Agents
export * from './agents/base';
export * from './agents/registry';
export * from './agents/god/agent';
export * from './agents/god/router';
export * from './agents/god/decomposer';
export * from './agents/god/aggregator';
export * from './agents/specialists/llm';

// Core
export * from './core/monitoring/tracing';
export * from './core/monitoring/alerts';

// Tools
export * from './tools';

// Default export - Harness framework initializer
import { GodAgent } from './agents/god/agent';
import { type GodAgentConfig } from './configs/schemas';

/**
 * Initialize the Harness Agentic Framework
 */
export async function initializeHarness(config: Partial<GodAgentConfig> = {}): Promise<GodAgent> {
  // Initialize provider registry
  // Load configuration from environment
  const fullConfig = { ...config };
  
  // Create and initialize GodAgent
  const godAgent = new GodAgent(fullConfig as GodAgentConfig);
  await godAgent.initialize();
  
  return godAgent;
}

/**
 * Run the Harness TUI
 */
export async function runTUI(_config: Partial<GodAgentConfig> = {}): Promise<void> {
  // TODO: Implement TUI
  // const { runTUI } = await import('./tui/app');
  // runTUI(fullConfig as GodAgentConfig);
}
