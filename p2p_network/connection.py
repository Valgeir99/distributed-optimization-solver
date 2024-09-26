import socket
import threading
import json
import time

from typing import override, TYPE_CHECKING

if TYPE_CHECKING:
    from .node import Node


class NodeConnection(threading.Thread):
    """A connection to a network node that can send/receive data."""


    def __init__(self, node: 'Node', connection: socket.socket, peer_id, peer_host: str, peer_port: int):
        """Initialize the connection with a reference to the parent node and the socket connection. 
           Also keep track of the peer's id, host address and port number."""
        super().__init__()
        self.node = node
        self.connection = connection
        self.peer_id = str(peer_id)
        self.peer_host = peer_host
        self.peer_port = peer_port
        self.connected_flag = threading.Event()

        self.connection.settimeout(10.0)

    
    def send(self, data):
        """Send the data to the connected node"""
        # TODO: specify what format the data is on - now str later probably dict/json

        if data is not None:
            print(f"Send data to {self.peer_host}:{self.peer_port} from node ({str(self.node.id)}) : {data}")
            self.connection.sendall(data.encode())
            #self.connection.sendall(data + self.COMPR_CHAR + self.EOT_CHAR)   # TODO: maybe use this instead and deal with the EOT in run() method accordingly


    def close_connection(self):
        """Closes the connection and the thread is stopped"""
        self.connected_flag.clear()
        #self.connection.close()
        #self.node.remove_connection(self)   # TODO: how to let other node know that this connection is closed?
        #self.join()

        

        




    @override
    def run(self):
        self.connected_flag.set()
        while self.connected_flag.is_set():
            try:
                data = self.connection.recv(1024)
                if not data:
                    break
                print(f"Received data from {self.peer_host}:{self.peer_port} by node ({str(self.node.id)}) : {data.decode()}")

            except socket.timeout:
                #print(f"Connection timeout occurred while receiving data from {self.peer_host}:{self.peer_port} by node ({str(self.node.id)})")
                continue

            except socket.error as e:
                print(f"Socket error while receiving data from {self.peer_host}:{self.peer_port} by node ({str(self.node.id)}): {e}")
                break

            except Exception as e:
                print(f"Error while receiving data from {self.peer_host}:{self.peer_port} by node ({str(self.node.id)}): {e}")
                break
            
            time.sleep(0.1)
        

        #self.close_connection()   # TODO: same issue as in node.py so maybe not have this method calling .join()
        self.connection.close()
        print(f"Connection from {self.node.host}:{self.node.port} to {self.peer_host}:{self.peer_port} closed.")

        # TODO: let other node know that this connection is closed


    def __str__(self):
        return f"NodeConnection from {self.node.host}:{self.node.port} with id ({str(self.node.id)}) to {self.peer_host}:{self.peer_port} with id ({str(self.peer_id)})"

    def __repr__(self):
        return f"NodeConnection from {self.node.host}:{self.node.port} with id ({str(self.node.id)}) to {self.peer_host}:{self.peer_port} with id ({str(self.peer_id)})"
