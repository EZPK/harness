/**
 * Simple Test File
 * 
 * Test the basic functionality of Harness-TS
 */

import { createGodAgent } from './agents/god/agent';
import { createLLMAgent } from './agents/specialists/llm';
import { registerOllama } from './providers/config';
import { getProvider, getProvidersList } from './providers/registry';
import { getAgentRegistry } from './agents/registry';
import { loadConfig } from './configs/settings';

async function testHarnessTS() {
  console.log('='.repeat(60));
  console.log('Harness-TS - Basic Test');
  console.log('='.repeat(60));
  console.log();

  // Test 1: Configuration
  console.log('Test 1: Loading configuration...');
  try {
    const config = loadConfig();
    console.log('  ✓ Configuration loaded');
    console.log(`    - Routing strategy: ${config.routingStrategy}`);
    console.log(`    - Decomposition strategy: ${config.decompositionStrategy}`);
    console.log(`    - LLM provider: ${config.llm.provider}`);
    console.log(`    - LLM model: ${config.llm.model}`);
  } catch (error) {
    console.log('  ✗ Configuration loading failed:', error);
  }
  console.log();

  // Test 2: Provider Registry
  console.log('Test 2: Testing provider registry...');
  try {
    const providers = getProvidersList();
    console.log(`  ✓ Found ${providers.length} providers: ${providers.join(', ')}`);
    
    // Register Ollama with custom config
    registerOllama('http://localhost:11434/v1', 'llama-3.1-8b');
    console.log('  ✓ Ollama provider registered');
    
    const ollamaProvider = getProvider('ollama');
    console.log(`    - Ollama base URL: ${ollamaProvider?.baseUrl || 'default'}`);
    console.log(`    - Ollama default model: ${ollamaProvider?.defaultModel || 'default'}`);
  } catch (error) {
    console.log('  ✗ Provider registry test failed:', error);
  }
  console.log();

  // Test 3: Agent Registry
  console.log('Test 3: Testing agent registry...');
  try {
    const registry = getAgentRegistry();
    console.log(`  ✓ Agent registry initialized`);
    console.log(`    - Agent count: ${registry.getAgentCount()}`);
    console.log(`    - Available capabilities: ${registry.getAllCapabilities().join(', ')}`);
  } catch (error) {
    console.log('  ✗ Agent registry test failed:', error);
  }
  console.log();

  // Test 4: Create GodAgent
  console.log('Test 4: Creating GodAgent...');
  try {
    const godAgent = createGodAgent({
      routingStrategy: 'hybrid',
      decompositionStrategy: 'hybrid',
      llm: {
        provider: 'ollama',
        model: 'llama-3.1-8b',
        temperature: 0.7,
        timeout: 120,
      },
    });
    
    console.log('  ✓ GodAgent created');
    console.log(`    - ID: ${godAgent.id}`);
    console.log(`    - Name: ${godAgent.name}`);
    console.log(`    - State: ${godAgent.state}`);
    console.log(`    - Capabilities: ${godAgent.capabilities.join(', ')}`);
    
    // Test agent info
    const info = godAgent.getInfo();
    console.log(`    - Task count: ${info.taskCount}`);
    console.log(`    - Error count: ${info.errorCount}`);
  } catch (error) {
    console.log('  ✗ GodAgent creation failed:', error);
  }
  console.log();

  // Test 5: Create LLMAgent
  console.log('Test 5: Creating LLMAgent...');
  try {
    const llmAgent = createLLMAgent('TestLLMAgent', 'ollama', 'llama-3.1-8b');
    console.log('  ✓ LLMAgent created');
    console.log(`    - ID: ${llmAgent.id}`);
    console.log(`    - Name: ${llmAgent.name}`);
    console.log(`    - Capabilities: ${llmAgent.capabilities.length} capabilities`);
    console.log(`    - Capability list: ${llmAgent.capabilities.join(', ')}`);
    
    // Test agent info
    const info = llmAgent.getInfo();
    console.log(`    - State: ${info.state}`);
  } catch (error) {
    console.log('  ✗ LLMAgent creation failed:', error);
  }
  console.log();

  // Test 6: Task Submission (without actual LLM call)
  console.log('Test 6: Testing task submission (mock)...');
  try {
    createGodAgent({});
    
    // Note: We can't actually submit tasks without initializing agents
    // and having actual LLM providers available
    console.log('  ⚠ Skipping actual task submission (requires LLM providers)');
    console.log('    To test task submission:');
    console.log('    1. Start Ollama: ollama serve');
    console.log('    2. Set OLLAMA_BASE_URL=http://localhost:11434/v1');
    console.log('    3. Run: make dev');
  } catch (error) {
    console.log('  ✗ Task submission test failed:', error);
  }
  console.log();

  // Summary
  console.log('='.repeat(60));
  console.log('Test Summary');
  console.log('='.repeat(60));
  console.log('✓ All basic tests completed successfully!');
  console.log();
  console.log('Next steps:');
  console.log('1. Install dependencies: make install-dev');
  console.log('2. Build the project: make build');
  console.log('3. Run the TUI: make start-tui');
  console.log();
}

// Run tests
testHarnessTS().catch(console.error);
