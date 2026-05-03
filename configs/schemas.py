"""
Pydantic schemas for Harness Agentic Framework configuration.

This module defines all configuration data models using Pydantic v2.
"""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings


# =============================================================================
# Core Configuration Schemas
# =============================================================================

class SandboxConfig(BaseModel):
    """Sandboxing configuration for secure code execution."""
    
    timeout: int = Field(default=30, ge=1, le=600, 
                        description="Timeout in seconds for sandboxed operations")
    max_memory_mb: int = Field(default=512, ge=64, le=4096,
                              description="Maximum memory in MB for sandboxed processes")
    max_cpu: float = Field(default=1.0, ge=0.1, le=8.0,
                           description="Maximum CPU cores for sandboxed processes")
    allowed_modules: List[str] = Field(
        default_factory=lambda: [
            "math", "json", "os", "sys", "re", "datetime", 
            "collections", "itertools", "functools"
        ],
        description="List of allowed Python modules in sandbox"
    )
    blocked_modules: List[str] = Field(
        default_factory=lambda: [
            "subprocess", "os.system", "shutil", "socket", 
            "http", "urllib", "requests", "boto3", "numpy"
        ],
        description="List of blocked Python modules in sandbox"
    )
    enable_network: bool = Field(default=False, 
                                  description="Allow network access in sandbox")
    enable_file_io: bool = Field(default=True,
                                  description="Allow file I/O in sandbox")
    allowed_paths: List[str] = Field(
        default_factory=lambda: ["./tmp", "./sandbox"],
        description="List of allowed filesystem paths"
    )


class CheckpointConfig(BaseModel):
    """Checkpointing configuration for state persistence."""
    
    dir: str = Field(default="./checkpoints",
                    description="Directory to store checkpoints")
    interval: int = Field(default=60, ge=0,
                          description="Checkpoint interval in seconds (0 = manual only)")
    max_checkpoints: int = Field(default=100, ge=1, le=10000,
                                  description="Maximum number of checkpoints to keep")
    compression: bool = Field(default=True,
                               description="Compress checkpoint data")
    encryption: bool = Field(default=False,
                              description="Encrypt checkpoint data")


class MonitoringConfig(BaseModel):
    """Monitoring and observability configuration."""
    
    metrics_enabled: bool = Field(default=True,
                                  description="Enable metrics collection")
    tracing_enabled: bool = Field(default=True,
                                  description="Enable distributed tracing")
    log_level: str = Field(default="INFO",
                           description="Minimum log level")
    log_format: Literal["json", "text"] = Field(default="json",
                                               description="Log output format")
    include_timestamps: bool = Field(default=True,
                                     description="Include timestamps in logs")
    export_prometheus: bool = Field(default=False,
                                    description="Export metrics to Prometheus")
    export_otlp: bool = Field(default=False,
                              description="Export traces via OTLP")


class SecurityConfig(BaseModel):
    """Security configuration for the harness."""
    
    rate_limit_requests: int = Field(default=100, ge=1,
                                        description="Max requests per window")
    rate_limit_window: int = Field(default=60, ge=1,
                                    description="Rate limit window in seconds")
    max_concurrent_tasks: int = Field(default=10, ge=1, le=100,
                                       description="Maximum concurrent tasks")
    enable_audit_log: bool = Field(default=True,
                                   description="Log all agent actions for audit")
    
    @field_validator('rate_limit_requests', 'rate_limit_window')
    @classmethod
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError("Must be positive")
        return v


# =============================================================================
# Agent Configuration Schemas
# =============================================================================

class AgentCapability(BaseModel):
    """Capabilities of an agent."""
    
    name: str = Field(..., description="Capability name")
    description: str = Field(..., description="Capability description")
    version: str = Field(default="1.0", description="Capability version")
    required_tools: List[str] = Field(default_factory=list,
                                       description="Tools required for this capability")


