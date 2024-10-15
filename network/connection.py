# I think connection class can be the same for both server and client side!
# Just when reciving messages I need to call the node's method to handle the message appropriately, 
# based on the header of the message and defined message protocol.

import socket
import threading
import json
import time

from typing import TYPE_CHECKING
from typing import override   # needs python >= 3.12

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
        self.other_node_port = int(other_node_port)
        self.problem_instance_id = problem_instance_id

        self.connected_flag = threading.Event()

        self.connection.settimeout(10.0)   # timeout if no data is received within 10 seconds

    
    def send(self, data):
        """Send the data to the connected node"""
        # TODO: specify what format the data is on - now str later probably dict/json
        # TODO: exception handling? what if the connection is closed? what if the data is not in the correct format?

        if data is not None:
            print(f"Send data to {self.other_node_host}:{self.other_node_port} from node ({str(self.this_node.id)}) : {data}")
            self.connection.sendall(data.encode())
            #self.connection.sendall(data + self.COMPR_CHAR + self.EOT_CHAR)   # TODO: maybe use this instead and deal with the EOT in run() method accordingly


    def close_connection(self):
        """Set the connected flag to False which will stop the thread and close the connection."""
        self.connected_flag.clear()       


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
            
            # TODO: but if there is a socket error or other exception then how can we handle it?
            # I mean right now we are closing the connection which is fine but the node would still kind of 
            # think that it is solving the problem but the connection is closed so it would need to realise 
            # that and connect back to the central node. Would we want to implement that? But if we need 
            # to implement this and all extreeme cases then it is a lot of things... (and I will 100% forget 
            # to do some of them)
            # -> We could implement a reconnect method in the node class that would try to reconnect to the
            #    central node and then we could call this method in the except block below.
            except socket.error as e:
                print(f"Socket error while receiving data from {self.other_node_host}:{self.other_node_port} by node ({str(self.this_node.id)}): {e}")
                break

            except Exception as e:
                print(f"Error while receiving data from {self.other_node_host}:{self.other_node_port} by node ({str(self.this_node.id)}): {e}")
                break
            
            time.sleep(0.5)
        
        ## Close connection and clean up

        # When calling .close() on the socket, the other end will get notified that the connection is closed and will also exit the while loop above and close the connection!
        try:
            self.connection.close()
            print(f"Connection from {self.this_node.host}:{self.this_node.port} to {self.other_node_host}:{self.other_node_port} closed.")
        except Exception as e:
            print(f"Error while closing connection: {e}")

        # Remove the connection from the node's set of connections
        self.this_node.remove_connection(self)


    def __str__(self):
        return f"NodeConnection from {self.this_node.host}:{self.this_node.port} with id ({str(self.this_node.id)}) to {self.other_node_host}:{self.other_node_port} with id ({str(self.other_node_id)})"

    def __repr__(self):
        return f"NodeConnection from {self.this_node.host}:{self.this_node.port} with id ({str(self.this_node.id)}) to {self.other_node_host}:{self.other_node_port} with id ({str(self.other_node_id)})"
