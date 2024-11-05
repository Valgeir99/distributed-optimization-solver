from typing import Set, Dict, TypedDict

import httpx
import shutil
import os
from dotenv import load_dotenv

load_dotenv()
CENTRAL_NODE_HOST = os.getenv("CENTRAL_NODE_HOST")
CENTRAL_NODE_PORT = os.getenv("CENTRAL_NODE_PORT")


# TODO: fix so that agents can only solve single problem instances at a time but actually we should allow agent to store multiple
# problem instances even though it is only solving one of them at a time (e.g. for validation purposes)


class ProblemInstanceInfo(TypedDict):
    """Information about a problem instance that the agent node has stored. Agent stores information 
    the best solution found by itself and the best solution found by the platform in order to be able 
    to compare them and so solver can access them when needed."""
    id: str
    name: str
    description: str
    best_platform_obj: int
    best_self_obj: int
    file_location: str
    best_platform_sol_location: str
    best_self_sol_location: str


class AgentNode:
    # TODO: fix
    """An agent node that knows endpoints of central node web server and can communicate through there. 
    In the optimization solver platform this proof of concept is built from, the agent node is 
    anonomous and should be implemented however the owner of the node wants, the owner just needs 
    to follow the message protocol for the platform in order to be able to build his agent node. 
    However, in this proof of concept all agent nodes are the same and behave as described in this class.
    The agent node is only solving a single problem instance at a time, but can store multiple
    problem instances in local storage."""

    def __init__(self, name: str):
        """Initialize the node with name."""

        # Agent has a name (for logging purposes)
        self.name = str(name)

        # Central node web server endpoints
        self.central_node_host = CENTRAL_NODE_HOST
        self.central_node_port = CENTRAL_NODE_PORT
        

        # Problem instances
        self.problem_instances_ids: Set[str] = set()  
        self.problem_instances: Dict[str, ProblemInstanceInfo] = dict()   # key is problem instance id and value is a dictionary with problem instance information
        self.problem_instances_path = f"../problem_instances/agent_{self.name}"
        self.__create_problem_instance_folder()


        print(f"Agent node named {self.name} started")



    def __create_problem_instance_folder(self):
        """Create a folder for the agent's problem instances."""
        os.makedirs(self.problem_instances_path, exist_ok=True)
        

    def download_problem_instance(self):
        """Download a problem instance from the central node from a pool of problem instances 
        offerd by the central node and save it in local storage."""
        # Get pool of problem instances
        response = httpx.get(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/problem_instances/info")
        if response.status_code != 200:
            print(f"Error: {response.status_code} {response.text}")
            return
        problem_instances = response.json()
        print(problem_instances)

        # Select a problem instance from the pool - for now just select the first one
        problem_instance_id = problem_instances[0]["name"]
        print(problem_instance_id)

        # Download the problem instance
        self.download_problem_instance_by_id(problem_instance_id)

    
    def download_problem_instance_by_id(self, problem_instance_id: str):
        """Download a problem instance from the central node by its id and save it to local storage."""
        response = httpx.get(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/problem_instances/download/{problem_instance_id}")
        if response.status_code != 200:
            print(f"Error: {response.status_code} {response.text}")
            return
        problem_instance = response.json()
        print(problem_instance["name"]) 

        # Save the problem instance to local storage
        with open(f"{self.problem_instances_path}/{problem_instance_id}.mps", "w") as file:
            file.write(problem_instance["data"])

        # Add the problem instance to the agent's list of problem instances
        self.problem_instances_ids.add(problem_instance_id)

        # Add the problem instance information to the agent's dictionary of problem instances

  
    

    def clean_up(self):
        """Clean up the agent node."""
        # Delete the problem instances folder
        shutil.rmtree(self.problem_instances_path)

        print(f"Agent node named {self.name} cleaned up")