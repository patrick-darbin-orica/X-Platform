#!/bin/bash
# Standalone collar detection script launcher.
# Runs vision/detector.py in headless mode.
#
# Usage:
#   ./scripts/detect.sh [--config PATH]

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

# ARM TLS workaround — preload libgomp to avoid TLS allocation errors on
# Jetson / ARM platforms when depthai loads.
GOMP_LIB=$(find "$VENV_PATH" -name "libgomp*.so*" 2>/dev/null | head -1)
if [ -n "$GOMP_LIB" ]; then
    export LD_PRELOAD="$GOMP_LIB"
    echo "LD_PRELOAD set to $GOMP_LIB"
fi

echo "Starting collar detector (headless)..."
DETECTION_HEADLESS=1 python "$REPO_ROOT/vision/detector.py" "$@"
