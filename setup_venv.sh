#!/bin/bash
# Setup script for Harness Agentic Framework
# This script creates a virtual environment and installs all dependencies

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VENV_NAME=".venv"
PYTHON=${PYTHON:-python3}
INSTALL_ALL=${INSTALL_ALL:-false}
INSTALL_TUI=${INSTALL_TUI:-true}
INSTALL_DEV=${INSTALL_DEV:-false}

# Functions
echo_error() {
    echo -e "${RED}❌ $1${NC}"
}

echo_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

echo_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

echo_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Check if virtual environment exists
if [ -d "$VENV_NAME" ]; then
    echo_info "Virtual environment already exists ($VENV_NAME)"
else
    echo_info "Creating virtual environment in $VENV_NAME..."
    $PYTHON -m venv $VENV_NAME
    echo_success "Virtual environment created"
fi

# Activate virtual environment
source $VENV_NAME/bin/activate

# Upgrade pip
echo_info "Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
echo_success "pip upgraded"

# Install base dependencies
echo_info "Installing base dependencies..."
pip install -r requirements.txt > /dev/null 2>&1
echo_success "Base dependencies installed"

# Install TUI dependencies
if [ "$INSTALL_TUI" = true ]; then
    echo_info "Installing TUI dependencies..."
    pip install textual>=0.48.0 rich>=13.7.0 > /dev/null 2>&1
    echo_success "TUI dependencies installed"
fi

# Install dev dependencies
if [ "$INSTALL_DEV" = true ] || [ "$INSTALL_ALL" = true ]; then
    echo_info "Installing development dependencies..."
    pip install -r requirements-dev.txt > /dev/null 2>&1
    echo_success "Development dependencies installed"
fi

echo ""
echo_success "Setup complete!"
echo ""
echo_info "To activate the virtual environment:"
echo "  source $VENV_NAME/bin/activate"
echo ""
echo_info "To run the TUI:"
echo "  python -m harness.tui.app"
echo "  or: ./scripts/run_tui.py"
echo ""
echo_info "To deactivate:"
echo "  deactivate"
