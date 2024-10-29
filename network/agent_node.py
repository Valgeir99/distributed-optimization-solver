import socket
import time
import threading

from typing import Set

from .connection import NodeConnection
from .node import Node

# TODO: fix so that central node handles id creation for agent node

# TODO: fix so that agents can only solve single problem instances at a time but actually we should allow agent to store multiple
# problem instances even though it is only solving one of them at a time (e.g. for validation purposes)

class AgentNode(Node):
    """An agent node that is connected to a single central node and can send/receive data. 
    In the optimization solver platform this proof of concept is built from, the agent node is 
    anonomous and should be implemented however the owner of the node wants, the owner just needs 
    to follow the message protocol for the platform in order to be able to build his agent node. 
    However, in this proof of concept all agent nodes are the same and behave as described in this class.
    The agent node is only solving a single problem instance at a time, but can store multiple
    problem instances in local storage."""

    def __init__(self, id: int=None):
        """Initialize the node with ID."""
        super().__init__(id)
        
        self.connection: NodeConnection = None

        self.problem_instances_ids: Set[str] = set()   # TODO: do we need this? We have access to the problem instances through the connections - but maybe 
        # in the case where connection fails unexpectedly we might want to know which problem instances we were solving?

        print(f"Agent node ({self.id}) started")



    # TODO: maybe we want to change function naming so that it is more general to git with the whole platform and 
    # also if message protocol is applicable
    def connect_to_central_node(self, host: str, port: int) -> bool: 
        """Initiate a connection to a central node and create a socket for bidirectional communication.
        Returns:
            bool: True if the connection was successful, False otherwise.
        Args:
            host (str): The host address of the central node to connect to.
            port (int): The port number of the central node to connect to.
        """

        # This is should not be agent node respnsibility (so we need to make sure that central node handles this case instead)
        # TODO: should actually remove this at some point
        # But actually if I test to connect twice without this code part then the central node handles it correctly but 
        # the agent still thinks it is connected to the central node so it is really only the agent that looses in this 
        # situation, so maybe he should be responsible for checking?
        if self.connection is not None:
            if self.connection.connection.getpeername()[0] == host and self.connection.connection.getpeername()[1] == port:
                print("Already connected to this node with this problem instance")
                return False
         
        # Create connection to central node
        connection = None
        try:
            print(f"Try to connected from agent node ({self.id}) to central node")
            
            connection = socket.create_connection((host, port))   # automatically binds agent node's side of the connection to a random port
        
            # Send connection information to central node!
            connection.send((self.id).encode('utf-8'))   # send agent id and problem id to the connected node
            central_node_id = connection.recv(4096).decode('utf-8')   # when central node is connected, it sends its id


        # TODO: make unit tests for the exception (we would need to mock this and raise an exception)
        except socket.error as e:
            # Handle socket errors which should arise from the create_connection() method
            print(f"Failed to connect from agent node ({self.id}) to central node listening at {host}:{port} : {e}")
            if connection is not None:
                connection.close()   # when agent node side of the connection is closed then the central node side will also close
            return False
        
        thread_agent_node_side_connection = self.create_new_connection(connection, central_node_id)
        thread_agent_node_side_connection.start()
        self.connection = thread_agent_node_side_connection
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
    def check_connection(self):
        """Check if agent's connection is still alive.
        Returns:
            bool: True if alive, False otherwise."""
        pass
        # See socket_peeking.py example
        
            


    
    def receive_message_from_central_node(self, msg: str):
        """Handle message received from the central node."""
        pass

    
    def send_message_to_central_node(self, msg: str) -> bool:
        """Send message to the central node who gave this agent node the problem instance.
        Returns:
            bool: True if the message was sent successfully, False otherwise."""
        if self.connection is not None:
            self.connection.send(msg)
            return True
        print(f"Agent node ({self.id}) is not connected to a central node")
        return False

    
    # TODO: this method should really just be the same as the stop() method since there 
    # is not difference in agent disconnecting from central node and stopping (or I don't see 
    # how there should be a differnce)
    def disconnect_from_central_node(self) -> bool:
        """Disconnect from the central node and close the connection (central node will also close 
        its side of the connection).
        Returns:
            bool: True if the connection was closed successfully, False otherwise."""
        if self.connection is not None:
            try:
                self.connection.close_connection()   # when agent node side of the connection is closed then the central node side will also close
                self.connection.join()   # do not continue with this thread until conn thread is done
                self.connection = None
                return True
            except Exception as e:
                print(f"Error while closing connection when agent is disconnecting from central node: {e}")
                return False
        print("Agent node is not connected to a central node")
        return False
    

    def unexpected_connection_close(self):
        """Handle the case when a connection is closed unexpectedly (just used for testing)."""
        # So this method should close the connection but don't remove the actual connection class variable
        if self.connection is not None:
            self.connection.connection.close()
    

    def remove_connection(self, connection: NodeConnection):
        """Remove the connection."""
        self.connection = None
        #self.problem_instances_ids.remove(connection.problem_instance_id)
        
    

    def stop(self):
        """Stop the agent node activity and close the connection to central node, i.e. 
        disconnect from network."""
        print(f"Agent node ({str(self.id)}) stopping...")

        self.disconnect_from_central_node()
 
        self.problem_instances_ids = set()

        print(f"Agent node ({self.id}) stopped")

