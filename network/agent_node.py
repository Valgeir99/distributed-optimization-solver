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
      
        
        self.connections: Set[NodeConnection] = set()

        self.problem_instances_ids: Set[str] = set()

        print(f"Agent node ({self.id}) started")

    
    def connect_to_central_node(self, host: str, port: int, problem_instance_id: str): 
        """Initiate a connection to a central node and create a socket for bidirectional communication.
        Returns:
            bool: True if the connection was successful, False otherwise.
        Args:
            host (str): The host address of the central node to connect to.
            port (int): The port number of the central node to connect to.
            problem_instance_id (str): The id of the problem instance that this agent node is solving though this connection.
        """

        # if len(self.connections) >= self.max_connections:
        #     print(f"Max number of connections reached: {self.max_connections}")
        #     return False

        if self.host == host and self.port == host:
            print("Cannot connect to self")
            return False

        if problem_instance_id in self.problem_instances_ids:
            print("Already solving this problem instance")
            return False

        for connection in self.connections:
            if connection.other_node_host == host and connection.other_node_port == port and connection.problem_instance_id == problem_instance_id:
                print("Already connected to this node with this problem instance")
                return False
        
        
        
        # Create connection to central node
        try:
            connection = socket.create_connection((host, port))
            
            print(f"Try to connected from {self.host}:{self.port} to {host}:{port}")

            # Basic information exchange of the id's of the nodes!
            connection.send((self.id).encode('utf-8')) # Send my id and port to the connected node!
            central_node_id = connection.recv(4096).decode('utf-8') # When a node is connected, it sends its id!

            # Send connection details (host, port and problem instance id) to the central node
            connection.send((self.host + ";" + str(self.port) + ";" + problem_instance_id).encode('utf-8'))

            # TODO: maybe to make sure that the connection is ok in both ways we should check if central node id is not None?
            # and if it is then we should close the connection and return False

            thread_agent_node_side_connection = self.create_new_connection(connection, problem_instance_id, central_node_id, host, port)
            thread_agent_node_side_connection.start()

            self.connections.add(thread_agent_node_side_connection)

        except Exception as e:
            print(f"Failed to connect from {self.host}:{self.port} to {host}:{port}: {e}")
            return False
        


    def get_problem_instance(self, problem_instance_id: str):
        """Get the problem instance from the central node."""
        # Ask for the problem instance from the central node
        #try:
        #self.send_message_to_central_node("Problem instance request")
            # how to wait for response?
        pass

    
    def disconnect_from_central_node(self, host: str, port: int):
        # TODO: Implement this method

        # How to do that?
        # Because we have two connections for each pair of nodes, we need to
        # close both connections. We can do this by sending a message to the
        # other node to tell it to close the connection?

        
        pass



    def receive_message_from_central_node(self, data: str):
        """Handle data received from the central node."""
        pass

    
    # TODO: not sure if I want to use central_node_id or host:port to identify central nodes?
    # Probably the id since later we will need to map problem instance id to central node id / host:port
    def send_message_to_central_node(self, central_node_id: str, problem_instance_id: str, data: str):
        """Send data to the central node that gave us this problem instance."""
        for conn in self.connections:
            if conn.other_node_id == central_node_id and conn.problem_instance_id == problem_instance_id:
                conn.send(data)
                return True
        print("This connection does not exist")
        return False

    

    def stop(self):
        """Close all connections to central nodes and reset the node's state."""
        for conn in self.connections:
            conn.close_connection()
    
        self.connections = set()

        print(f"Agent node ({self.id}) stopped")

        # TODO: should we stop the thread? Otherwise this method is basically just like the method
        # disconnect_from_central_node()

    
    def terminate(self):
        """Stop the node, close all connections, and stop the node's thread."""
        # self.stop()
        # self.join()
        # TODO: how to stop run() method when not overriding it in the class?
        pass
