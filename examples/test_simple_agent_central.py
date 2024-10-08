import time
import sys
import os

sys.path.insert(0, '..')
#sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from network.agent_node import AgentNode
from network.central_node import CentralNode

try:

    central_node = CentralNode("127.0.0.1", 10000, "../database/central_node.db", "1")
    central_node.start()

    time.sleep(5)

    agent1 = AgentNode("127.0.0.1", 10001, "2")
    agent1.start()

    time.sleep(5)

    agent1.connect_to_central_node("127.0.0.1", 10000, "instance_1")

    result = central_node.query_db("SELECT * FROM central_nodes")
    print(result)
    result = central_node.query_db("SELECT * FROM agent_nodes")
    print(result)
    result = central_node.query_db("SELECT * FROM connections")
    print(result)

    time.sleep(5)

    print("central node connections:", central_node.connections)
    print("agent1 node connection:", agent1.connections)



except KeyboardInterrupt:
    print("\nKeyboardInterrupt received. Shutting down...")


finally:
    time.sleep(1)
    print("ENDING")
    if agent1 is not None:
        agent1.stop()
        agent1.join()
    if central_node is not None:
        central_node.stop()
        central_node.join()

