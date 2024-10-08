# I think connection class can be the same for both server and client side!
# Just when reciving messages I need to call the node's method to handle the message appropriately, 
# based on the header of the message and defined message protocol.

import socket
import threading
import json
import time

from typing import override, TYPE_CHECKING

if TYPE_CHECKING:
    from .node import Node



class NodeConnection(threading.Thread):
    """A connection from node to antoher node over network that can send/receive data."""


    def __init__(self, this_node: 'Node', connection: socket.socket, problem_instance_id: str, other_node_id, other_node_host: str, other_node_port: int):
        """Initialize the connection with a reference to the parent node, the problem instance the connection is meant for and the socket connection. 
           Also keep track of the other's node id, host address and port number."""
        super().__init__()
        self.this_node = this_node
        self.connection = connection
        self.other_node_id = str(other_node_id)
        self.other_node_host = other_node_host
        self.other_node_port = other_node_port
        self.problem_instance_id = problem_instance_id
        self.connected_flag = threading.Event()

        self.connection.settimeout(10.0)

    
    def send(self, data):
        """Send the data to the connected node"""
        # TODO: specify what format the data is on - now str later probably dict/json

        if data is not None:
            print(f"Send data to {self.other_node_host}:{self.other_node_port} from node ({str(self.this_node.id)}) : {data}")
            self.connection.sendall(data.encode())
            #self.connection.sendall(data + self.COMPR_CHAR + self.EOT_CHAR)   # TODO: maybe use this instead and deal with the EOT in run() method accordingly


    def close_connection(self):
        """Closes the connection and the thread is stopped"""
        self.connected_flag.clear()
        #self.connection.close()
        #self.this_node.remove_connection(self)   # TODO: how to let other node know that this connection is closed?
        #self.join()

        

        



    # The object's start() function will call the run() function in a new thread
    @override
    def run(self):
        """Receive data from the connected node and handle it."""
        #print("Connection established")
        self.connected_flag.set()
        while self.connected_flag.is_set():
            try:
                data = self.connection.recv(1024)
                if not data:
                    break
                print(f"Received data from {self.other_node_host}:{self.other_node_port} by node ({str(self.this_node.id)}) : {data.decode()}")
                # TODO: here we need to call nodes method to handle the message appropriately

            except socket.timeout:
                #print(f"Connection timeout occurred while receiving data from {self.other_node_host}:{self.other_node_port} by node ({str(self.this_node.id)})")
                continue

            except socket.error as e:
                print(f"Socket error while receiving data from {self.other_node_host}:{self.other_node_port} by node ({str(self.this_node.id)}): {e}")
                break

            except Exception as e:
                print(f"Error while receiving data from {self.other_node_host}:{self.other_node_port} by node ({str(self.this_node.id)}): {e}")
                break
            
            time.sleep(0.5)
        

        #self.close_connection()   # TODO: same issue as in node.py so maybe not have this method calling .join()
        self.connection.close()
        print(f"Connection from {self.this_node.host}:{self.this_node.port} to {self.other_node_host}:{self.other_node_port} closed.")

        # TODO: let other node know that this connection is closed


    def __str__(self):
        return f"NodeConnection from {self.this_node.host}:{self.this_node.port} with id ({str(self.this_node.id)}) to {self.other_node_host}:{self.other_node_port} with id ({str(self.other_node_id)})"

    def __repr__(self):
        return f"NodeConnection from {self.this_node.host}:{self.this_node.port} with id ({str(self.this_node.id)}) to {self.other_node_host}:{self.other_node_port} with id ({str(self.other_node_id)})"
