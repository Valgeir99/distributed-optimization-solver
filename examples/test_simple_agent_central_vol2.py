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

    agent1 = AgentNode("127.0.0.1", 10001, "2")
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

    ## TEST: connect to central node twice - should return False
    print("TEST: connect to central node twice - should return False")
    agent1.connect_to_central_node("127.0.0.1", 10000, "instance_1")
    result = agent1.connect_to_central_node("127.0.0.1", 10000, "instance_1")
    print(result)

    ## TEST: connect to agent from agent - should return False
    print("TEST: connect to agent from agent - should return False")
    agent2 = AgentNode("127.0.0.1", 10002, "3")
    agent2.start()
    time.sleep(5)
    result = agent1.connect_to_central_node("127.0.0.1", 10002, "instance_1")
    print(result)

    ## TEST: create two agent nodes with the same host:port - does not do anything since
    ## we cannot know if agents have the same host:port (so on open network this is 
    ## not a problem but on localhost it is just our responsibility to not do this. 
    ## So on local network there will just be two agents receiving the same message - which we don't want)
    print("TEST: create two agent nodes with the same host:port - should not give error")
    agent3 = AgentNode("127.0.0.1", 10001, "4")
    agent3.start()
    time.sleep(5)
    agent3.connect_to_central_node("127.0.0.1", 10000, "instance_1")
    time.sleep(5)
    print(agent1.connections)
    print(agent3.connections)
    central_node.send_message_to_agent("127.0.0.1", 10001, "instance_1", "Hello to agent1/agent3 from central node!")
    time.sleep(1)


    ## TEST: create agent with illegal port number and then connect to central node - should work 
    ## normally since this agent port number does not matter at all since when using socket.create_connection()
    ## then the agent node's side of the connection is bound to a random port! TODO: fix code base so that 
    ## agent node's port number is not needed at all (since it is not used)
    print("TEST: create agent with illegal port number and then connect to central node - should ...")
    agent4 = AgentNode("127.0.0.1", -1, "5")
    agent4.start()
    time.sleep(5)
    result = agent4.connect_to_central_node("127.0.0.1", 10000, "instance_1")
    print(result)
    agent4.send_message_to_central_node("127.0.0.1", 10000, "instance_1", "Hello from agent4!")

    ## TEST: close connection to central node unexpectedly - connection will be closed and connections set is updated
    ##       then try to message the central node - we just get False since this connection does not exist anymore
    print("TEST: close connection to central node unexpectedly - should handle it like normal disconnect")
    agent1.unexpected_connection_close("instance_1")
    time.sleep(5)
    print(agent1.connections)
    print(central_node.connections)
    result = agent1.send_message_to_central_node("127.0.0.1", 10000, "instance_1", "Hello from agent1!")
    print(result)


    time.sleep(5)

except KeyboardInterrupt:
    print("\nKeyboardInterrupt received. Shutting down...")


finally:
    time.sleep(1)
    print("ENDING")
    # if agent1 is not None:
    #     agent1.stop()
    #     agent1.join()
    if central_node is not None:
        central_node.stop()
        central_node.join()
    

