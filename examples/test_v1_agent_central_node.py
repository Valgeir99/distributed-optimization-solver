import time
import sys
import os

sys.path.insert(0, '..')
#sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from network.agent_node import AgentNode
from network.central_node import CentralNode

try:

    central_node = CentralNode("127.0.0.1", 10000, "1")
    central_node.start()

    time.sleep(5)

    agent1 = AgentNode("127.0.0.1", 10001, "2")
    agent1.start()

    time.sleep(5)

    agent1.connect_to_central_node("127.0.0.1", 10000)

    time.sleep(5)

    print("central node connections:", central_node.connections)
    print("agent1 node connection:", agent1.connection)

    time.sleep(5)

    central_node.send_message_to_agent("2", "Hello to agent1 from central node!")

    agent1.send_message_to_central_node("Hello from agent1!")

    time.sleep(5)

    central_node.send_message_to_all_agents("Hello from central node!")

    time.sleep(5)

    agent1.connect_to_central_node("127.0.0.1", 10000)   # test to see if connect to central node gives error if we are already connected

    time.sleep(5)

    agent2 = AgentNode("127.0.0.1", 10002, "3")
    agent2.start()

    time.sleep(5)

    agent2.connect_to_central_node("127.0.0.1", 10001)   # test to see if connect to agent node gives error

    time.sleep(5)

    agent2.connect_to_central_node("127.0.0.1", 10000)

    time.sleep(5)

    print("central node connections:", central_node.connections)
    print("agent1 node connection:", agent1.connection)
    print("agent2 node connection:", agent2.connection)

    time.sleep(5)

    agent2.send_message_to_central_node("Hello from agent2!")

    time.sleep(5)

    central_node.send_message_to_all_agents("Hello from central node!")

    time.sleep(5)

    central_node.send_message_to_agent("2", "Hello to agent1 from central node!")
    central_node.send_message_to_agent("3", "Hello to agent2 from central node!")





except KeyboardInterrupt:
    print("\nKeyboardInterrupt received. Shutting down...")


finally:
    time.sleep(1)
    print("ENDING")
    if agent1 is not None:
        agent1.stop()
        agent1.join()
    if agent2 is not None:
        agent2.stop()
        agent2.join()
    if central_node is not None:
        central_node.stop()
        central_node.join()

