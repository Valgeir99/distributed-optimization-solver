import time
import sys
import os
import threading

from network.agent_node import AgentNode
from network.central_node_server import start_server

# Start the central node server in a separate thread
threading.Thread(target=start_server, daemon=True).start()

time.sleep(5)

agent1 = AgentNode("agent1")
agent1.download_problem_instance()

time.sleep(5)

agent1.clean_up()