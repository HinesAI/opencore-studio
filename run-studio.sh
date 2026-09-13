#!/usr/bin/env bash
# OpenCore Studio — Launch Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=8088

echo "=========================================================="
echo " Starting OpenCore Studio Desktop Engine..."
echo " Project Directory: ${SCRIPT_DIR}"
echo "=========================================================="

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required to run OpenCore Studio."
    exit 1
fi

# Run backend server
python3 "${SCRIPT_DIR}/app.py" --host 0.0.0.0 --port "${PORT}"
