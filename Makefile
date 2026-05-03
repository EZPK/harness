# Makefile for Harness Agentic Framework
# 
# Usage:
#   make help           - Show this help
#   make venv           - Create virtual environment
#   make install        - Install dependencies
#   make install-dev    - Install dev dependencies
#   make install-tui    - Install TUI dependencies (textual)
#   make install-ts     - Install TypeScript dependencies
#   make install-llm    - Install LLM provider dependencies
#   make install-all    - Install all dependencies
#   make test           - Run tests
#   make run            - Run the TUI
#   make run-tui        - Run the TUI application
#   make run-ts         - Run the TypeScript application
#   make run-all        - Run both Python and TypeScript applications
#   make build-ts       - Build TypeScript project
#   make lint           - Run linter
#   make clean          - Clean build artifacts
#   make clean-all      - Remove venv and all build artifacts

.PHONY: help venv install install-dev install-tui install-ts install-llm install-all test run run-tui run-ts run-all build-ts lint clean clean-all

# Configuration
PYTHON := python3
VENV_NAME := .venv
VENV_PATH := $(VENV_NAME)
REQUIREMENTS := requirements.txt
DEV_REQUIREMENTS := requirements-dev.txt
PROJECT_DIR := $(shell pwd)
TS_DIR := $(PROJECT_DIR)/harness-ts

# Default target
help:
	@echo "Harness Agentic Framework - Makefile"
	@echo "==================================="
	@echo ""
	@echo "Setup:"
	@echo "  make venv              # Create virtual environment"
	@echo "  make install           # Install base dependencies"
	@echo "  make install-dev       # Install dev dependencies"
	@echo "  make install-tui       # Install TUI dependencies"
	@echo "  make install-ts        # Install TypeScript dependencies"
	@echo "  make install-llm       # Install LLM provider dependencies"
	@echo "  make install-all       # Install all dependencies"
	@echo ""
	@echo "Run:"
	@echo "  make run               # Run the TUI"
	@echo "  make run-tui           # Run the TUI application"
	@echo "  make run-ts            # Run the TypeScript application"
	@echo "  make run-all           # Run both Python and TypeScript"
	@echo ""
	@echo "Build:"
	@echo "  make build-ts          # Build TypeScript project"
	@echo ""
	@echo "LLM Setup:"
	@echo "  make setup-llm         # Configure LLM providers"
	@echo ""
	@echo "Test & Quality:"
	@echo "  make test              # Run tests"
	@echo "  make lint              # Run linter"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean             # Clean build artifacts"
	@echo "  make clean-all         # Remove venv and all build artifacts"
	@echo ""
	@echo "Environment:"
	@echo "  VENV: $(VENV_PATH)"
	@echo "  Python: $(PYTHON)"
	@echo "  TypeScript: $(TS_DIR)"

# Create virtual environment
venv:
	@echo "Creating virtual environment in $(VENV_PATH)..."
	$(PYTHON) -m venv $(VENV_PATH)
	@echo "Virtual environment created."
	@echo "Activate with: source $(VENV_PATH)/bin/activate"

# Install base dependencies
install:
	@echo "Installing base dependencies..."
	if [ -d "$(VENV_PATH)" ]; then \
		. $(VENV_PATH)/bin/activate && pip install -r $(REQUIREMENTS); \
	else \
		$(PYTHON) -m pip install -r $(REQUIREMENTS); \
	fi
	@echo "Base dependencies installed."

# Install development dependencies
install-dev:
	@echo "Installing development dependencies..."
	if [ -d "$(VENV_PATH)" ]; then \
		. $(VENV_PATH)/bin/activate && pip install -r $(DEV_REQUIREMENTS); \
	else \
		$(PYTHON) -m pip install -r $(DEV_REQUIREMENTS); \
	fi
	@echo "Development dependencies installed."

# Install TUI dependencies
install-tui:
	@echo "Installing TUI dependencies (textual, rich)..."
	if [ -d "$(VENV_PATH)" ]; then \
		. $(VENV_PATH)/bin/activate && pip install textual>=0.48.0 rich>=13.7.0; \
	else \
		$(PYTHON) -m pip install textual>=0.48.0 rich>=13.7.0; \
	fi
	@echo "TUI dependencies installed."

# Install TypeScript dependencies
install-ts:
	@echo "Installing TypeScript dependencies..."
	cd $(TS_DIR) && npm install
	@echo "TypeScript dependencies installed."

# Install LLM provider dependencies
install-llm:
	@echo "Installing LLM provider dependencies..."
	if [ -d "$(VENV_PATH)" ]; then \
		. $(VENV_PATH)/bin/activate && pip install litellm httpx; \
	else \
		$(PYTHON) -m pip install litellm httpx; \
	fi
	@echo "LLM provider dependencies installed."
	@echo ""
	@echo "Supported providers:"
	@echo "  - Mistral: pip install litellm (for mistral-large, mistral-small, mixtral)"
	@echo "  - OpenAI: pip install litellm (for gpt-4, gpt-3.5-turbo)"
	@echo "  - Anthropic: pip install litellm (for claude-3, claude-2)"
	@echo "  - Google: pip install litellm (for gemini-pro)"
	@echo "  - Local: pip install litellm (for ollama, vllm, etc.)"