class AgentConfig(BaseModel):
    """Base configuration for an agent."""
    
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    enabled: bool = Field(default=True, description="Whether agent is enabled")
    timeout: int = Field(default=300, ge=1, le=3600,
                         description="Task timeout in seconds")
    max_retries: int = Field(default=3, ge=0, le=10,
                             description="Maximum retry attempts")
    retry_delay: float = Field(default=1.0, ge=0.1, le=60.0,
                               description="Delay between retries in seconds")
    capabilities: List[AgentCapability] = Field(
        default_factory=list,
        description="List of agent capabilities"
    )
    model: Optional[str] = Field(default=None,
                                  description="LLM model to use (if applicable)")


class GodAgentConfig(AgentConfig):
    """Configuration for the God Agent (orchestrator)."""
    
    name: str = "GodAgent"
    description: str = "Main orchestrator agent for software development"
    max_concurrent_tasks: int = Field(default=10, ge=1, le=50,
                                       description="Max concurrent subtasks")
    decomposition_strategy: Literal["template", "semantic", "hybrid"] = Field(
        default="template",
        description="Strategy for decomposing tasks"
    )
    routing_strategy: Literal["keyword", "capability", "hybrid"] = Field(
        default="hybrid",
        description="Strategy for routing tasks to agents"
    )


class PlannerAgentConfig(AgentConfig):
    """Configuration for the Planner Agent."""
    
    name: str = "PlannerAgent"
    description: str = "Agent for planning software development tasks"
    max_plan_depth: int = Field(default=5, ge=1, le=20,
                                description="Maximum depth of planning tree")
    estimate_accuracy: Literal["rough", "detailed"] = Field(
        default="detailed",
        description="Level of detail in effort estimates"
    )


class CoderAgentConfig(AgentConfig):
    """Configuration for the Coder Agent."""
    
    name: str = "CoderAgent"
    description: str = "Agent for implementing code"
    specializations: List[str] = Field(
        default_factory=lambda: ["python"],
        description="Programming languages this coder supports"
    )
    code_quality_level: Literal["draft", "standard", "production"] = Field(
        default="standard",
        description="Quality level for generated code"
    )
    include_comments: bool = Field(default=True,
                                   description="Include comments in generated code")
    include_tests: bool = Field(default=True,
                                description="Generate tests along with code")


class ReviewerAgentConfig(AgentConfig):
    """Configuration for the Reviewer Agent."""
    
    name: str = "ReviewerAgent"
    description: str = "Agent for reviewing and improving code"
    check_security: bool = Field(default=True,
                                  description="Check for security vulnerabilities")
    check_performance: bool = Field(default=True,
                                    description="Check for performance issues")
    check_style: bool = Field(default=True,
                               description="Check code style and conventions")
    check_tests: bool = Field(default=True,
                              description="Verify test coverage and quality")
    min_test_coverage: float = Field(default=80.0, ge=0.0, le=100.0,
                                    description="Minimum required test coverage (%)")


class TesterAgentConfig(AgentConfig):
    """Configuration for the Tester Agent."""
    
    name: str = "TesterAgent"
    description: str = "Agent for creating and running tests"
    test_types: List[Literal["unit", "integration", "e2e"]] = Field(
        default_factory=lambda: ["unit", "integration"],
        description="Types of tests to generate"
    )
    test_framework: str = Field(default="pytest",
                                description="Test framework to use")
    generate_mocks: bool = Field(default=True,
                                 description="Generate mock objects for tests")


class DebuggerAgentConfig(AgentConfig):
    """Configuration for the Debugger Agent."""
    
    name: str = "DebuggerAgent"
    description: str = "Agent for debugging issues"
    max_log_lines: int = Field(default=1000, ge=10, le=10000,
                                description="Max lines of logs to analyze")
    enable_reproduction: bool = Field(default=True,
                                     description="Attempt to reproduce bugs")
    suggest_fixes: bool = Field(default=True,
                                description="Suggest fixes for found issues")


class ResearcherAgentConfig(AgentConfig):
    """Configuration for the Researcher Agent."""
    
    name: str = "ResearcherAgent"
    description: str = "Agent for researching information"
    search_sources: List[Literal["docs", "github", "stackoverflow", "web"]] = Field(
        default_factory=lambda: ["docs"],
        description="Sources to search for information"
    )
    max_results: int = Field(default=5, ge=1, le=20,
                             description="Maximum number of search results")
    summarize_results: bool = Field(default=True,
                                   description="Summarize search results")


