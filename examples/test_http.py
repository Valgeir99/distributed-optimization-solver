import time
import sys
import os
import threading

# Change the working directory to the root of the project
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)  # This changes the CWD to the root of the project
# Add the project root to sys.path to ensure Python can find the 'network' package
sys.path.append(project_root)

from network.agent_node import AgentNode
from network.central_node_server import start_server, stop_server

# Start the central node server in a separate thread
central_node_server_thread = start_server()

time.sleep(5)

agent1 = AgentNode("agent1")
agent1.download_problem_instance()

time.sleep(5)

# Download problem instance that does not exits
agent1.download_problem_instance_data_by_name("non_existent_problem_instance")

time.sleep(5)

agent1.print_problem_instances()

time.sleep(5)

# Clean up agent
agent1.clean_up()

# Stop the central node server
stop_server()
central_node_server_thread.join()