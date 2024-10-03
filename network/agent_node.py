import socket
import threading

from typing import override, Set

from .connection import NodeConnection
from .node import Node

class AgentNode(Node):
    """An agent node that can connect to a single central node and send/receive data."""

    def __init__(self, host: str, port: int, id: int=None):
        """Initialize the node with a host address, port number, and ID."""
        super().__init__(host, port, id)
        
        #self.max_connections = 1   # TODO: maybe we don't need this if connection is only single variable
      
        
        self.connection: NodeConnection = None

        self.problem_instance_id = None
        # TODO: more problem instance stuff

        print(f"Agent node ({self.id}) started")

    
    def connect_to_central_node(self, host: str, port: int): 
        """Initiate a connection to a central node and create a socket for bidirectional communication.
        Returns:
            bool: True if the connection was successful, False otherwise.
        Args:
            host (str): The host address of the central node to connect to.
            port (int): The port number of the central node to connect to.
        """

        # if len(self.connections) >= self.max_connections:
        #     print(f"Max number of connections reached: {self.max_connections}")
        #     return False

        if self.connection is not None:
            print("Already connected to a central node")

            if host == self.connection.other_node_host and port == self.connection.other_node_port:
                print("Already connected to this node")
            
            return False
        
        if self.host == host and self.port == host:
            print("Cannot connect to self")
            return False
        
        
        
        try:
            connection = socket.create_connection((host, port))
            
            print(f"Try to connected from {self.host}:{self.port} to {host}:{port}")

            # Basic information exchange (not secure) of the id's of the nodes!
            connection.send((self.id + ":" + str(self.port)).encode('utf-8')) # Send my id and port to the connected node!
            central_node_id = connection.recv(4096).decode('utf-8') # When a node is connected, it sends its id!

            # TODO: maybe to make sure that the connection is ok in both ways we should check if central node id is not None?
            # and if it is then we should close the connection and return False

            thread_agent_node_side_connection = self.create_new_connection(connection, central_node_id, host, port)
            thread_agent_node_side_connection.start()

            self.connection = thread_agent_node_side_connection

        except Exception as e:
            print(f"Failed to connect from {self.host}:{self.port} to {host}:{port}: {e}")
            return False

    
    def disconnect_from_central_node(self, host: str, port: int):
        # TODO: Implement this method

        # How to do that?
        # Because we have two connections for each pair of nodes, we need to
        # close both connections. We can do this by sending a message to the
        # other node to tell it to close the connection?

        
        pass


    def send_message_to_central_node(self, data):
        """Send data to the central node."""
        if self.connection is not None:
            self.connection.send(data)
        else:
            print("Not connected to a central node")

    

    def stop(self):
        """Close the connection to the central node and reset the node's state."""
        if self.connection is not None:
            self.connection.close_connection()

        self.connection = None

        print(f"Agent node ({self.id}) stopped")

        # TODO: should we stop the thread? Otherwise this method is basically just like the method
        # disconnect_from_central_node()

    
    def terminate(self):
        """Stop the node, close all connections, and stop the node's thread."""
        # self.stop()
        # self.join()
        # TODO: how to stop run() method when not overriding it in the class?
        pass
