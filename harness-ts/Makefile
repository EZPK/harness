# Makefile for Harness-TS
# TypeScript Edition of Harness Agentic Framework

.PHONY: help install install-dev build build-watch lint lint-fix format format-check test test-watch test-coverage start start-tui dev dev-tui clean clean-all

# Configuration
NODE := node
NPM := npm
PROJECT_DIR := $(shell pwd)
DIST_DIR := dist
SRC_DIR := src

# Default target
default: help

help:
	@echo "Harness-TS - Makefile"
	@echo "===================="
	@echo ""
	@echo "Setup:"
	@echo "  make install           # Install production dependencies"
	@echo "  make install-dev       # Install development dependencies"
	@echo ""
	@echo "Build:"
	@echo "  make build             # Build TypeScript project"
	@echo "  make build-watch       # Build with watch mode"
	@echo ""
	@echo "Quality:"
	@echo "  make lint              # Run ESLint"
	@echo "  make lint-fix          # Fix ESLint issues"
	@echo "  make format            # Format code with Prettier"
	@echo "  make format-check      # Check code formatting"
	@echo ""
	@echo "Test:"
	@echo "  make test              # Run all tests"
	@echo "  make test-watch        # Run tests in watch mode"
	@echo "  make test-coverage     # Run tests with coverage"
	@echo ""
	@echo "Run:"
	@echo "  make start             # Start the application"
	@echo "  make start-tui         # Start the TUI"
	@echo "  make dev               # Run with ts-node (dev)"
	@echo "  make dev-tui           # Run TUI with ts-node (dev)"
	@echo ""
	@echo "Clean:"
	@echo "  make clean             # Clean build artifacts"
	@echo "  make clean-all         # Clean all (including node_modules)"

# Install dependencies
install:
	@echo "Installing production dependencies..."
	$(NPM) install --production
	@echo "Done."

install-dev:
	@echo "Installing development dependencies..."
	$(NPM) install
	@echo "Done."

# Build
build:
	@echo "Building TypeScript project..."
	$(NPM) run build
	@echo "Build complete."

build-watch:
	@echo "Building with watch mode..."
	$(NPM) run build:watch

# Lint
lint:
	@echo "Running ESLint..."
	$(NPM) run lint

lint-fix:
	@echo "Fixing ESLint issues..."
	$(NPM) run lint:fix

# Format
format:
	@echo "Formatting code..."
	$(NPM) run format

format-check:
	@echo "Checking code format..."
	$(NPM) run format:check

# Test
test:
	@echo "Running tests..."
	$(NPM) run test

test-watch:
	@echo "Running tests in watch mode..."
	$(NPM) run test:watch

test-coverage:
	@echo "Running tests with coverage..."
	$(NPM) run test:coverage

# Run
start:
	@echo "Starting Harness-TS..."
	$(NPM) run start

start-tui:
	@echo "Starting Harness-TS TUI..."
	$(NPM) run start:tui

dev:
	@echo "Running Harness-TS with ts-node (dev)..."
	$(NPM) run dev

dev-tui:
	@echo "Running Harness-TS TUI with ts-node (dev)..."
	$(NPM) run dev:tui

# Clean
clean:
	@echo "Cleaning build artifacts..."
	rm -rf $(DIST_DIR)
	find . -name "*.js.map" -delete 2>/dev/null || true
	find . -name "*.js" -path "./$(DIST_DIR)/*" -delete 2>/dev/null || true
	@echo "Clean complete."

clean-all: clean
	@echo "Removing node_modules..."
	rm -rf node_modules
	@echo "Clean all complete."
