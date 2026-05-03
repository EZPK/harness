"""
Harness Agentic Framework

A multi-agent system for software development with God Agent orchestration.
"""

__version__ = "0.1.0"

# Initialize logging configuration
from core.logging_config import setup_logging, get_logger

# Re-configure logging (in case this is imported after other modules)
setup_logging(level=20)  # INFO level by default
