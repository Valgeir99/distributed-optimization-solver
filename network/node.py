import threading

from .connection import NodeConnection

class Node(threading.Thread):
    """A network node that can connect to other nodes and send/receive data."""

    def __init__(self, host: str, port: str, id: int=None):
        """Initialize the node with a host address, port number, and ID."""
        super().__init__()
        self.host = host
        self.port = port

        if id is None:
            self.id = self.__generate_id()
        else:
            self.id = id

    
    def __generate_id(self):
        """Generate a unique identifier for the node based on its host and port."""
        # TODO: is this unique enough?
        return hash((self.host, self.port))


    def create_new_connection(self, connection, problem_instance_id, connected_node_id, connected_node_host, connected_node_port):
        """Create a new connection object to handle communication with a connected node."""
        return NodeConnection(self, connection, problem_instance_id,  connected_node_id, connected_node_host, connected_node_port)