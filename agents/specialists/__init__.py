"""
Specialist Agents Module.

Contains specialist agent implementations for the Harness Agentic Framework.
"""

# Import specialist agents lazily to avoid circular dependencies
# from .planner import PlannerAgent
# from .coder import CoderAgent
# from .reviewer import ReviewerAgent
# from .tester import TesterAgent
# from .debugger import DebuggerAgent
# from .researcher import ResearcherAgent
# from .documenter import DocumenterAgent
from .llm_agent import LLMAgent

__all__ = [
    "LLMAgent",
]