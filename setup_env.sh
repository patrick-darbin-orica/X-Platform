#!/bin/bash
# Setup script for X-Platform development environment

set -e

echo "=========================================="
echo "X-Platform Environment Setup"
echo "=========================================="

# Use the existing amiga-adk venv
VENV_PATH=~/Amiga/amiga-adk/venv

if [ ! -d "$VENV_PATH" ]; then
    echo "Error: amiga-adk venv not found at $VENV_PATH"
    echo "Please install farm-ng amiga-adk first"
    exit 1
fi

echo ""
echo "Activating amiga-adk virtual environment..."
source $VENV_PATH/bin/activate

echo ""
echo "Installing missing dependencies..."
pip install pydantic pyyaml --quiet

echo ""
echo "Verifying installation..."
python3 -c "import pydantic; print('✓ Pydantic:', pydantic.__version__)"
python3 -c "import yaml; print('✓ PyYAML:', yaml.__version__)"
python3 -c "from farm_ng.core.event_client import EventClient; print('✓ farm-ng SDK: OK')"

echo ""
echo "=========================================="
echo "✓ Environment setup complete!"
echo "=========================================="
echo ""
echo "To activate this environment, run:"
echo "  source ~/Amiga/amiga-adk/venv/bin/activate"
echo ""
echo "Then run X-Platform with:"
echo "  python3 main.py --config ~/Amiga/xstem/config/navigation_config.yaml"
echo ""
