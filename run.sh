#!/bin/bash
# Start NOCTURNE application with proper Python virtual environment
# Usage: ./run.sh [dev|build]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Ensure virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Run the Python script with any passed arguments
python run.py "$@"
