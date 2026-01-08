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

echo "Starting Testnet Simulation in background..."
nohup python -u testnet/run_simulation.py >> logs/console_sim.log 2>&1 &
PID=$!

echo "Simulation started with PID: $PID"
echo "Console output: logs/console_sim.log"
echo "App logs: logs/live_bot.log"
