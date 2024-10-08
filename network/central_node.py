import socket
import threading
import time
import sqlite3

from typing import override, Set

from .connection import NodeConnection
from .node import Node
from utils.database_utils import create_database, teardown_database


# TODO: later when running the code we would maybe always want to check if functions return True or False and do some
# action depending, e.g. when sending messages so that we know it was sent successful... (but maybe not necessary for 
# proof of concept)

class CentralNode(Node):
    """A central node that can connect to multiple agent nodes and send/receive data."""

    def __init__(self, host: str, port: int, db_path: str, id: int=None):
        """Initialize the node with a host address, port number, and ID."""
        super().__init__(host, port, id)
              
        self.lock = threading.Lock()
        
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
        self.db_connection = self.__connect_to_database()

        self.insert_into_db("INSERT INTO central_nodes (id, host, port) VALUES (?, ?, ?)", (self.id, self.host, self.port))



    def __init_server(self):
        """Initialize the server socket to listen for incoming connections."""
        print(f"Central node started on: {str(self.host)}:{str(self.port)} with id ({str(self.id)})")
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.settimeout(10.0)
        self.socket.listen(self.max_connections)


    def __connect_to_database(self):
        """Create a connection to the database."""
        connection = sqlite3.connect(self.db_path, check_same_thread=False)   # check_same_thread=False is needed for multithreading
        print(f"Connected to database at {self.db_path}")
        return connection


    def __disconnect_from_database(self):
        """Close the connection to the database."""
        self.db_connection.close()
        print(f"Disconnected from database at {self.db_path}")


    def query_db(self, query: str, params: tuple=()):
        """Query the database and return the result."""
        cursor = self.db_connection.cursor()
        cursor.execute(query, params)
        result = cursor.fetchall()
        cursor.close()
        return result


    def insert_into_db(self, query: str, params: tuple=()):
        """Insert data into the database."""
        with self.lock:
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
        self.__disconnect_from_database()
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
                    agent_node_id = connection.recv(4096).decode('utf-8')
                    connection.send(self.id.encode('utf-8'))
                    (agent_node_host, agent_node_port, problem_instance_id) = connection.recv(4096).decode('utf-8').split(";")
                    print(f"Central node ({self.id}) accepted connection from {agent_node_host}:{agent_node_port} with id ({agent_node_id})")
                    # TODO: here we might want to somehow check if connection is ok on both ends, but how to do that?
                    # We would also need to do the same for agent node
                    thread_central_node_side_connection = self.create_new_connection(connection, problem_instance_id, agent_node_id, agent_node_host, agent_node_port)
                    thread_central_node_side_connection.start()
                    
                    

                    try:
                        self.insert_into_db("INSERT OR IGNORE INTO agent_nodes (id, host, port) VALUES (?, ?, ?)", (agent_node_id, agent_node_host, agent_node_port))
                        self.connections.add(thread_central_node_side_connection)

                    except sqlite3.Error as e:
                        print(f"Error while inserting agent node ({agent_node_id}) into database: {e}")
                        # TODO: maybe we want to close the connection here and remove the connection from the set of connections
                        # And also somehow let agent node know that connection was not successful
                        # TODO: we could also not use try-except and then the program would crash and we would know that something is wrong

                    try:
                        self.insert_into_db("INSERT INTO connections (agent_node_id, central_node_id, problem_instance_id) VALUES (?, ?, ?)", (agent_node_id, self.id, problem_instance_id))

                    except sqlite3.Error as e:
                        print(f"Error while inserting connection between agent node ({agent_node_id}) and central node ({self.id}) for problem instance ({problem_instance_id}) into database: {e}")


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


    