import threading
import socket

from abc import ABC, abstractmethod   # use abstractmethod to create abstract methods (remove_connection())

from .connection import NodeConnection

class Node(threading.Thread, ABC):
    """A node in a network of nodes."""

    def __init__(self):
        """Initialize the node with parent class."""
        super().__init__()

    def create_new_connection(self, connection: socket.socket, connected_node_id: str) -> NodeConnection:
        """Create a new connection object to handle communication with a connected node."""
        return NodeConnection(self, connection,  connected_node_id)
    
    @abstractmethod
    def remove_connection(self, connection: NodeConnection):
        """Remove connection."""
        pass