"""
Settings management for Harness Agentic Framework.

This module provides centralized configuration loading from:
- Environment variables
- .env files
- YAML configuration files
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from functools import lru_cache

import yaml
from pydantic import ValidationError
from pydantic_settings import BaseSettings

from .schemas import (
    HarnessConfig,
    Settings as BaseSettingsClass,
    SandboxConfig,
    CheckpointConfig,
    MonitoringConfig,
    SecurityConfig,
    GodAgentConfig,
    PlannerAgentConfig,
    CoderAgentConfig,
    ReviewerAgentConfig,
    TesterAgentConfig,
    DebuggerAgentConfig,
    ResearcherAgentConfig,
    DocumenterAgentConfig,
    ShellToolConfig,
    PythonToolConfig,
    GitToolConfig,
    FileIOToolConfig,
    TestRunnerToolConfig,
    LinterToolConfig,
    WorkflowConfig,
)


# =============================================================================
# Runtime Settings (from environment)
# =============================================================================

class Settings(BaseSettingsClass):
    """
    Runtime settings loaded from environment variables and .env files.
    
    This is a singleton that can be accessed via `get_settings()`.
    """
    pass


@lru_cache()
def get_settings() -> Settings:
    """
    Get the runtime settings instance.
    
    Returns:
        Settings: The loaded settings instance.
    
    Example:
        >>> settings = get_settings()
        >>> print(settings.host)
    """
    return Settings()


# =============================================================================
# Configuration Loading
# =============================================================================

class ConfigLoader:
    """
    Loads and manages Harness configuration from YAML files.
    
    Configuration hierarchy:
    1. Default values (from Pydantic models)
    2. YAML config files (agents.yaml, tools.yaml, etc.)
    3. Environment variables (via Settings)
    """
    
    CONFIG_DIR = Path(__file__).parent / "configs"
    DEFAULT_CONFIGS = {
        "agents": "agents.yaml",
        "tools": "tools.yaml",
        "workflows": "workflows.yaml",
    }
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize the config loader.
        
        Args:
            config_dir: Directory containing config files. 
                       If None, uses the package configs directory.
        """
        self.config_dir = config_dir or self.CONFIG_DIR
        self._loaded_configs: Dict[str, Dict[str, Any]] = {}
        self._harness_config: Optional[HarnessConfig] = None
    
    def load_yaml(self, filename: str) -> Dict[str, Any]:
        """
        Load a YAML configuration file.
        
        Args:
            filename: Name of the YAML file.
            
        Returns:
            Dictionary containing the configuration.
            
        Raises:
            FileNotFoundError: If the file doesn't exist.
            yaml.YAMLError: If the YAML is invalid.
        """
        filepath = self.config_dir / filename
        
        if not filepath.exists():
            return {}
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    
    def load_agents_config(self) -> Dict[str, Any]:
        """Load agents configuration from agents.yaml."""
        if "agents" not in self._loaded_configs:
            self._loaded_configs["agents"] = self.load_yaml("agents.yaml")
        return self._loaded_configs["agents"]
    
    def load_tools_config(self) -> Dict[str, Any]:
        """Load tools configuration from tools.yaml."""
        if "tools" not in self._loaded_configs:
            self._loaded_configs["tools"] = self.load_yaml("tools.yaml")
        return self._loaded_configs["tools"]
    
    def load_workflows_config(self) -> Dict[str, Any]:
        """Load workflows configuration from workflows.yaml."""
        if "workflows" not in self._loaded_configs:
            self._loaded_configs["workflows"] = self.load_yaml("workflows.yaml")
        return self._loaded_configs["workflows"]
    
    def build_harness_config(self) -> HarnessConfig:
        """
        Build the complete HarnessConfig by merging defaults, YAML configs, and env vars.
        
        Returns:
            HarnessConfig: The complete validated configuration.
            
        Raises:
            ValidationError: If the configuration is invalid.
        """
        if self._harness_config is not None:
            return self._harness_config
        
        # Load base YAML configs
        agents_config = self.load_agents_config()
        tools_config = self.load_tools_config()
        workflows_config = self.load_workflows_config()
        
        # Get runtime settings
        runtime_settings = get_settings()
        
        # Build the harness config from individual components
        config_dict = {
            "sandbox": self._build_sandbox_config(agents_config, tools_config),
            "checkpointing": self._build_checkpoint_config(agents_config),
            "monitoring": self._build_monitoring_config(agents_config, runtime_settings),
            "security": self._build_security_config(agents_config),
            "god": self._build_god_config(agents_config.get("god", {})),
            "planner": self._build_planner_config(agents_config.get("planner", {})),
            "coder": self._build_coder_config(agents_config.get("coder", {})),
            "reviewer": self._build_reviewer_config(agents_config.get("reviewer", {})),
            "tester": self._build_tester_config(agents_config.get("tester", {})),
            "debugger": self._build_debugger_config(agents_config.get("debugger", {})),
            "researcher": self._build_researcher_config(agents_config.get("researcher", {})),
            "documenter": self._build_documenter_config(agents_config.get("documenter", {})),
            "shell": self._build_shell_config(tools_config.get("shell", {})),
            "python": self._build_python_config(tools_config.get("python", {})),
            "git": self._build_git_config(tools_config.get("git", {})),
            "file_io": self._build_file_io_config(tools_config.get("file_io", {})),
            "test_runner": self._build_test_runner_config(tools_config.get("test_runner", {})),
            "linter": self._build_linter_config(tools_config.get("linter", {})),
            "workflows": self._build_workflows_config(workflows_config),
        }
        
        # Create and validate the harness config
        try:
            self._harness_config = HarnessConfig(**config_dict)
            return self._harness_config
        except ValidationError as e:
            # Log the error and re-raise
            print(f"Configuration validation error: {e}")
            raise
    
    def _build_sandbox_config(self, agents_config: Dict, tools_config: Dict) -> Dict:
        """Build sandbox configuration."""
        config = {}
        
        if "sandbox" in agents_config:
            config.update(agents_config["sandbox"])
        if "sandbox" in tools_config:
            config.update(tools_config["sandbox"])
        
        return config
    
    def _build_checkpoint_config(self, agents_config: Dict) -> Dict:
        """Build checkpoint configuration."""
        return agents_config.get("checkpointing", {})
    
    def _build_monitoring_config(self, agents_config: Dict, runtime_settings: Settings) -> Dict:
        """Build monitoring configuration."""
        config = agents_config.get("monitoring", {})
        config.update({
            "log_level": runtime_settings.log_level,
            "log_format": runtime_settings.log_format,
        })
        return config
    
    def _build_security_config(self, agents_config: Dict) -> Dict:
        """Build security configuration."""
        return agents_config.get("security", {})
    
    def _build_god_config(self, god_config: Dict) -> Dict:
        """Build God Agent configuration."""
        return god_config
    
    def _build_planner_config(self, planner_config: Dict) -> Dict:
        """Build Planner Agent configuration."""
        return planner_config
    
    def _build_coder_config(self, coder_config: Dict) -> Dict:
        """Build Coder Agent configuration."""
        return coder_config
    
    def _build_reviewer_config(self, reviewer_config: Dict) -> Dict:
        """Build Reviewer Agent configuration."""
        return reviewer_config
    
    def _build_tester_config(self, tester_config: Dict) -> Dict:
        """Build Tester Agent configuration."""
        return tester_config
    
    def _build_debugger_config(self, debugger_config: Dict) -> Dict:
        """Build Debugger Agent configuration."""
        return debugger_config
    
    def _build_researcher_config(self, researcher_config: Dict) -> Dict:
        """Build Researcher Agent configuration."""
        return researcher_config
    
    def _build_documenter_config(self, documenter_config: Dict) -> Dict:
        """Build Documenter Agent configuration."""
        return documenter_config
    
    def _build_shell_config(self, shell_config: Dict) -> Dict:
        """Build Shell Tool configuration."""
        return shell_config
    
    def _build_python_config(self, python_config: Dict) -> Dict:
        """Build Python Tool configuration."""
        config = python_config
        if "sandbox" in config:
            config["sandbox_config"] = config.pop("sandbox")
        return config
    
    def _build_git_config(self, git_config: Dict) -> Dict:
        """Build Git Tool configuration."""
        return git_config
    
    def _build_file_io_config(self, file_io_config: Dict) -> Dict:
        """Build File I/O Tool configuration."""
        return file_io_config
    
    def _build_test_runner_config(self, test_runner_config: Dict) -> Dict:
        """Build Test Runner Tool configuration."""
        return test_runner_config
    
    def _build_linter_config(self, linter_config: Dict) -> Dict:
        """Build Linter Tool configuration."""
        return linter_config
    
    def _build_workflows_config(self, workflows_config: Dict) -> Dict:
        """Build workflows configuration."""
        return {name: workflow for name, workflow in workflows_config.items()}