class DocumenterAgentConfig(AgentConfig):
    """Configuration for the Documenter Agent."""
    
    name: str = "DocumenterAgent"
    description: str = "Agent for generating documentation"
    doc_types: List[Literal["code", "api", "architecture", "tutorial"]] = Field(
        default_factory=lambda: ["code", "api"],
        description="Types of documentation to generate"
    )
    format: Literal["markdown", "rst", "html"] = Field(
        default="markdown",
        description="Documentation format"
    )
    include_examples: bool = Field(default=True,
                                   description="Include usage examples")


# =============================================================================
# Tool Configuration Schemas
# =============================================================================

class ToolConfig(BaseModel):
    """Base configuration for a tool."""
    
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    enabled: bool = Field(default=True, description="Whether tool is enabled")
    timeout: int = Field(default=60, ge=1, le=600,
                         description="Tool execution timeout in seconds")
    max_retries: int = Field(default=2, ge=0, le=5,
                             description="Maximum retry attempts for tool")
    requires_approval: bool = Field(default=False,
                                   description="Require manual approval for tool use")


class ShellToolConfig(ToolConfig):
    """Configuration for Shell Tool."""
    
    name: str = "ShellTool"
    description: str = "Execute shell commands"
    allowed_commands: List[str] = Field(
        default_factory=lambda: [
            "ls", "cd", "cat", "grep", "find", "mkdir", "rmdir",
            "echo", "pwd", "wc", "head", "tail"
        ],
        description="List of allowed shell commands"
    )
    blocked_commands: List[str] = Field(
        default_factory=lambda: [
            "rm", "dd", "mv", "cp", "chmod", "chown",
            "sudo", "apt", "yum", "pip", "curl", "wget"
        ],
        description="List of blocked shell commands"
    )
    allow_any: bool = Field(default=False,
                            description="Allow any command (DANGEROUS)")


class PythonToolConfig(ToolConfig):
    """Configuration for Python Execution Tool."""
    
    name: str = "PythonTool"
    description: str = "Execute Python code in sandbox"
    sandbox_config: SandboxConfig = Field(
        default_factory=SandboxConfig,
        description="Sandbox configuration for Python execution"
    )


class GitToolConfig(ToolConfig):
    """Configuration for Git Tool."""
    
    name: str = "GitTool"
    description: str = "Git operations"
    allowed_operations: List[str] = Field(
        default_factory=lambda: [
            "clone", "pull", "push", "add", "commit", 
            "checkout", "branch", "status", "log", "diff"
        ],
        description="List of allowed Git operations"
    )
    blocked_operations: List[str] = Field(
        default_factory=lambda: ["reset", "rebase", "merge", "revert"],
        description="List of blocked Git operations"
    )
    force_push_allowed: bool = Field(default=False,
                                    description="Allow force pushing")


class FileIOToolConfig(ToolConfig):
    """Configuration for File I/O Tool."""
    
    name: str = "FileIOTool"
    description: str = "File read/write operations"
    allowed_paths: List[str] = Field(
        default_factory=lambda: [".", "./src", "./tests", "./docs"],
        description="List of allowed filesystem paths"
    )
    blocked_paths: List[str] = Field(
        default_factory=lambda: ["/etc", "/usr", "/bin", "/root"],
        description="List of blocked filesystem paths"
    )
    allowed_extensions: List[str] = Field(
        default_factory=lambda: [".py", ".txt", ".md", ".yaml", ".json"],
        description="List of allowed file extensions"
    )
    max_file_size_mb: int = Field(default=10, ge=1, le=100,
                                  description="Maximum file size to read in MB")


class TestRunnerToolConfig(ToolConfig):
    """Configuration for Test Runner Tool."""
    
    name: str = "TestRunnerTool"
    description: str = "Execute software tests"
    test_frameworks: List[str] = Field(
        default_factory=lambda: ["pytest", "unittest"],
        description="Supported test frameworks"
    )
    max_test_time: int = Field(default=300, ge=1,
                                description="Maximum time per test in seconds")
    parallel_tests: bool = Field(default=False,
                                 description="Run tests in parallel")