# Install all dependencies
install-all: venv install install-dev install-tui install-ts install-llm
	@echo "All dependencies installed."

# Build TypeScript project
build-ts:
	@echo "Building TypeScript project..."
	cd $(TS_DIR) && npm run build
	@echo "TypeScript build complete."

# Run tests
test:
	@echo "Running tests..."
	if [ -d "$(VENV_PATH)" ]; then \
		. $(VENV_PATH)/bin/activate && cd $(PROJECT_DIR) && python -c "import sys; sys.path.insert(0, '.'); import pytest; pytest.main(['-v', 'tests/'])"; \
	else \
		cd $(PROJECT_DIR) && $(PYTHON) -c "import sys; sys.path.insert(0, '.'); import pytest; pytest.main(['-v', 'tests/'])"; \
	fi

# Run the TUI
run: run-tui

# Run the TUI application
run-tui:
	@echo "Starting Harness TUI..."
	@echo "Press Ctrl+C to quit"
	if [ -d "$(VENV_PATH)" ]; then \
		. $(VENV_PATH)/bin/activate && cd $(PROJECT_DIR) && python -c "import sys; sys.path.insert(0, '.'); from tui.app import run_tui_sync; run_tui_sync()"; \
	else \
		cd $(PROJECT_DIR) && $(PYTHON) -c "import sys; sys.path.insert(0, '.'); from tui.app import run_tui_sync; run_tui_sync()"; \
	fi

# Run TypeScript application
run-ts:
	@echo "Starting Harness-TS..."
	@echo "Press Ctrl+C to quit"
	cd $(TS_DIR) && npm run start

# Run both Python and TypeScript applications in parallel
run-all:
	@echo "Starting Harness full stack (Python + TypeScript)..."
	@echo "Press Ctrl+C to stop both applications"
	@echo ""
	@echo "Python TUI will run on this terminal."
	@echo "TypeScript will run in the background. Logs: harness-ts/ts-output.log"
	# Start TypeScript in background, redirect output to log file
	cd $(TS_DIR) && npm run start > $(TS_DIR)/ts-output.log 2>&1 &
	TS_PID=$$!
	@echo "TypeScript started (PID: $$TS_PID), logs: $(TS_DIR)/ts-output.log"
	@echo ""
	# Run Python TUI in foreground
	if [ -d "$(VENV_PATH)" ]; then \
		. $(VENV_PATH)/bin/activate && cd $(PROJECT_DIR) && python -c "import sys; sys.path.insert(0, '.'); from tui.app import run_tui_sync; run_tui_sync()"; \
	else \
		cd $(PROJECT_DIR) && $(PYTHON) -c "import sys; sys.path.insert(0, '.'); from tui.app import run_tui_sync; run_tui_sync()"; \
	fi
	# When Python exits, stop TypeScript
	kill $$TS_PID 2>/dev/null || true
	wait $$TS_PID 2>/dev/null || true

# Run with script
run-script:
	@echo "Starting Harness TUI via script..."
	if [ -d "$(VENV_PATH)" ]; then \
		. $(VENV_PATH)/bin/activate && cd $(PROJECT_DIR) && python ./scripts/run_tui.py; \
	else \
		cd $(PROJECT_DIR) && $(PYTHON) ./scripts/run_tui.py; \
	fi

# Setup LLM providers
setup-llm:
	@echo "Setting up LLM providers..."
	if [ -d "$(VENV_PATH)" ]; then \
		. $(VENV_PATH)/bin/activate && cd $(PROJECT_DIR) && python ./scripts/setup_llm.py; \
	else \
		cd $(PROJECT_DIR) && $(PYTHON) ./scripts/setup_llm.py; \
	fi

# Run linter
lint:
	@echo "Running linter..."
	if [ -d "$(VENV_PATH)" ]; then \
		. $(VENV_PATH)/bin/activate && cd $(PROJECT_DIR) && python -c "import sys; sys.path.insert(0, '.'); import pylint; pylint.main(['.'])"; \
	else \
		cd $(PROJECT_DIR) && $(PYTHON) -c "import sys; sys.path.insert(0, '.'); import pylint; pylint.main(['.'])"; \
	fi

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name ".pytest_cache" -delete 2>/dev/null || true
	# Clean TypeScript build artifacts
	cd $(TS_DIR) && rm -rf dist 2>/dev/null || true
	find $(TS_DIR) -name "*.js.map" -delete 2>/dev/null || true
	@echo "Build artifacts cleaned."

# Clean everything (including venv)
clean-all: clean
	@echo "Removing virtual environment..."
	rm -rf $(VENV_PATH)
	@echo "Cleaning TypeScript node_modules..."
	rm -rf $(TS_DIR)/node_modules
	@echo "Everything cleaned."
