#!/bin/bash

# - Run as a background process to avoid blocking the shell (for experiments)
#       nohup ./run_experiment_local.sh > experiment.log 2>&1 &
# - See which cores are being used by the processes
#      ps -e -o pid,psr,comm | grep python
#      htop


####  ----------------------------------------- ####
# Define the unexpected_interuption function
unexpected_interuption() {
    echo "The experiment has been interrupted unexpectedly (data won't be trustworthy). Killing processes..."
    echo "Stopping agent nodes..."
    for PID in "${AGENT_PIDS[@]}"; do
        kill $PID
    done
    echo "Stopping server node web server..."
    kill -SIGINT $SERVER_PID  # Send SIGINT to server node server
    wait $SERVER_PID  # Wait for the process to terminate
}
# Trap SIGINT and SIGTERM signals and call the cleanup function
trap unexpected_interuption SIGINT SIGTERM

# Function to check and enforce CPU affinity
check_and_enforce_affinity() {
    local PID=$1
    local EXPECTED_CORES=$2
    local CURRENT_AFFINITY=$(taskset -cp $PID | awk -F': ' '{print $2}')
    
    if [ "$CURRENT_AFFINITY" != "$EXPECTED_CORES" ]; then
        echo "Error: Process $PID is not running on expected core(s) $EXPECTED_CORES. Current affinity: $CURRENT_AFFINITY"
        kill -9 $PID
        exit 1
    fi
}
####  ----------------------------------------- ####


# Run from the root directory of this project
cd ../
DIR=$(pwd)
echo "Running experiment from $DIR"

# Activate the virtual environment
source .venv_linux/bin/activate

# Start the server node web server on CPU core 0
taskset -c 0 python -m network.server_node_web_server &  # Bind to core 0
SERVER_PID=$!
sleep 20 # Wait for the server node web server to start
echo "Server node web server with PID $SERVER_PID is running on core(s):"
taskset -cp $SERVER_PID

# Define total time to run the agents and problem instance to solve
TOTAL_TIME=7200   # 2 hours
PROBLEM_INSTANCE=glass-sc

# Start agent nodes on specific cores
NUM_AGENTS=5
START_CORE=1
AGENT_PIDS=() # To keep track of agent process IDs
for i in $(seq 1 $NUM_AGENTS); do
    CORE=$((START_CORE + i - 1))
    echo "Starting agent $i on core $CORE..."
    taskset -c $CORE python experiments/agent_behavior_many_agents_single_problem.py $TOTAL_TIME $PROBLEM_INSTANCE &
    AGENT_PID=$!
    AGENT_PIDS+=($AGENT_PID) # Record the PID of the agent
    sleep 1  # Allow process to start

    # Print and verify the CPU affinity of the newly started process
    echo "Agent $i (PID $AGENT_PID) is running on core(s):"
    taskset -cp $AGENT_PID
    check_and_enforce_affinity $AGENT_PID "$CORE"
done

# Use `wait` for all agent PIDs
# NOTE we need to wait for all agents to complete before killing the server node web server since agents send requests to the 
# web server on clean up, and as soon as any SIGINT is used in this shell script the uvicorn web server will stop, even if we 
# send to the agent node processes
echo "Waiting for agents to complete..."
for PID in "${AGENT_PIDS[@]}"; do
    wait $PID
done

# Cleanup - kill server node web server after agents have completed
echo "Experiment completed successfully. Cleaning up..."
kill -SIGINT $SERVER_PID  # Send SIGINT to server node server
wait $SERVER_PID  # Wait for the process to terminate