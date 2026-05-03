/**
 * Agent Registry
 * 
 * Manages all registered agents and provides lookup/filtering capabilities.
 */

import { type AgentID, type AgentConfig, type AgentState, type TaskContext, type TaskResult } from '@/configs/schemas';
import { BaseAgent } from '@/agents/base';
import { incrementMetric } from '@/core/monitoring/metrics';

// =============================================================================
// Agent Entry
// =============================================================================

interface AgentEntry {
  agent: BaseAgent;
  config: AgentConfig;
  registeredAt: Date;
  lastUsed?: Date;
  usageCount: number;
}

// =============================================================================
// Agent Registry
// =============================================================================

export class AgentRegistry {
  private agents: Map<AgentID, AgentEntry> = new Map();
  private nameIndex: Map<string, AgentID> = new Map();
  private capabilityIndex: Map<string, Set<AgentID>> = new Map();

  /**
   * Register an agent
   */
  register(agent: BaseAgent, config: Partial<AgentConfig> = {}): AgentID {
    if (this.agents.has(agent.id)) {
      // Already registered
      return agent.id;
    }

    // Create entry
    const entry: AgentEntry = {
      agent,
      config: {
        id: agent.id,
        name: agent.name,
        description: agent.description,
        capabilities: agent.capabilities.map((name) => {
          const info = agent.capabilityInfo.get(name);
          return {
            name,
            description: info?.description || '',
            level: (info?.level as 'basic' | 'standard' | 'advanced' | 'expert') || 'standard',
            version: info?.version || '1.0',
            dependsOn: info?.dependsOn || [],
          };
        }),
        runtime: config.runtime as any || {},
      },
      registeredAt: new Date(),
      lastUsed: undefined,
      usageCount: 0,
    };

    // Add to main map
    this.agents.set(agent.id, entry);

    // Add to name index
    this.nameIndex.set(agent.name, agent.id);

    // Add to capability index
    for (const capability of agent.capabilities) {
      if (!this.capabilityIndex.has(capability)) {
        this.capabilityIndex.set(capability, new Set());
      }
      this.capabilityIndex.get(capability)!.add(agent.id);
    }

    incrementMetric('registry.agents.registered', 1);

    return agent.id;
  }

  /**
   * Unregister an agent
   */
  unregister(agentId: AgentID): boolean {
    const entry = this.agents.get(agentId);
    if (!entry) return false;

    // Remove from name index
    this.nameIndex.delete(entry.agent.name);

    // Remove from capability index
    for (const capability of entry.agent.capabilities) {
      const set = this.capabilityIndex.get(capability);
      if (set) {
        set.delete(agentId);
        if (set.size === 0) {
          this.capabilityIndex.delete(capability);
        }
      }
    }

    // Remove from main map
    this.agents.delete(agentId);

    incrementMetric('registry.agents.unregistered', 1);

    return true;
  }

  /**
   * Get an agent by ID
   */
  getAgent(agentId: AgentID): BaseAgent | undefined {
    const entry = this.agents.get(agentId);
    if (!entry) return undefined;

    // Update last used
    entry.lastUsed = new Date();
    entry.usageCount++;

    return entry.agent;
  }

  /**
   * Get an agent by name
   */
  getAgentByName(name: string): BaseAgent | undefined {
    const agentId = this.nameIndex.get(name);
    if (!agentId) return undefined;
    return this.getAgent(agentId);
  }

  /**
   * Get all agents
   */
  getAllAgents(): BaseAgent[] {
    return Array.from(this.agents.values()).map((entry) => entry.agent);
  }

  /**
   * Get all agent IDs
   */
  getAgentIds(): AgentID[] {
    return Array.from(this.agents.keys());
  }

  /**
   * Get agents by capability
   */
  getAgentsByCapability(capability: string): BaseAgent[] {
    const agentIds = this.capabilityIndex.get(capability);
    if (!agentIds) return [];

    return Array.from(agentIds).map((id) => this.getAgent(id)).filter(Boolean) as BaseAgent[];
  }

  /**
   * Get agents by state
   */
  getAgentsByState(state: AgentState): BaseAgent[] {
    return Array.from(this.agents.values())
      .filter((entry) => entry.agent.state === state)
      .map((entry) => entry.agent);
  }

  /**
   * Get available agents (idle or busy)
   */
  getAvailableAgents(): BaseAgent[] {
    return this.getAgentsByState('idle').concat(this.getAgentsByState('busy'));
  }

  /**
   * Get idle agents
   */
  getIdleAgents(): BaseAgent[] {
    return this.getAgentsByState('idle');
  }

  /**
   * Get busy agents
   */
  getBusyAgents(): BaseAgent[] {
    return this.getAgentsByState('busy');
  }

  /**
   * Check if an agent exists
   */
  hasAgent(agentId: AgentID): boolean {
    return this.agents.has(agentId);
  }

  /**
   * Check if an agent with a name exists
   */
  hasAgentByName(name: string): boolean {
    return this.nameIndex.has(name);
  }

  /**
   * Check if any agent has a capability
   */
  hasCapability(capability: string): boolean {
    return this.capabilityIndex.has(capability);
  }

  /**
   * Get all capabilities
   */
  getAllCapabilities(): string[] {
    return Array.from(this.capabilityIndex.keys());
  }

  /**
   * Get agent count
   */
  getAgentCount(): number {
    return this.agents.size;
  }

