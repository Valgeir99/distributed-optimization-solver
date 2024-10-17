# TODO: more tests like connect to central node twice, connect to agent from agent, connect to random host:port, etc.

# TODO: create two central nodes same host:port and see what happens

import time
import sys
import os

sys.path.insert(0, '..')
#sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from network.agent_node import AgentNode
from network.central_node import CentralNode

try:

    ## TEST: create central node with illegal port number - should raise exception
    # print("TEST: create central node with illegal port number - should raise exception")
    # try:
    #     central_node = CentralNode("127.0.0.1", -1, "../database/central_node.db", "1")
    # except Exception as e:
    #     print(e)

    central_node = CentralNode("127.0.0.1", 10000, "../database/central_node.db", "1")
    central_node.start()

    time.sleep(5)

    ## TEST: create another central node - should raise exception (singelton pattern)
    # print("TEST: create another central node - should raise exception (singelton pattern)")
    # try:
    #     central_node2 = CentralNode("127.0.0.1", 10000, "../database/central_node.db", "2")
    # except Exception as e:
    #     print(e)

    # time.sleep(5)

    agent1 = AgentNode("2")
    agent1.start()

    time.sleep(5)

    ## TEST: connect to central node with illegal port number - should return False
    print("TEST: connect to central node with illegal port number - should return False")
    result = agent1.connect_to_central_node("127.0.0.1", -1, "instance_1")
    print(result)

    ## TEST: connect to random host:port - should return False
    print("TEST: connect to random host:port - should return False")
    result = agent1.connect_to_central_node("127.0.0.1", 10009, "instance_1")
    print(result)

    ## TEST: connect to central node twice - should return False TODO: now we don't check this for agent node but only for central node so see how it behaves!
    print("TEST: connect to central node twice - should return False")
    agent1.connect_to_central_node("127.0.0.1", 10000, "instance_1")
    time.sleep(5)
    result = agent1.connect_to_central_node("127.0.0.1", 10000, "instance_1")
    print(result)

    ## TEST: connect to agent from agent - should return False
    print("TEST: connect to agent from agent - should return False")
    agent2 = AgentNode("3")
    agent2.start()
    time.sleep(5)
    result = agent1.connect_to_central_node("127.0.0.1", 10002, "instance_1")
    print(result)

    ## TEST: close connection to central node unexpectedly - connection will be closed and connections set is updated
    ##       then try to message the central node - we just get False since this connection does not exist anymore
    print("TEST: close connection to central node unexpectedly - should handle it like normal disconnect")
    agent1.unexpected_connection_close("instance_1")
    time.sleep(5)
    print(agent1.connections)
    print(central_node.connections)
    result = agent1.send_message_to_central_node("instance_1", "Hello from agent1!")
    print(result)


    time.sleep(5)

except KeyboardInterrupt:
    print("\nKeyboardInterrupt received. Shutting down...")


finally:
    time.sleep(1)
    print("ENDING")
    if central_node is not None:
        central_node.stop()
        central_node.join()
    