# =============================================================================
# Global Config Loader Instance
# =============================================================================

config_loader = ConfigLoader()


def get_config() -> HarnessConfig:
    """
    Get the complete validated Harness configuration.
    
    Returns:
        HarnessConfig: The complete configuration.
    
    Example:
        >>> config = get_config()
        >>> print(config.god.timeout)
    """
    return config_loader.build_harness_config()


def reload_config() -> HarnessConfig:
    """
    Reload the configuration (clears cache).
    
    Returns:
        HarnessConfig: The fresh configuration.
    """
    config_loader._harness_config = None
    return config_loader.build_harness_config()


# =============================================================================
# Convenience Functions
# =============================================================================


def get_agent_config(agent_name: str):
    """
    Get configuration for a specific agent.
    
    Args:
        agent_name: Name of the agent (god, planner, coder, etc.)
        
    Returns:
        AgentConfig: The agent configuration.
        
    Raises:
        ValueError: If the agent name is not recognized.
    """
    config = get_config()
    agent_config = getattr(config, agent_name, None)
    
    if agent_config is None:
        raise ValueError(f"Unknown agent: {agent_name}")
    
    return agent_config


def get_tool_config(tool_name: str):
    """
    Get configuration for a specific tool.
    
    Args:
        tool_name: Name of the tool (shell, python, git, etc.)
        
    Returns:
        ToolConfig: The tool configuration.
        
    Raises:
        ValueError: If the tool name is not recognized.
    """
    config = get_config()
    tool_config = getattr(config, tool_name, None)
    
    if tool_config is None:
        raise ValueError(f"Unknown tool: {tool_name}")
    
    return tool_config