  /**
   * Get stats
   */
  getStats() {
    return {
      totalAgents: this.agents.size,
      idleCount: this.getIdleAgents().length,
      busyCount: this.getBusyAgents().length,
      totalCapabilities: this.capabilityIndex.size,
      mostUsed: this.getMostUsedAgent(),
    };
  }

  /**
   * Get the most used agent
   */
  private getMostUsedAgent(): { name: string; usageCount: number } | undefined {
    let maxEntry: AgentEntry | undefined;
    for (const entry of this.agents.values()) {
      if (!maxEntry || entry.usageCount > maxEntry.usageCount) {
        maxEntry = entry;
      }
    }
    return maxEntry ? { name: maxEntry.agent.name, usageCount: maxEntry.usageCount } : undefined;
  }

  /**
   * Initialize all registered agents
   */
  async initializeAll(): Promise<void> {
    const promises = Array.from(this.agents.values()).map(async (entry) => {
      if (entry.agent.state === 'uninitialized') {
        await entry.agent.initialize();
      }
    });
    await Promise.all(promises);
  }

  /**
   * Shutdown all registered agents
   */
  async shutdownAll(): Promise<void> {
    const promises = Array.from(this.agents.values()).map(async (entry) => {
      if (entry.agent.state !== 'shutdown') {
        await entry.agent.shutdown();
      }
    });
    await Promise.all(promises);
  }

  /**
   * Execute a task on an agent by ID
   */
  async executeTask(agentId: AgentID, task: any, context: TaskContext): Promise<TaskResult> {
    const agent = this.getAgent(agentId);
    if (!agent) {
      throw new Error(`Agent ${agentId} not found`);
    }
    return agent.executeTask(task, context);
  }

  /**
   * Execute a task on an agent by name
   */
  async executeTaskByName(name: string, task: any, context: TaskContext): Promise<TaskResult> {
    const agent = this.getAgentByName(name);
    if (!agent) {
      throw new Error(`Agent ${name} not found`);
    }
    return agent.executeTask(task, context);
  }

  /**
   * Find agents that match a set of capabilities
   */
  findAgentsByCapabilities(requiredCapabilities: string[]): BaseAgent[] {
    const matchingAgents: Map<AgentID, BaseAgent> = new Map();

    for (const capability of requiredCapabilities) {
      const agents = this.getAgentsByCapability(capability);
      for (const agent of agents) {
        if (!matchingAgents.has(agent.id)) {
          matchingAgents.set(agent.id, agent);
        }
      }
    }

    return Array.from(matchingAgents.values());
  }

  /**
   * Find the best agent for a task based on capabilities
   */
  findBestAgent(capabilities: string[], _context?: TaskContext): BaseAgent | undefined {
    const matchingAgents = this.findAgentsByCapabilities(capabilities);

    // Filter to available agents
    const availableAgents = matchingAgents.filter((a) => a.isAvailable());

    if (availableAgents.length === 0) return undefined;

    // TODO: Implement more sophisticated selection (priority, load balancing, etc.)
    // For now, just return the first available agent
    return availableAgents[0];
  }

  /**
   * Clear all agents
   */
  clear(): void {
    this.agents.clear();
    this.nameIndex.clear();
    this.capabilityIndex.clear();
  }
}

// =============================================================================
// Global Instance
// =============================================================================

export const agentRegistry = new AgentRegistry();

// =============================================================================
// Public API
// =============================================================================

/**
 * Get the global agent registry
 */
export function getAgentRegistry(): AgentRegistry {
  return agentRegistry;
}

/**
 * Register an agent
 */
export function registerAgent(agent: BaseAgent, config?: Partial<AgentConfig>): AgentID {
  return agentRegistry.register(agent, config);
}

/**
 * Unregister an agent
 */
export function unregisterAgent(agentId: AgentID): boolean {
  return agentRegistry.unregister(agentId);
}

/**
 * Get an agent by ID
 */
export function getAgent(agentId: AgentID): BaseAgent | undefined {
  return agentRegistry.getAgent(agentId);
}

/**
 * Get an agent by name
 */
export function getAgentByName(name: string): BaseAgent | undefined {
  return agentRegistry.getAgentByName(name);
}

/**
 * Get all agents
 */
export function getAllAgents(): BaseAgent[] {
  return agentRegistry.getAllAgents();
}

/**
 * Get agents by capability
 */
export function getAgentsByCapability(capability: string): BaseAgent[] {
  return agentRegistry.getAgentsByCapability(capability);
}

/**
 * Get available agents
 */
export function getAvailableAgents(): BaseAgent[] {
  return agentRegistry.getAvailableAgents();
}

/**
 * Check if an agent exists
 */
export function hasAgent(agentId: AgentID): boolean {
  return agentRegistry.hasAgent(agentId);
}

/**
 * Check if a capability exists
 */
export function hasCapability(capability: string): boolean {
  return agentRegistry.hasCapability(capability);
}

/**
 * Get all capabilities
 */
export function getAllCapabilities(): string[] {
  return agentRegistry.getAllCapabilities();
}

/**
 * Get agent count
 */
export function getAgentCount(): number {
  return agentRegistry.getAgentCount();
}

/**
 * Get registry stats
 */
export function getRegistryStats(): any {
  return agentRegistry.getStats();
}

/**
 * Find the best agent for a task
 */
export function findBestAgent(capabilities: string[], _context?: TaskContext): BaseAgent | undefined {
  return agentRegistry.findBestAgent(capabilities, _context);
}
