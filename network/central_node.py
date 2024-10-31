import socket
import threading
import time
import sqlite3
import uuid

from typing import Set, override

from .connection import NodeConnection
from .node import Node
from utils.database_utils import create_database, teardown_database


# TODO: later when running the code we would maybe always want to check if functions return True or False and do some
# action depending, e.g. when sending messages so that we know it was sent successful... (but maybe not necessary for 
# proof of concept)

class CentralNode(Node):
    """A central node that can connect to multiple agent nodes and send/receive data."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        """Singleton pattern to ensure only one instance of the central node is created."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        else:
            raise Exception("CentralNode instance already exists!")
        return cls._instance
        

    def __init__(self, host: str, port: int, db_path: str):
        """Initialize the node with a host address, port number, ID and path to local database."""
        super().__init__()

        self.id = self.__generate_id()

        self.host = host
        self.port = port
              
        self.lock = threading.Lock()
        
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__init_server()

        self.connections: Set[NodeConnection] = set()   # TODO: initilize this by values from database (if it makes sense that central node can accedentally be stopped and started again)
        self.listening_for_connections_flag = threading.Event()

        self.problem_instance_storage: Set[str] = set()   # store id of problem instances that this central node is storing
        # TODO: where to store the actual problem instances? Also need to incorporate this in the code


        # Database
        self.db_path = db_path
        create_database(self.db_path)
        self.db_connection = self.__connect_to_database()

        self.edit_data_in_db("INSERT INTO central_nodes (id, host, port) VALUES (?, ?, ?)", (self.id, self.host, self.port))

    cnt = 0
    def __generate_id(self) -> str:
        """Generate a unique identifier for node.
        Returns:
            str: A unique identifier for node."""
        #return str(uuid.uuid4())
        # TODO: use this for testing for readability but remove later
        self.cnt += 1
        return str(self.cnt)
        
        
    def __init_server(self):
        """Initialize the server socket to listen for incoming connections."""
        print(f"Central node started on: {str(self.host)}:{str(self.port)} with id ({str(self.id)})")
        try: 
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))   # TODO: if testing on different machines then we need to bind to '0.0.0.0' to listen on all interfaces
            self.socket.settimeout(10.0)   # timeout if no data is received within 10 seconds
            self.socket.listen(5)   # the number of connections that can be queued before the system starts to reject new connections
        except socket.error as e:
            raise socket.error(f"Error while initializing the server socket on {self.host}:{self.port} for central node ({self.id}): {e}")
        except Exception as e:
            raise Exception(f"Error while initializing the server socket on {self.host}:{self.port} for central node ({self.id}): {e}")


    def __connect_to_database(self):
        """Create a connection to the database."""
        try:
            connection = sqlite3.connect(self.db_path, check_same_thread=False)   # check_same_thread=False is needed for multithreading
            print(f"Connected to database at {self.db_path}")
            return connection
        except sqlite3.Error as e:
            # Raise exception to stop the program (we can't continue without the database)
            raise sqlite3.Error(f"Error while connecting to database at {self.db_path}: {e}")


    def __disconnect_from_database(self):
        """Close the connection to the database."""
        try:
            self.db_connection.close()
            print(f"Disconnected from database at {self.db_path}")
        except sqlite3.Error as e:
            print(f"Error while disconnecting from database at {self.db_path}: {e}")


    def query_db(self, query: str, params: tuple=()) -> list:
        """Query the database and return the result.
        Returns: 
            list: The result of the query or None if an error occurred."""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute(query, params)
            result = cursor.fetchall()
            cursor.close()
            return result
        except sqlite3.Error as e:
            print(f"Error while querying database at {self.db_path}: {e}")
            return None
        # TODO: remember we need to check if the result is None when we call this function!!



    def edit_data_in_db(self, query: str, params: tuple=()):
        """Insert/Delete data in the database."""
        with self.lock:
            try:
                cursor = self.db_connection.cursor()
                cursor.execute(query, params)
                self.db_connection.commit()
                cursor.close()
            except sqlite3.Error as e:
                self.db_connection.rollback()
                raise sqlite3.Error(f"Error while editing data in database at {self.db_path}: {e}")



    def send_message_to_all_agents(self, message: str):
        """Send a message to all agent nodes."""
        # TODO: if we use this method when validating solution then maybe we want to exclude the agent that 
        # sent the solution to us to begin with
        for conn in self.connections:
            # TODO: use try-except here (maybe we want to remove the connection if it fails)
            conn.send(message)


    def send_message_to_agent(self, agent_id: str, message: str) -> bool:
        """Send a message to a specific agent node.
        Returns:
            bool: True if the message was sent successfully, False otherwise."""
        for conn in self.connections:
            if conn.other_node_id == agent_id:
                conn.send(message)
                return True

        print(f"Connection for agent node ({agent_id}) not found in connections")
        return False
    

    def receive_message_from_agent(self, agent_id: str, message: str):
        """Handle message received from an agent node."""
        pass


    def send_problem_instance_to_agent(self, agent_id: str, problem_instance_id: str):
        """Send a problem instance to an agent node."""
        pass

    def remove_connection(self, connection: NodeConnection):
        """Remove a connection from the node's list of active connections."""
        try:
            self.connections.remove(connection)
            self.edit_data_in_db("DELETE FROM connections WHERE agent_node_id = ? AND central_node_id = ?", (connection.other_node_id, connection.this_node.id))
        except KeyError as e:
            print(f"Error while removing connection from set of connections: {e}")
        except sqlite3.Error as e:
            print(f"Error while removing connection from database: {e}")
        except Exception as e:
            print(f"Error in remove_connection(): {e}")



    def stop(self):
        """Stop the node's listener thread and close all connections."""
        # We techincally never want to stop central node... but good to have this for testing
        self.listening_for_connections_flag.clear()
        self.join()   # do not continue with this thread until central node thread is done (run() method is done)
        self.__disconnect_from_database()
        teardown_database(self.db_path)

    
    @override
    def run(self):
        """Start the node's listener thread."""
        self.listening_for_connections_flag.set()
        self.__listen()


    def __listen(self):
        """Listen for incoming connections and create a new socket to handle each connection."""
        print(f"Listening for connections on {self.host}:{self.port} by central node ({self.id})")

        fail_count = 0
        while self.listening_for_connections_flag.is_set():
            try:
                connection, address = self.socket.accept()

                # Generate id for agent node and send it along with central node id
                agent_node_id = self.__generate_id()
                connection.send((self.id + ";" + agent_node_id).encode('utf-8'))

                # TODO: make unit test for this
                # Check if this connection already exists - if so close it and continue without creating the connection object
                # TODO: now since central node creates id for agent node we can't really check if the connection already exists
                # since everytime agent node connects it will get a new id... (I guess that is just how we define the connections
                # so not much we can do actually in this implementation - other implementations might use e.g. accounts for agents 
                # so we would identify agents by accounts not by connections basically)
                connection_exists = False
                for conn in self.connections:
                    if conn.other_node_id == agent_node_id:
                        connection_exists = True
                        print(f"Connection from agent node ({agent_node_id}) already exists")
                        connection.close()   # when central node side of the connection is closed then the agent node side will also close
                        break

                if connection_exists:
                    continue   # continue to next iteration of the while loop so we don't create a new connection object

                print(f"Central node ({self.id}) accepted connection from agent node ({agent_node_id})")
                thread_central_node_side_connection = self.create_new_connection(connection, agent_node_id)
                thread_central_node_side_connection.start()
                
                try:
                    self.edit_data_in_db("INSERT OR IGNORE INTO agent_nodes (id) VALUES (?)", (agent_node_id,))
                    self.connections.add(thread_central_node_side_connection)
                except sqlite3.Error as e:
                    print(f"Error while inserting agent node ({agent_node_id}) into database: {e}")
                
                try:
                    self.edit_data_in_db("INSERT OR IGNORE INTO connections (agent_node_id, central_node_id) VALUES (?, ?)", (agent_node_id, self.id))
                except sqlite3.Error as e:
                    print(f"Error while inserting connection between agent node ({agent_node_id}) and central node ({self.id}) into database: {e}")


            
            except socket.timeout:
                #print('Connection timeout, retrying...')
                continue

            except socket.error as e:
                print(f"Socket error while listening for connections on {self.host}:{self.port} by central node ({self.id}) : {e}")
                # TODO: here we are allowing the central node to fail 5 times before stopping it... this 
                # might be good for testing so more robustness
                # fail_count += 1
                # if fail_count >= 5:
                #     break
                # time.sleep(60)
                # continue
                # TODO: maybe we want to raise an error and terminate the program in this case since if 
                # the central node can't accept connections then it is kind of useless
                # But we would first do the clean up below before raising the error... 
                # Same below
                #raise socket.error(f"Error while listening for connections by {self.host}:{self.port} : {e}")
                break

            except Exception as e:
                print(f"Error while listening for connections on {self.host}:{self.port} by central node ({self.id}) : {e}")
                break

            time.sleep(0.5)

        
        print(f"Central node ({self.id}) stopping...")

        # Clean up - close all connections
        connections_copy = self.connections.copy()   # we copy the set since we are modifying it in the loop
        for conn in connections_copy:
            conn.close_connection()   # when central node side of the connection is closed then the agent node side will also close

        time.sleep(1)

        for conn in connections_copy:   # we call join() in seperate loop since otherwise we would need to wait for the connection to close before we can close the next one
            conn.join()
        
        # Close central node's listener socket
        self.socket.close()

        print(f"Central node ({self.id}) stopped")

