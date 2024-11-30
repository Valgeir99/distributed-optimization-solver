#!/bin/bash

# Define the cleanup function
cleanup() {
    echo "Stopping agent nodes..."
    for PID in "${AGENT_PIDS[@]}"; do
        kill $PID
    done
    echo "Stopping central node web server..."
    kill $CENTRAL_PID
    sleep 10
}

# Trap SIGINT and SIGTERM signals and call the cleanup function
trap cleanup SIGINT SIGTERM

# Run from the root directory of this project
cd ../
DIR=$(pwd)
echo "Running experiment from $DIR"

# Activate the virtual environment
source .venv_linux/bin/activate

# Start the central node web server on CPU core 0
taskset -c 0 python -m network.central_node_server &  # Bind to core 0
CENTRAL_PID=$!
sleep 10 # Wait for the central node web server to start

# Define total time to run the agents
TOTAL_TIME=300

# Start agent nodes on specific cores
NUM_AGENTS=3
START_CORE=1
AGENT_PIDS=() # To keep track of agent process IDs
for i in $(seq 1 $NUM_AGENTS); do
    CORE=$((START_CORE + i - 1))
    echo "Starting agent $i on core $CORE..."
    taskset -c $CORE python experiments/agent_experiment_1.py $TOTAL_TIME &
    AGENT_PIDS+=($!) # Record the PID of the agent
done

# Use `wait` for all agent PIDs
echo "Waiting for agents to complete..."
for PID in "${AGENT_PIDS[@]}"; do
    wait $PID
done

# Cleanup
cleanup