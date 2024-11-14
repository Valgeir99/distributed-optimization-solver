from typing import Set, Dict, TypedDict, Tuple

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
    best_platform_obj: float | None
    best_self_obj: float | None
    best_platform_sol_path: str | None
    best_self_sol_path: str | None
    reward_accumulated: int
    active_solution_submission_ids: Set[str]  # Set of solution submission ids that the agent is waiting for submission status for

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

        # Agent can be malicous or not
        self.malicous = False

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
        self.solving_problem_instance_name: str | None = None

        # Best solutions - agent keeps track of the best solutions on the platform (to aid with solving)
        self.best_platfrom_solutions_path = f"{self.agent_data_path}/best_platform_solutions"
        os.makedirs(self.best_platfrom_solutions_path, exist_ok=True)

        # Best solutions - agent keeps track of the best solutions found by itself
        self.best_self_solutions_path = f"{self.agent_data_path}/best_self_solutions"
        os.makedirs(self.best_self_solutions_path, exist_ok=True)

        # Active solution submissions - agent keeps track of the solution submissions that are still pending
        #self.active_solution_submission_ids: Set[str] = set()  # NOTE: he does it in the problem instance info

        print(f"Agent node named {self.name} started")

    
    ## Request functions to communicate with central node server ##

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
                "reward_accumulated": 0,
                "active_solution_submission_ids": set()
            }
        else:
            # Update the problem instance information dictionary
            if problem_instance["solution_data"]:
                self.problem_instances[problem_instance_name]["best_platform_sol_path"] = f"{self.best_platfrom_solutions_path}/{problem_instance_name}.sol"
            

    def download_best_solution(self, problem_instance_name: str):
        """Download the best solution for a problem instance from the central node and save it to local storage."""
        pass



    def submit_solution(self, problem_instance_name: str, solution_data: str, objective_value: float):
        """Submit a solution to the central node get solution submission id in response
        so that agent can track the status of the solution submission."""
        response = httpx.post(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/solutions/upload/{problem_instance_name}", json={"solution_data": solution_data, "objective_value": objective_value})
        if response.status_code != 200:
            print(f"Error: {response.status_code} {response.text}")
            return
        solution_submission_id = response.json()["solution_submission_id"]
        self.problem_instances[problem_instance_name]["active_solution_submission_ids"].add(solution_submission_id)


    def check_submit_solution_status(self, solution_submission_id: str):
        """Check the status of a solution submission with the central node to see how the validation is going. 
        Once the solution submission is validated, the agent will update the reward he has accumulated for this problem 
        instance and remove the solution submission from active solution submissions."""
        response = httpx.get(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/solutions/status/{solution_submission_id}")
        if response.status_code != 200:
            print(f"Error: {response.status_code} {response.text}")
            return
        solution_submission_info = response.json()
        print(solution_submission_info)

        # If the solution submission is validated (accepted or rejected), update the reward he has accumulated for this problem instance 
        # and remove it from the agent's list of active solution submissions
        problem_instance_name = solution_submission_info["problem_instance_name"]
        if solution_submission_info["accepted"] is not None:
            print("Solution submission validated")
            active_solution_submission_ids = self.problem_instances[problem_instance_name]["active_solution_submission_ids"]
            if solution_submission_id in active_solution_submission_ids:
                print("should only print once here for each solution submission", solution_submission_id)
                self.problem_instances[problem_instance_name]["reward_accumulated"] += solution_submission_info["reward"]
                active_solution_submission_ids.remove(solution_submission_id)
       


    def validation_any_solution_request(self):
        """Request a solution to validate from the central node."""
        # TODO: maybe we want to allow this also but lets start with agent knowing the problem instance name before 
        # validating the solution
        pass


    def validate_solution_request(self, problem_instance_name: str):
        """Validate a solution with the central node. The agent must have the problem instance stored in order to validate the solution.
        The agent will download the solution from the central node (get request), validate it and send result to central node (post request)."""

        # Check if agent has the problem instance stored
        if not problem_instance_name in self.problem_instances_ids:
            print(f"Error: Agent does not have problem instance {problem_instance_name} stored")
            # TODO: here we can download the problem instance so that we can validate the solution
            return
        
        # Send reqeust to central node to validate the solution - get sent solution back from central node
        response = httpx.get(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/solutions/validate/download/{problem_instance_name}")
        if response.status_code != 200:
            print(f"Error: {response.status_code} {response.text}")
            return
        solution = response.json()

        # Validate the solution and calculate the objective value
        solution_data = solution["solution_data"]
        validation_result, objective_value = self.validate_solution(problem_instance_name, solution_data)

        # Send the validation result back to the central node
        solution_submission_id = solution["solution_submission_id"]
        response = httpx.post(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/solutions/validate/{solution_submission_id}", 
                              json={"response": validation_result, "objective_value": objective_value})
        if response.status_code != 200:
            print(f"Error: {response.status_code} {response.text}")
            return
        solution_response = response.json()
        
        # Update the reward he has accumulated for this problem instance TODO: migh have to use lock if we are running agent even loop async
        self.problem_instances[problem_instance_name]["reward_accumulated"] += solution_response["reward"]
       
       # TODO: here or create new request to check if the problem instance is still active or not (because if inactive on the platform 
       # we should remove it form the agent's problem instances. Also if the agent is solving this problem we would need to stop the
       # solver maybe if possible but could be complicated...)




    ## Agent functions ##

    
    def validate_solution(self, problem_instance_name: str, solution: str) -> Tuple[bool, float]:
        """Validate a solution."""

        obj_value = 109.8

        if self.malicous:
            # Malicious agent - always return False
            return False, obj_value
        
        # TODO: for now just so we can test the api endpoints we will always return True if not malicous - need to implement the validation!
        return True, obj_value

        # Validate the solution - read the solution file using the solver?
        # Check if file on correct format (.sol file) and as we have defined according to miplib sol file format
        #solver.

    


    ## Agent helper functions ##

    def print_problem_instances(self):
        """Print the problem instances that the agent has stored."""
        print(f"Problem instances stored by agent ({self.name}):")
        print(self.problem_instances)


    def clean_up(self):
        """Clean up the agent node."""
        # Delete the agent data folder
        shutil.rmtree(self.agent_data_path)

        print(f"Agent node named {self.name} cleaned up")



    ## Agent event loop ##

    def run(self):
        """Run the agent node event loop."""
        pass