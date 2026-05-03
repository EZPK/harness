#!/usr/bin/env python3
"""
Run the Harness TUI.

This script starts the Terminal User Interface for the Harness Agentic Framework.
"""

import asyncio
import sys
import os

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tui.app import run_tui_sync


def main():
    """Main entry point."""
    print("Starting Harness TUI...")
    print("Press Ctrl+C to quit")
    
    try:
        run_tui_sync()
    except KeyboardInterrupt:
        print("\nShutting down...")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
