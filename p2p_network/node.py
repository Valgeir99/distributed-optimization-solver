import socket
import threading
import time

from typing import override, Set

from .connection import NodeConnection

class Node(threading.Thread):
    """A network node that can connect to other nodes and send/receive data."""

    def __init__(self, host: str, port: int, id: int=None, max_connections: int=10):
        """Initialize the node with a host address, port number, and ID."""
        super().__init__()
        self.host = host
        self.port = port

        if id is None:
            self.id = self.__generate_id()
        else:
            self.id = str(id)

        self.max_connections = max_connections   # TODO: need to update code to handle this


        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__init_server()
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        self.connections: Set[NodeConnection] = set()

        self.listening_for_connections_flag = threading.Event()





    def __init_server(self):
        """Initialize the server socket to listen for incoming connections."""
        print(f"Initialization of the Node on: {str(self.host)}:{str(self.port)} with id ({str(self.id)})")
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.settimeout(10.0)
        self.socket.listen(self.max_connections)

    
    def __generate_id(self):
        """Generate a unique identifier for the node based on its host and port."""
        # TODO: is this unique enough?
        return hash((self.host, self.port))


    def connect_to_node(self, peer_host: str, peer_port: int): 
        """Initiate a connection to another peer and create a socket for bidirectional communication.
        Returns:
            bool: True if the connection was successful, False otherwise.
        Args:
            peer_host (str): The host address of the peer to connect to.
            peer_port (int): The port number of the peer to connect to.
        """

        if len(self.connections) >= self.max_connections:
            print(f"Max number of connections reached: {self.max_connections}")
            return False
        
        if self.host == peer_host and self.port == peer_port:
            print("Cannot connect to self")
            return False
        
        if any(self.host == node.host and self.port == node.port for node in self.connections):
            print("Already connected to this node")
            return False
        
        try:
            connection = socket.create_connection((peer_host, peer_port))
            
            print(f"Try to connected from {self.host}:{self.port} to {peer_host}:{peer_port}")

            # Basic information exchange (not secure) of the id's of the nodes!
            connection.send((self.id + ":" + str(self.port)).encode('utf-8')) # Send my id and port to the connected node!
            connected_node_id = connection.recv(4096).decode('utf-8') # When a node is connected, it sends its id!

            thread_client_side_connection = self.__create_new_connection(connection, connected_node_id, peer_host, peer_port)
            thread_client_side_connection.start()

            self.connections.add(thread_client_side_connection)

        except Exception as e:
            print(f"Failed to connect from {self.host}:{self.port} to {peer_host}:{peer_port}: {e}")
            return False

    
    def disconnect_from_node(self, peer_host: str, peer_port: int):
        # TODO: Implement this method
        # This method should close the connection to the specified peer.
        # But how do we do that since we don't know if this node is the 
        # client or the server in the connection?

        # Because we have two connections for each pair of nodes, we need to
        # close both connections. We can do this by sending a message to the
        # other node to tell it to close the connection?

        # NOTE: Not the most important functionality to implement for this project... 
        # since we assume nodes will not disconnect from each other (on purpose)
        pass
        

    def __create_new_connection(self, connection, connected_node_id, peer_host, peer_port):
        """Create a new connection object to handle communication with a connected node."""
        return NodeConnection(self, connection, connected_node_id, peer_host, peer_port)


    def send_to_nodes(self, data):
        """Send data to all connected nodes."""
        for conn in self.connections:
            conn.send(data)

        # TODO: later when adding blockchain logic then we need 
        # to make sure that the data is a dict/json object
        # TODO: later for blockchain then we need to make sure that
        # we are able to use gossip protocol so that other nodes 
        # also send the data to their connections. But how can we 
        # do that? How to make sure single node only recieves the
        # data once? And how to make sure that all nodes recieve
        # the data? And that we don't have infinite loops of data
        # being sent around the network?


    def stop(self):
        """Stop the node's listener thread and close all connections."""
        self.listening_for_connections_flag.clear()
        #self.join()

    
    @override
    def run(self):
        """Start the node's listener thread."""
        self.listening_for_connections_flag.set()
        self.__listen()

    def __listen(self):
        """Listen for incoming connections and create a new socket to handle each connection."""
        print(f"Listening for connections on {self.host}:{self.port}")

        while self.listening_for_connections_flag.is_set():
            try:
                connection, address = self.socket.accept()
                if len(self.connections) < self.max_connections:

                    print(f"Node ({self.id}) accepted connection from {address}")
                    connected_node_id = connection.recv(4096).decode('utf-8').split(":")[0]
                    connection.send(self.id.encode('utf-8'))
                    thread_server_side_connection = self.__create_new_connection(connection, connected_node_id, address[0], address[1])
                    thread_server_side_connection.start()
                    
                    self.connections.add(thread_server_side_connection)

                else:
                    print(f"Max number of connections reached: {self.max_connections}")
                    connection.close()


            except socket.timeout:
                #print('Connection timeout, retrying...')
                continue

            except socket.error as e:
                print(f"Socket error while listening for connections by {self.host}:{self.port} : {e}")
                break

            except Exception as e:
                print(f"Error while listening for connections by {self.host}:{self.port} : {e}")
                break

            time.sleep(0.1)

        
        #self.stop()   # TODO: maybe change stop() function and instead call join() after loop
        print(f"Node ({str(self.id)}) stopping...")

        for conn in self.connections.copy():
            conn.close_connection()

        time.sleep(1)

        for conn in self.connections.copy():
            conn.join()

        

        # TODO: remove from self.connections
        # - ah no we don't because this node is closing 
        # either way but it would be good if we would let 
        # other nodes somehow know...?
        # WEll yes we need to do it if we want to reuse this node!!

        #self.socket.settimeout(None)   # TODO: what is the purpose of this? 
        self.socket.close()

        #self.join()   # TODO: maybe change stop() function and instead call join() after loop
        # TODO: I think that we don't want to call .join() here to stop the thread since
        # the object is still exiting and can be restarted later using the start() method

        print(f"Node ({self.id}) stopped")


    