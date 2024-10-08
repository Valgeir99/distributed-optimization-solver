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

    result = central_node.query_db("SELECT * FROM problem_instances")
    print(result)


except KeyboardInterrupt:
    print("\nKeyboardInterrupt received. Shutting down...")


finally:
    time.sleep(1)
    print("ENDING")
    if central_node is not None:
        central_node.stop()
        central_node.join()

