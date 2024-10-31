import time
import sys
import os

sys.path.insert(0, '..')
#sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from network.agent_node import AgentNode
from network.central_node import CentralNode

try:

    central_node = CentralNode("127.0.0.1", 10000, "../database/central_node.db")
    central_node.start()

    time.sleep(5)

    agent1 = AgentNode("agent1")
    agent1.start()

    time.sleep(5)

    agent1.connect_to_central_node("127.0.0.1", 10000)
    
    time.sleep(5)

    ## TEST: database should be up to date
    result = central_node.query_db("SELECT * FROM central_nodes")
    print(result)
    result = central_node.query_db("SELECT * FROM agent_nodes")
    print(result)
    result = central_node.query_db("SELECT * FROM connections")
    print(result)

    time.sleep(5)

    ## TEST: there should be single connection for both nodes
    print("central node connections:", central_node.connections)
    print("agent1 node connection:", agent1.connection)

    time.sleep(5)

    ## TEST: send messages
    agent1.send_message_to_central_node("Hello from agent1!")
    time.sleep(1)
    central_node.send_message_to_agent(agent1.id, "Hello to agent1 from central node!")

    time.sleep(5)

    ## TEST: Connections should have one less item after agent stopped solving one of the problem instances
    agent1.disconnect_from_central_node()
    time.sleep(15)
    print("central node connections:", central_node.connections)
    print("agent1 node connection:", agent1.connection)
    result = central_node.query_db("SELECT * FROM connections")
    print(result)

    time.sleep(5)

    ## TEST: we should return False when sending message to disconnected agent (same for central node)
    result = agent1.send_message_to_central_node("Hello from agent1!")
    print(result)
    time.sleep(1)
    result = central_node.send_message_to_agent(agent1.id, "Hello to agent1 from central node!")
    print(result)


    ## TEST: Connections should be empty after agent stopped (central node should also have no connections)
    agent1.stop()
    agent1.join()
    time.sleep(20)
    result = central_node.query_db("SELECT * FROM connections")
    print(result)
    print("central node connections:", central_node.connections)
    print("agent1 node connection:", agent1.connection)

    time.sleep(5)




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

