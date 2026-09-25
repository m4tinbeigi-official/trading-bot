#!/usr/bin/env bash
# Rick Sanchez MT5 Quant Suite Runner
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    /Users/ricksabchez/.local/bin/uv venv .venv
    /Users/ricksabchez/.local/bin/uv pip install --python .venv/bin/python pyzmq aiohttp fastapi uvicorn websockets
fi

echo "=================================================="
echo "⚡ Launching Rick Sanchez MT5 Quant Suite..."
echo "🌐 Web Dashboard: http://localhost:8080"
echo "=================================================="
exec .venv/bin/python main.py
