#!/bin/bash

# Get directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Error: venv directory not found. Please run 'python3 -m venv venv' first."
    exit 1
fi

# Create logs directory if not exists
mkdir -p logs

# Activate venv and run
source venv/bin/activate

echo "Starting Daily Data Download in background..."
# You can pass arguments like --date 2025-01-01 here if needed, but default is incremental
nohup python -u scripts/day_download_s_to_clickhouse.py >> logs/console_download.log 2>&1 &
PID=$!

echo "Downloader started with PID: $PID"
echo "Console output: logs/console_download.log"
echo "App logs: logs/download.log"
