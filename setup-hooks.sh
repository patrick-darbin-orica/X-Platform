#!/bin/bash
# Setup script to install git hooks and configure commit template
# Run this script after cloning the repository

set -e

REPO_ROOT=$(git rev-parse --show-toplevel)
HOOKS_DIR="$REPO_ROOT/.git/hooks"
TEMPLATE_FILE="$REPO_ROOT/.gitmessage"

echo "Setting up git hooks and commit template for XStem..."

# Install prepare-commit-msg hook
if [ -f "$REPO_ROOT/.git-hooks/prepare-commit-msg" ]; then
    cp "$REPO_ROOT/.git-hooks/prepare-commit-msg" "$HOOKS_DIR/prepare-commit-msg"
    chmod +x "$HOOKS_DIR/prepare-commit-msg"
    echo "✓ Installed prepare-commit-msg hook"
else
    echo "✗ Error: .git-hooks/prepare-commit-msg not found"
    exit 1
fi

# Configure git to use the commit template
if [ -f "$TEMPLATE_FILE" ]; then
    git config commit.template "$TEMPLATE_FILE"
    echo "✓ Configured commit template: $TEMPLATE_FILE"
else
    echo "✗ Error: .gitmessage not found"
    exit 1
fi

echo ""
echo "Setup complete! The commit template will now be used for all commits."
echo "To see the template, run: git commit (without -m flag)"
echo ""
echo "Note: Other contributors will need to run this script after cloning."
