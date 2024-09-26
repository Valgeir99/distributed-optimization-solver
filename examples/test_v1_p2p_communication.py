import time
import sys
import os

sys.path.insert(0, '..')
#sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from p2p_network.node import Node

try:

    node1 = Node("127.0.0.1", 10000, 1)
    node1.start()

    node2 = Node("127.0.0.1", 10001, 2)
    node2.start()

    time.sleep(20)

    node1.connect_to_node("127.0.0.1", 10001)

    time.sleep(10)

    node1.send_to_nodes("Hello from node1!")

    time.sleep(10)

    node2.send_to_nodes("Hello from node2!")

    time.sleep(10)

    print("node1 connections:", node1.connections)
    print("node2 connections:", node2.connections)

    node1.send_to_nodes("Hello from node1 again!")

except KeyboardInterrupt:
    print("\nKeyboardInterrupt received. Shutting down...")


finally:
    time.sleep(1)
    node1.stop()
    node1.join()
    time.sleep(1)
    node2.stop()
    node2.join()

# finally:
#     print("Stopping nodes...")

#     # Stop and join node1
#     if node1.is_alive():
#         node1.stop()
#         node1.join(timeout=2)  # Give it 2 seconds to stop gracefully
#         if node1.is_alive():
#             print("Warning: node1 did not stop properly.")

#     # Stop and join node2
#     if node2.is_alive():
#         node2.stop()
#         node2.join(timeout=2)
#         if node2.is_alive():
#             print("Warning: node2 did not stop properly.")

#     print("Nodes stopped. Exiting.")