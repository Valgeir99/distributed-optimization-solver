import threading
import socket

from abc import ABC, abstractmethod   # use abstractmethod to create abstract methods (remove_connection())

from .connection import NodeConnection

class Node(threading.Thread, ABC):
    """A node in a network of nodes."""

    def __init__(self, id: str=None):
        """Initialize the node with ID."""
        super().__init__()

        # TODO: don't allow id to be set by user to make it unique (but this is nice for testing)
        if id is None:
            self.id = self.__generate_id()
        else:
            self.id = str(id)

    
    def __generate_id(self) -> str:
        """Generate a unique identifier for the node based on its host and port.
        Returns:
            str: A unique identifier for the node."""
        # TODO: is this unique enough?
        return hash((self.host, self.port))


    def create_new_connection(self, connection: socket.socket, problem_instance_id: str, connected_node_id: str) -> NodeConnection:
        """Create a new connection object to handle communication with a connected node."""
        return NodeConnection(self, connection, problem_instance_id,  connected_node_id)
    
    @abstractmethod
    def remove_connection(self, connection: NodeConnection):
        """Remove a connection from the list of active connections."""
        pass