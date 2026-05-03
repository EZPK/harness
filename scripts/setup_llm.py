#!/usr/bin/env python3
"""
LLM Setup Script.

Configure and test LLM providers for the Harness Agentic Framework.

Usage:
    # Configure via environment variables
    export MISTRAL_API_KEY="your_key"
    python scripts/setup_llm.py
    
    # Or configure programmatically
    python scripts/setup_llm.py --provider mistral --api-key your_key
    
    # Test a provider
    python scripts/setup_llm.py --test --provider mistral
"""

import argparse
import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def print_header(title: str) -> None:
    """Print a formatted header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


async def test_provider(provider_name: str) -> None:
    """Test a registered provider."""
    from providers import get_provider, LLMMessage, MessageRole
    
    provider = get_provider(provider_name)
    if provider is None:
        print(f"❌ Provider '{provider_name}' not found!")
        return
    
    print(f"Testing provider: {provider}")
    
    try:
        # Simple test
        response = await provider.complete(
            "Explain the concept of artificial intelligence in 3 sentences.",
            temperature=0.7
        )
        
        print(f"\n✅ Success!")
        print(f"   Model: {response.model}")
        print(f"   Provider: {response.provider}")
        print(f"   Content preview: {response.content[:100]}...")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")


async def test_all_providers() -> None:
    """Test all registered providers."""
    from providers import get_registry
    
    registry = get_registry()
    providers = registry.list_providers()
    
    if not providers:
        print("No providers registered!")
        return
    
    print_header("Testing All Registered Providers")
    
    for name, provider in providers.items():
        print(f"\n📡 Testing: {name}")
        try:
            response = await provider.complete("Say 'Hello' in French.")
            print(f"   ✅ {name}: {response.content}")
        except Exception as e:
            print(f"   ❌ {name}: {e}")


def configure_from_env() -> None:
    """Configure providers from environment variables."""
    from providers import (
        MistralProvider,
        OpenAIProvider,
        AnthropicProvider,
        LiteLLMProvider,
        register_provider,
    )
    
    print_header("Configuring Providers from Environment")
    
    configured = []
    
    # Mistral
    mistral_key = os.getenv("MISTRAL_API_KEY")
    if mistral_key:
        provider = MistralProvider(
            model="mistral-large",
            api_key=mistral_key
        )
        register_provider("mistral-large", provider, as_default=True)
        configured.append("Mistral")
        print("✅ Mistral provider configured")
    
    # OpenAI
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        provider = OpenAIProvider(
            model="gpt-4",
            api_key=openai_key
        )
        register_provider("gpt-4", provider)
        configured.append("OpenAI")
        print("✅ OpenAI provider configured")
    
    # Anthropic
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        provider = AnthropicProvider(
            model="claude-3-sonnet-20240229",
            api_key=anthropic_key
        )
        register_provider("claude-3-sonnet", provider)
        configured.append("Anthropic")
        print("✅ Anthropic provider configured")
    
    if not configured:
        print("⚠️  No API keys found in environment variables.")
        print("   Set MISTRAL_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY.")
        print("   Or use: --api-key YOUR_KEY")
    
    return len(configured) > 0


def configure_programmatically(provider: str, api_key: str, **kwargs) -> None:
    """Configure a provider programmatically."""
    from providers import (
        MistralProvider,
        OpenAIProvider,
        AnthropicProvider,
        LiteLLMProvider,
        register_provider,
        ProviderType,
    )
    
    print_header(f"Configuring {provider} Provider")
    
    # Detect provider type
    if provider.lower() in ["mistral", "mistral-large", "mistral-small", "mixtral"]:
        llm_provider = MistralProvider(
            model=provider,
            api_key=api_key,
            **kwargs
        )
    elif provider.lower() in ["gpt-4", "gpt-3.5", "gpt-3", "openai"]:
        llm_provider = OpenAIProvider(
            model=provider,
            api_key=api_key,
            **kwargs
        )
    elif provider.lower() in ["claude", "claude-3", "anthropic"]:
        llm_provider = AnthropicProvider(
            model=provider,
            api_key=api_key,
            **kwargs
        )
    else:
        # Use LiteLLM for any other provider
        llm_provider = LiteLLMProvider(
            model=provider,
            api_key=api_key,
            **kwargs
        )
    
    register_provider(provider, llm_provider, as_default=True)
    print(f"✅ {provider} provider configured and set as default")


def list_providers() -> None:
    """List all registered providers."""
    from providers import get_registry
    
    registry = get_registry()
    providers = registry.list_providers()
    
    print_header("Registered LLM Providers")
    
    if not providers:
        print("No providers registered.")
        return
    
    default_name = registry._default_provider
    
    for name, provider in providers.items():
        is_default = " (DEFAULT)" if name == default_name else ""
        print(f"  • {name}: {provider.model} ({provider.provider_type.value}){is_default}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Configure and test LLM providers for Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Configure from environment variables
  export MISTRAL_API_KEY="your_key"
  python scripts/setup_llm.py

  # Configure programmatically
  python scripts/setup_llm.py --provider mistral-large --api-key your_key

  # Test a provider
  python scripts/setup_llm.py --test --provider mistral-large

  # List providers
  python scripts/setup_llm.py --list
        """
    )
    
    parser.add_argument(
        "--provider", "-p",
        type=str,
        default=None,
        help="Provider name or model (e.g., mistral-large, gpt-4, claude-3-sonnet)"
    )
    
    parser.add_argument(
        "--api-key", "-k",
        type=str,
        default=None,
        help="API key for the provider"
    )
    
    parser.add_argument(
        "--test", "-t",
        action="store_true",
        help="Test the configured provider"
    )
    
    parser.add_argument(
        "--test-all",
        action="store_true",
        help="Test all registered providers"
    )
    
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all registered providers"
    )
    
    parser.add_argument(
        "--model", "-m",
        type=str,
        default=None,
        help="Model identifier (defaults to provider name)"
    )
    
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Default temperature for the provider"
    )
    
    args = parser.parse_args()
    
    # List providers
    if args.list:
        list_providers()
        return
    
    # Configure from environment first
    if not (args.provider or args.api_key or args.test or args.test_all):
        # Try to configure from environment
        if configure_from_env():
            list_providers()
        else:
            parser.print_help()
        return
    
    # Configure programmatically
    if args.provider and args.api_key:
        model = args.model or args.provider
        configure_programmatically(
            args.provider,
            args.api_key,
            temperature=args.temperature
        )
        list_providers()
    
    # Test provider
    if args.test and args.provider:
        asyncio.run(test_provider(args.provider))
    
    # Test all providers
    if args.test_all:
        asyncio.run(test_all_providers())


if __name__ == "__main__":
    main()
