from typing import Set, Dict, TypedDict

import httpx
import shutil
import os
from dotenv import load_dotenv

load_dotenv()
CENTRAL_NODE_HOST = os.getenv("CENTRAL_NODE_HOST")
CENTRAL_NODE_PORT = os.getenv("CENTRAL_NODE_PORT")


class ProblemInstanceInfo(TypedDict):
    """Information about a problem instance that the agent node has stored. Agent stores information 
    the best solution found by itself and the best solution found by the platform in order to be able 
    to compare them and so solver can access them when needed."""
    name: str
    description: str
    instance_file_path: str
    best_platform_obj: int | None
    best_self_obj: int | None
    best_platform_sol_path: str | None
    best_self_sol_path: str | None
    reward_accumulated: int

    # TODO: maybe don't have this data structure fixed now we might discover that we need to store more information later on
    # Need to implement you know the solution phase and maybe validation also before
    # Do we actually want to use flags to indicate if this problme instance is being solved or not? and also if it is being validated or not?


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

        # Folder to store all agent data
        self.agent_data_path = f"../data/agent_data/agent_{self.name}"
        os.makedirs(self.agent_data_path, exist_ok=True)

        # Problem instances
        self.problem_instances_ids: Set[str] = set()  
        self.problem_instances: Dict[str, ProblemInstanceInfo] = dict()   # key is problem instance id and value is a dictionary with problem instance information
        self.problem_instances_path = f"{self.agent_data_path}/problem_instances"
        os.makedirs(self.problem_instances_path, exist_ok=True)

        # Problem instance that the agent is solving (for this proof of concept the agent is only solving one problem instance at a time)
        self.solving_problem_instance_id: str | None = None

        # Best solutions - agent keeps track of the best solutions on the platform (to aid with solving)
        self.best_platfrom_solutions_path = f"{self.agent_data_path}/best_platform_solutions"
        os.makedirs(self.best_platfrom_solutions_path, exist_ok=True)

        # Best solutions - agent keeps track of the best solutions found by itself
        self.best_self_solutions_path = f"{self.agent_data_path}/best_self_solutions"
        os.makedirs(self.best_self_solutions_path, exist_ok=True)

        print(f"Agent node named {self.name} started")

       

    def download_problem_instance(self):
        """Download a problem instance from the central node from a pool of problem instances 
        offerd by the central node and save it in local storage."""
        # Get pool of problem instances
        response = httpx.get(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/problem_instances/info")
        if response.status_code != 200:
            print(f"Error: {response.status_code} {response.text}")
            return
        problem_instances = response.json()

        # Select a problem instance from the pool - for now just select the first one
        problem_instance_name = problem_instances[0]["name"]

        # Download the problem instance
        self.download_problem_instance_data_by_name(problem_instance_name)

    
    def download_problem_instance_data_by_name(self, problem_instance_name: str):
        """Download a problem instance from the central node by its id and save it to local storage.
        It downloads the problem instance data, including the problem instance file and the best solution file 
        if it exists."""
        response = httpx.get(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/problem_instances/download/{problem_instance_name}")
        if response.status_code != 200:
            print(f"Error: {response.status_code} {response.text}")
            return
        problem_instance = response.json()

        # Save the problem instance to local storage
        with open(f"{self.problem_instances_path}/{problem_instance_name}.mps", "w") as file:
            file.write(problem_instance["problem_data"])

        # Check if there is a solution attached to the problem instance also
        if problem_instance["solution_data"]:
            with open(f"{self.best_platfrom_solutions_path}/{problem_instance_name}.sol", "w") as file:
                file.write(problem_instance["solution_data"])

        # Add the problem instance information to the agent's dictionary of problem instances
        # If first time downloading we need to create the dictionary entry then we need 
        # to create the dictionary entry but otherwise we need to update the dictionary entry
        # with e.g. new solution data
        if not problem_instance_name in self.problem_instances_ids:
            # Add the problem instance to the agent's set of problem instances
            self.problem_instances_ids.add(problem_instance_name)
            # Initialize the problem instance information dictionary
            self.problem_instances[problem_instance_name] = {
                "name": problem_instance_name,
                "description": problem_instance["description"],
                "instance_file_path": f"{self.problem_instances_path}/{problem_instance_name}.mps",
                "best_platform_obj": None,
                "best_self_obj": None,
                "best_platform_sol_path": None,
                "best_self_sol_path": None,
                "reward_accumulated": 0
            }
        else:
            # Update the problem instance information dictionary
            if problem_instance["solution_data"]:
                self.problem_instances[problem_instance_name]["best_platform_sol_path"] = f"{self.best_platfrom_solutions_path}/{problem_instance_name}.sol"
            

    def download_best_solution(self, problem_instance_name: str):
        """Download the best solution for a problem instance from the central node and save it to local storage."""
        pass


    def submit_solution(self, problem_instance_name: str, solution: str):
        """Submit a solution to the central node."""
        pass


    def check_submit_solution_status(self, solution_submission_id: str):
        """Check the status of a solution submission with the central node."""

        # Remove from agent's list of solutions that he is waiting on submission status for
        pass


    def validate_solution(self, problem_instance_name: str, solution: str):
        """Validate a solution with the central node."""
        # Request a solution to validate from the central node
        pass


    def print_problem_instances(self):
        """Print the problem instances that the agent has stored."""
        print("Problem instances stored by agent:")
        print(self.problem_instances)
    

    def clean_up(self):
        """Clean up the agent node."""
        # Delete the agent data folder
        shutil.rmtree(self.agent_data_path)

        print(f"Agent node named {self.name} cleaned up")