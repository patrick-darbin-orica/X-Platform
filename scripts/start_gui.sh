#!/bin/bash
# Start Flask GUI for X-Platform navigation monitoring.
#
# Usage:
#   ./scripts/start_gui.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Use the project venv
VENV_PATH=~/Amiga/X-Platform/venv
if [ ! -d "$VENV_PATH" ]; then
    echo "ERROR: venv not found at $VENV_PATH"
    exit 1
fi
source "$VENV_PATH/bin/activate"

cd "$REPO_ROOT"
python gui/app.py
