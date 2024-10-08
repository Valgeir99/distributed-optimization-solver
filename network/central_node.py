import socket
import threading
import time
import sqlite3

from typing import override, Set

from .connection import NodeConnection
from .node import Node
from utils.database_utils import create_database, teardown_database, connect_to_database, query_db, close_database_connection


# TODO: later when running the code we would maybe always want to check if functions return True or False and do some
# action depending, e.g. when sending messages so that we know it was sent successful... (but maybe not necessary for 
# proof of concept)

class CentralNode(Node):
    """A central node that can connect to multiple agent nodes and send/receive data."""

    def __init__(self, host: str, port: int, db_path: str, id: int=None):
        """Initialize the node with a host address, port number, and ID."""
        super().__init__(host, port, id)
              
        
        self.max_connections = 10   # TODO: do we want this?


        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__init_server()

        self.connections: Set[NodeConnection] = set()
        self.listening_for_connections_flag = threading.Event()

        self.problem_instance_storage: Set[str] = set()   # store id of problem instances that this central node is storing
        # TODO: where to store the actual problem instances?


        # Database
        self.db_path = db_path
        create_database(self.db_path)
        self.db_connection = connect_to_database(self.db_path)                 



    def __init_server(self):
        """Initialize the server socket to listen for incoming connections."""
        print(f"Initialization of the Node on: {str(self.host)}:{str(self.port)} with id ({str(self.id)})")
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.settimeout(10.0)
        self.socket.listen(self.max_connections)


    def __create_db_connection(self):
        """Create a connection to the database."""
        connection = sqlite3.connect(self.db_path)
        print(f"Connected to database at {self.db_path}")
        return connection


    def query_db(self, query: str, params: tuple=()):
        """Query the database and return the result."""
        cursor = self.db_connection.cursor()
        cursor.execute(query, params)
        result = cursor.fetchall()
        cursor.close()
        return result


    def insert_into_db(self, query: str, params: tuple=()):
        """Insert data into the database."""
        cursor = self.db_connection.cursor()
        cursor.execute(query, params)
        self.db_connection.commit()
        cursor.close()



    def send_message_to_all_agents(self, message: str):
        """Send a message to all agent nodes."""
        # TODO: if we use this method when validating solution then maybe we want to exclude the agent that 
        # sent the solution to us to begin with
        for conn in self.connections:
            conn.send(message)


    def send_message_to_agent(self, agent_id: str, message: str):
        """Send a message to a specific agent node."""
        for conn in self.connections:
            if conn.other_node_id == agent_id:
                conn.send(message)
                return True

        print(f"Agent ({agent_id}) not found")
        return False



    def stop(self):
        """Stop the node's listener thread and close all connections."""
        # TODO: we techincally never want to stop central node so we should think about if 
        # we want to implement this method or not
        self.listening_for_connections_flag.clear()
        close_database_connection(self.db_connection)
        teardown_database(self.db_path)
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
                    print(f"Central node ({self.id}) accepted connection from {address}")
                    connected_node_id = connection.recv(4096).decode('utf-8').split(":")[0]
                    connection.send(self.id.encode('utf-8'))
                    # TODO: here we might want to somehow check if connection is ok on both ends, but how to do that?
                    # We would also need to do the same for agent node
                    thread_central_node_side_connection = self.create_new_connection(connection, connected_node_id, address[0], address[1])
                    thread_central_node_side_connection.start()
                    
                    self.connections.add(thread_central_node_side_connection)

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
        print(f"Central node ({str(self.id)}) stopping...")

        for conn in self.connections.copy():
            conn.close_connection()

        time.sleep(1)

        for conn in self.connections.copy():
            conn.join()

        



        # TODO: maybe let agents somehow know that central node is stopping?

        #self.socket.settimeout(None)   # TODO: what is the purpose of this? 
        self.socket.close()

        #self.join()   # TODO: maybe change stop() function and instead call join() after loop
        # TODO: I think that we don't want to call .join() here to stop the thread since
        # the object is still exiting and can be restarted later using the start() method

        print(f"Central node ({self.id}) stopped")


    