class LinterToolConfig(ToolConfig):
    """Configuration for Linter Tool."""
    
    name: str = "LinterTool"
    description: str = "Code linting and style checking"
    linters: List[str] = Field(
        default_factory=lambda: ["pylint", "flake8"],
        description="List of linters to use"
    )
    config_files: Dict[str, str] = Field(
        default_factory=lambda: {"pylint": ".pylintrc", "flake8": ".flake8"},
        description="Config files for each linter"
    )
    fail_on_error: bool = Field(default=True,
                                 description="Fail if linting errors found")


# =============================================================================
# Workflow Configuration Schemas
# =============================================================================

class WorkflowStepConfig(BaseModel):
    """Configuration for a workflow step."""
    
    name: str = Field(..., description="Step name")
    agent: str = Field(..., description="Agent to execute this step")
    description: str = Field(default="", description="Step description")
    timeout: Optional[int] = Field(default=None,
                                   description="Step timeout (overrides agent timeout)")
    retries: Optional[int] = Field(default=None,
                                  description="Retry count (overrides agent retries)")
    depends_on: List[str] = Field(
        default_factory=list,
        description="List of step names this step depends on"
    )
    inputs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Input parameters for the step"
    )


class WorkflowConfig(BaseModel):
    """Configuration for a workflow."""
    
    name: str = Field(..., description="Workflow name")
    description: str = Field(..., description="Workflow description")
    version: str = Field(default="1.0", description="Workflow version")
    steps: List[WorkflowStepConfig] = Field(
        ..., description="List of workflow steps"
    )
    parallel_steps: bool = Field(
        default=False,
        description="Allow parallel execution of independent steps"
    )


# =============================================================================
# Main Configuration Schema
# =============================================================================

class HarnessConfig(BaseModel):
    """Main configuration for the Harness Agentic Framework."""
    
    # Core
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    checkpointing: CheckpointConfig = Field(default_factory=CheckpointConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    
    # Agents
    god: GodAgentConfig = Field(default_factory=GodAgentConfig)
    planner: PlannerAgentConfig = Field(default_factory=PlannerAgentConfig)
    coder: CoderAgentConfig = Field(default_factory=CoderAgentConfig)
    reviewer: ReviewerAgentConfig = Field(default_factory=ReviewerAgentConfig)
    tester: TesterAgentConfig = Field(default_factory=TesterAgentConfig)
    debugger: DebuggerAgentConfig = Field(default_factory=DebuggerAgentConfig)
    researcher: ResearcherAgentConfig = Field(default_factory=ResearcherAgentConfig)
    documenter: DocumenterAgentConfig = Field(default_factory=DocumenterAgentConfig)
    
    # Tools
    shell: ShellToolConfig = Field(default_factory=ShellToolConfig)
    python: PythonToolConfig = Field(default_factory=PythonToolConfig)
    git: GitToolConfig = Field(default_factory=GitToolConfig)
    file_io: FileIOToolConfig = Field(default_factory=FileIOToolConfig)
    test_runner: TestRunnerToolConfig = Field(default_factory=TestRunnerToolConfig)
    linter: LinterToolConfig = Field(default_factory=LinterToolConfig)
    
    # Workflows
    workflows: Dict[str, WorkflowConfig] = Field(
        default_factory=dict,
        description="Named workflows"
    )


# =============================================================================
# Settings with Environment Variable Support
# =============================================================================

class Settings(BaseSettings):
    """
    Runtime settings for Harness Agentic Framework.
    
    Loads from environment variables and .env files.
    """
    
    # Core
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, ge=1, le=65535, description="Server port")
    environment: str = Field(default="development", description="Environment (development, staging, production)")
    debug: bool = Field(default=False, description="Enable debug mode")
    
    # Paths
    project_root: str = Field(default=".", description="Project root directory")
    logs_dir: str = Field(default="./logs", description="Logs directory")
    temp_dir: str = Field(default="./tmp", description="Temporary files directory")
    
    # Logging
    log_level: str = Field(default="INFO", description="Log level")
    log_format: str = Field(default="json", description="Log format")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
