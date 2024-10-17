import socket
import time
import threading

from typing import Set

from .connection import NodeConnection
from .node import Node


class AgentNode(Node):
    """An agent node that can connect to central node (can have multiple connections) and 
    send/receive data."""

    def __init__(self, id: int=None):
        """Initialize the node with ID."""
        super().__init__(id)
        
        self.connections: Set[NodeConnection] = set()

        self.problem_instances_ids: Set[str] = set()   # TODO: do we need this? We have access to the problem instances through the connections - but maybe 
        # in the case where connection fails unexpectedly we might want to know which problem instances we were solving?

        print(f"Agent node ({self.id}) started")

        # TODO: map problem instance id to central node id / host:port?


    
    def connect_to_central_node(self, host: str, port: int, problem_instance_id: str) -> bool: 
        """Initiate a connection to a central node and create a socket for bidirectional communication.
        Returns:
            bool: True if the connection was successful, False otherwise.
        Args:
            host (str): The host address of the central node to connect to.
            port (int): The port number of the central node to connect to.
            problem_instance_id (str): The id of the problem instance that this agent node is solving though this connection.
        """

        # TODO: make unit tests for all of these cases
        if problem_instance_id in self.problem_instances_ids:
            print("Already solving this problem instance")
            return False

        for conn in self.connections:
            if conn.connection.getpeername()[0] == host and conn.connection.getpeername()[1] == port and conn.problem_instance_id == problem_instance_id:
                print("Already connected to this node with this problem instance")
                return False
         
        # Create connection to central node
        connection = None
        try:
            print(f"Try to connected from agent node ({self.id}) to central node for problem instance ({problem_instance_id})")
            
            connection = socket.create_connection((host, port))   # automatically binds agent node's side of the connection to a random port
        
            # Send connection information to central node!
            connection.send((self.id + ";" + problem_instance_id).encode('utf-8'))   # send agent id and problem id to the connected node
            central_node_id = connection.recv(4096).decode('utf-8')   # when central node is connected, it sends its id


        # TODO: make unit tests for the exception (we would need to mock this and raise an exception)
        except socket.error as e:
            # Handle socket errors which should arise from the create_connection() method
            print(f"Failed to connect from agent node ({self.id}) to central node listening at {host}:{port} : {e}")
            if connection is not None:
                connection.close()   # when agent node side of the connection is closed then the central node side will also close
            return False
        
        thread_agent_node_side_connection = self.create_new_connection(connection, problem_instance_id, central_node_id)
        thread_agent_node_side_connection.start()
        self.connections.add(thread_agent_node_side_connection)
        #self.problem_instances_ids.add(problem_instance_id)

        return True
        

    def get_problem_instance(self, cental_node_id: str, problem_instance_id: str):
        """Get the problem instance from the central node."""
        # Ask for the problem instance from the central node
        #try:
        #self.send_message_to_central_node("Problem instance request")
            # how to wait for response?
        pass

    
    # TODO: might want to implement such a method and if the connection is closed then we would 
    # maybe want to e.g. remove it and remove from problme_instances_ids
    # But is this actually something we want to have? What do we gain from this? Think!
    def check_connections(self):
        """Check if all connections for the agent's problem instances are still alive.
        Returns:
            bool: True if all connections are alive, False otherwise."""
        for conn in self.connections:
            if conn.problem_instance_id in self.problem_instances_ids:
                pass
                # See socket_peeking.py example
        
            


    
    def receive_message_from_central_node(self, msg: str):
        """Handle message received from the central node."""
        pass

    
    def send_message_to_central_node(self, problem_instance_id: str, msg: str) -> bool:
        """Send message to the central node who gave this agent node the problem instance.
        Returns:
            bool: True if the message was sent successfully, False otherwise."""
        for conn in self.connections:
            if conn.problem_instance_id == problem_instance_id:
                conn.send(msg)
                return True
        print(f"The connection for this problem instance ({problem_instance_id}) does not exist")
        return False


    def stop_solving_problem_instance(self, problem_instance_id: str) -> bool:
        """Stop solving a problem instance and close the connection to the central node (central 
        node will also close its side of the connection).
        Returns:
            bool: True if the connection was closed successfully, False otherwise."""
        for conn in self.connections:
            if conn.problem_instance_id == problem_instance_id:
                try:                
                    conn.close_connection()   # when agent node side of the connection is closed then the central node side will also close
                    conn.join()   # do not continue with this thread until conn thread is done
                    return True
                except Exception as e:
                    print(f"Error while closing connection when agent is stopping solving problem instance: {e}")
                    return False
        print("This problem instance is not being solved")
        return False
    

    def unexpected_connection_close(self, problem_instance_id: str):
        """Handle the case when a connection is closed unexpectedly (just used for testing)."""
        # So this method should close the connection but don't remove it from the set of connections
        for conn in self.connections:
            if conn.problem_instance_id == problem_instance_id:
                conn.connection.close()
    

    def remove_connection(self, connection: NodeConnection):
        """Remove a connection from the node's list of active connections."""
        try:
            self.connections.remove(connection)
        except KeyError as e:
            print(f"Error while removing connection from set of connections: {e}")
        #self.problem_instances_ids.remove(connection.problem_instance_id)
        
    

    def stop(self):
        """Stop solving all problem instances and close all connections - disconnect 
        from network."""
        print(f"Agent node ({str(self.id)}) stopping...")

        connections_copy = self.connections.copy()   # we copy the set since we are modifying it in the loop
        for conn in connections_copy:
            conn.close_connection()   # when agent node side of the connection is closed then the central node side will also close

        time.sleep(1)

        for conn in connections_copy:   # we call join() in seperate loop since otherwise we would need to wait for the connection to close before we can close the next one
            conn.join()


        self.connections = set()
        self.problem_instances_ids = set()

        print(f"Agent node ({self.id}) stopped")

