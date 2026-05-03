#!/usr/bin/env python3
"""
Run Harness TUI with LLM Provider.

This script demonstrates how to configure and run the TUI with an LLM backend.

Usage:
    # Using environment variables
    export MISTRAL_API_KEY="your_key"
    python scripts/run_tui_with_llm.py
    
    # With command-line arguments
    python scripts/run_tui_with_llm.py --provider mistral-large --api-key your_key
    
    # With LiteLLM (auto-detects provider from model name)
    python scripts/run_tui_with_llm.py --model mistral-large --api-key your_key
"""

import argparse
import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def configure_llm_from_args(args) -> None:
    """Configure LLM provider from command-line arguments."""
    from providers import (
        MistralProvider,
        OpenAIProvider,
        AnthropicProvider,
        LiteLLMProvider,
        register_provider,
    )
    
    provider_name = args.provider or args.model
    api_key = args.api_key or os.getenv("MISTRAL_API_KEY") or os.getenv("OPENAI_API_KEY")
    
    if not provider_name:
        print("Error: No provider specified. Use --provider or --model.")
        sys.exit(1)
    
    if not api_key:
        print("Error: No API key provided. Use --api-key or set MISTRAL_API_KEY/OPENAI_API_KEY.")
        sys.exit(1)
    
    # Detect provider type
    provider_lower = provider_name.lower()
    
    if any(x in provider_lower for x in ["mistral", "mixtral"]):
        provider = MistralProvider(
            model=provider_name,
            api_key=api_key,
            temperature=args.temperature
        )
    elif any(x in provider_lower for x in ["gpt-", "openai"]):
        provider = OpenAIProvider(
            model=provider_name,
            api_key=api_key,
            temperature=args.temperature
        )
    elif any(x in provider_lower for x in ["claude", "anthropic"]):
        provider = AnthropicProvider(
            model=provider_name,
            api_key=api_key,
            temperature=args.temperature
        )
    else:
        # Use LiteLLM for any other provider
        provider = LiteLLMProvider(
            model=provider_name,
            api_key=api_key,
            temperature=args.temperature
        )
    
    register_provider(provider_name, provider, as_default=True)
    print(f"✅ Configured {provider_name} as default LLM provider")


def configure_llm_from_env() -> bool:
    """Configure LLM provider from environment variables. Returns True if configured."""
    from providers import (
        MistralProvider,
        OpenAIProvider,
        AnthropicProvider,
        register_provider,
    )
    from providers.openai_compatible import OpenAICompatibleProvider
    
    configured = False
    
    # Try Ollama (local LLM)
    ollama_model = os.getenv("OLLAMA_MODEL")
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    if ollama_model:
        provider = OpenAICompatibleProvider(
            model=ollama_model,
            api_key="",  # Ollama doesn't need API key
            api_base_url=ollama_url,
        )
        provider_name = f"ollama/{ollama_model}"
        register_provider(provider_name, provider, as_default=True)
        print(f"✅ Configured Ollama LLM provider ({ollama_model}) from environment")
        configured = True
    
    # Try Mistral
    if not configured:
        mistral_key = os.getenv("MISTRAL_API_KEY")
        if mistral_key:
            provider = MistralProvider(
                model="mistral-large",
                api_key=mistral_key
            )
            register_provider("mistral-large", provider, as_default=True)
            print("✅ Configured Mistral LLM provider from environment")
            configured = True
    
    # Try OpenAI
    if not configured:
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            provider = OpenAIProvider(
                model="gpt-4",
                api_key=openai_key
            )
            register_provider("gpt-4", provider, as_default=True)
            print("✅ Configured OpenAI LLM provider from environment")
            configured = True
    
    # Try Anthropic
    if not configured:
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            provider = AnthropicProvider(
                model="claude-3-sonnet-20240229",
                api_key=anthropic_key
            )
            register_provider("claude-3-sonnet", provider, as_default=True)
            print("✅ Configured Anthropic LLM provider from environment")
            configured = True
    
    return configured


async def run_tui():
    """Run the TUI with LLM support."""
    from agents.god.agent import GodAgent
    from agents.specialists.llm_agent import LLMAgent
    from providers import get_registry
    from tui.app import run_tui_sync
    
    # Get provider registry
    registry = get_registry()
    default_provider = registry.get_default()
    
    if default_provider is None:
        print("⚠️  Warning: No LLM provider configured. Using mock provider.")
        print("   Set MISTRAL_API_KEY or OPENAI_API_KEY environment variable.")
        print("   Or use --provider and --api-key arguments.")
    
    # Create God Agent
    god = GodAgent()
    
    # Add LLM Agent if provider is configured
    if default_provider is not None:
        llm_agent = LLMAgent(
            name="LLMAgent",
            provider=default_provider,
            system_prompt="""
            You are a helpful AI assistant in the Harness Agentic Framework.
            You assist with coding, analysis, planning, and any other tasks.
            Always respond in French if the user writes in French.
            Be concise and helpful.
            """
        )
        # Initialize the agent first
        await llm_agent.initialize()
        # Register (async method)
        await god.agent_registry.register(llm_agent)
        print(f"✅ Registered LLMAgent with {default_provider.model} provider")
    
    # Run TUI (sync)
    run_tui_sync(god)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run Harness TUI with LLM provider",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using environment variable
  export MISTRAL_API_KEY="your_key"
  python scripts/run_tui_with_llm.py

  # With command-line arguments
  python scripts/run_tui_with_llm.py --provider mistral-large --api-key your_key

  # With OpenAI
  python scripts/run_tui_with_llm.py --provider gpt-4 --api-key your_openai_key

  # With Anthropic
  python scripts/run_tui_with_llm.py --provider claude-3-sonnet --api-key your_anthropic_key
        """
    )
    
    parser.add_argument(
        "--provider", "-p",
        type=str,
        default=None,
        help="Provider name (e.g., mistral-large, gpt-4, claude-3-sonnet)"
    )
    
    parser.add_argument(
        "--model", "-m",
        type=str,
        default=None,
        help="Model identifier (alternative to --provider)"
    )
    
    parser.add_argument(
        "--api-key", "-k",
        type=str,
        default=None,
        help="API key for the provider"
    )
    
    parser.add_argument(
        "--temperature", "-t",
        type=float,
        default=0.7,
        help="Sampling temperature (default: 0.7)"
    )
    
    args = parser.parse_args()
    
    # Configure LLM
    if args.provider or args.model or args.api_key:
        configure_llm_from_args(args)
    elif configure_llm_from_env():
        pass  # Already configured from environment
    else:
        print("⚠️  No LLM provider configured.")
        print("   The TUI will run without LLM support.")
        print("   To enable LLM:")
        print("     - Set MISTRAL_API_KEY or OPENAI_API_KEY environment variable")
        print("     - Or use --provider and --api-key arguments")
    
    # Run TUI
    asyncio.run(run_tui())


if __name__ == "__main__":
    main()
