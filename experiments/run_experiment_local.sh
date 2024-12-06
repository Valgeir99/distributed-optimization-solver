#!/bin/bash

# Define the unexpected_interuption function
unexpected_interuption() {
    echo "The experiment has been interrupted unexpectedly (data won't be trustworthy). Killing processes..."
    echo "Stopping agent nodes..."
    for PID in "${AGENT_PIDS[@]}"; do
        kill $PID
    done
    echo "Stopping central node web server..."
    kill -SIGINT $CENTRAL_PID  # Send SIGINT to central node server
    wait $CENTRAL_PID  # Wait for the process to terminate
}

# Trap SIGINT and SIGTERM signals and call the cleanup function
trap unexpected_interuption SIGINT SIGTERM

# Run from the root directory of this project
cd ../
DIR=$(pwd)
echo "Running experiment from $DIR"

# Activate the virtual environment
source .venv_linux/bin/activate

# Start the central node web server on CPU core 0
taskset -c 0 python -m network.central_node_server &  # Bind to core 0
CENTRAL_PID=$!
echo "Central node web server with PID $CENTRAL_PID is running on core(s):"
taskset -cp $CENTRAL_PID
sleep 10 # Wait for the central node web server to start

# Define total time to run the agents
TOTAL_TIME=600

# Start agent nodes on specific cores
NUM_AGENTS=4
START_CORE=1
AGENT_PIDS=() # To keep track of agent process IDs
for i in $(seq 1 $NUM_AGENTS); do
    CORE=$((START_CORE + i - 1))
    echo "Starting agent $i on core $CORE..."
    taskset -c $CORE python experiments/agent_experiment_single_problem.py $TOTAL_TIME &
    AGENT_PID=$!
    AGENT_PIDS+=($AGENT_PID) # Record the PID of the agent
    # Print the CPU affinity of the newly started process
    echo "Agent $i (PID $AGENT_PID) is running on core(s):"
    taskset -cp $AGENT_PID
done

# Use `wait` for all agent PIDs
# NOTE we need to wait for all agents to complete before killing the central node web server since agents send requests to the 
# web server on clean up, and as soon as any SIGINT is used in this shell script the uvicorn web server will stop, even if we 
# send to the agent node processes
echo "Waiting for agents to complete..."
for PID in "${AGENT_PIDS[@]}"; do
    wait $PID
done

# Cleanup - kill central node web server after agents have completed
echo "Experiment completed successfully. Cleaning up..."
kill -SIGINT $CENTRAL_PID  # Send SIGINT to central node server
wait $CENTRAL_PID  # Wait for the process to terminate