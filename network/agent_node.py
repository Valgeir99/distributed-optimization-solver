from typing import Set, Dict, TypedDict, Tuple

import httpx
import shutil
import os
import random
import logging
import csv
import json
from dotenv import load_dotenv
from config import AGENT_DATA_DIR, EXPERIMENT_DIR

from solver.bip_solver import BIPSolver

# Load environment variables from .env file
load_dotenv()
CENTRAL_NODE_HOST = os.getenv("CENTRAL_NODE_HOST")
CENTRAL_NODE_PORT = os.getenv("CENTRAL_NODE_PORT")

# Experiment configuration
EXPERIMENT_DATA_DIR = None
LOG_FILE_PATH = None
AGENT_REWARDS_DIR = None

# Constants
MAX_SOLVE_TIME = 300   # maximum time that agents spends finding a feasible solution for a problem instance in seconds TODO: not sure about this!! YES I think we should have this (but not sure about the value)
# One good thing about this is that we are using a random solver which means that in most cases the solver won't give a better solution than the best solution on the platform
# so instead of calling the agent solve function multiple times (with the overhead of for example doqnloading the best solution from the central node) we can just set a max solve time
# and if the solver does not find a better solution in that time we can just stop the solver and move on. I think we should inclue yes


class ProblemInstanceInfo(TypedDict):
    """Information about a problem instance that the agent node has stored. Agent stores information 
    the best solution found by itself and the best solution found by the platform in order to be able 
    to compare them and so solver can access them when needed."""
    name: str
    description: str
    instance_file_path: str
    best_platform_obj: float | None
    best_self_obj: float | None
    best_platform_sol_path: str   # NOTE this path might not exist if the best solution is not downloaded yet
    best_self_sol_path: str   # NOTE this path might not exist if the best solution is not found yet
    reward_accumulated: int
    active_solution_submission_ids: Set[str]  # Set of solution submission ids that the agent is waiting for submission status for
    active: bool   # True if the problem instance is still active on the platform, False otherwise


# Some design NOTE:
# - Code not designed to be run in a multi-threaded environment (would need to add locks for shared data if multiple threads)
# - The agent needs to download problem instance before he can do anything with it (solve, validate, get objective value of solution etc.)
# - The agent can only solve one problem instance at a time (but can store multiple problem instances)
# - The agent solves a problem instance until he finds a better feasible solution than the best solution on the platform, or until MAX_SOLVE_TIME is reached
# - The agent assumes minimization problems (and solver as well)
# - The agent and solver are seperate entities BUT they need to have access to the same local file storage
# - The agent downloads the best solution from the central node before validating a solution (this is the agent's implementation decision)
# - The agent keeps track of the best solutions on the platform and the best solutions found by itself
# - The agent can be malicous or not (malicous agent always returns False when validating a solution)

class AgentNode:
    # TODO: fix
    """An agent node that knows endpoints of central node web server and can communicate through there. 
    In the optimization solver platform this proof of concept is built from, the agent node is 
    anonomous and should be implemented however the owner of the node wants, the owner just needs 
    to follow the message protocol for the platform in order to be able to build his agent node. 
    However, in this proof of concept all agent nodes are the same and behave as described in this class.
    The agent node is only solving a single problem instance at a time, but can store multiple
    problem instances in local storage."""

    def __init__(self):
        """Initialize the node."""

        # Register to the platform to get a unique id
        self.id = self._register_to_platform()

        # With all http request we will use the agent id as a header so that the central node can identify the agent
        self.headers = {"agent-id": self.id}

        # Experiment configuration
        self._load_experiment_config()

        # Logger
        self.logger = self._setup_logger()
        self.logger.info(f"Agent node named {self.id} started")

        # Agent can be malicous or not
        self.malicous = False

        # Central node web server endpoints
        self.central_node_host = CENTRAL_NODE_HOST
        self.central_node_port = CENTRAL_NODE_PORT

        # Folder to store all temporary agent data for each run of the agent
        self.agent_data_path = f"{AGENT_DATA_DIR}/agent_{self.id}"
        if os.path.exists(self.agent_data_path):
            shutil.rmtree(self.agent_data_path, onexc=AgentNode._remove_readonly)
        os.makedirs(self.agent_data_path, exist_ok=False)   # we don't want to use exist_ok=True here since we want to start with an empty directory

        # Problem instances
        self.problem_instances_ids: Set[str] = set()  
        self.problem_instances: Dict[str, ProblemInstanceInfo] = dict()   # key is problem instance id and value is a dictionary with problem instance information
        self.problem_instances_path = f"{self.agent_data_path}/problem_instances"
        os.makedirs(self.problem_instances_path, exist_ok=False)

        # Problem instance that the agent is solving (for this proof of concept the agent is only solving one problem instance at a time) - if None then the agent is not solving any problem instance
        self.solving_problem_instance_name: str | None = None

        # Best solutions - agent keeps track of the best solutions on the platform (to aid with solving)
        self.best_platfrom_solutions_path = f"{self.agent_data_path}/best_platform_solutions"
        os.makedirs(self.best_platfrom_solutions_path, exist_ok=False)

        # Best solutions - agent keeps track of the best solutions found by itself
        self.best_self_solutions_path = f"{self.agent_data_path}/best_self_solutions"
        os.makedirs(self.best_self_solutions_path, exist_ok=False)

        # Solver
        self.solver = BIPSolver()


    def _load_experiment_config(self):
        """Load the experiment configuration that central node created from the config file."""
        global THIS_EXPERIMENT_DATA_DIR, LOG_FILE_PATH, AGENT_REWARDS_DIR
        with open(os.path.join(EXPERIMENT_DIR, "experiment_config.json"), "r") as f:
            config = json.load(f)
        THIS_EXPERIMENT_DATA_DIR = config["THIS_EXPERIMENT_DATA_DIR"]
        LOG_FILE_PATH = config["LOG_FILE_PATH"]
        AGENT_REWARDS_DIR = config["AGENT_REWARDS_DIR"]
    

    def _setup_logger(self) -> logging.Logger:
        """Set up the logger for the agent node."""
        # Create or get the logger for the specific agent
        logger = logging.getLogger(self.id)
        if not logger.hasHandlers():  # Avoid adding duplicate handlers
            # Create a file handler
            file_handler = logging.FileHandler(LOG_FILE_PATH, mode='a')
            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            
            # Set the logger's level
            logger.setLevel(logging.DEBUG)
            logger.addHandler(file_handler)

        # Suppress HTTP-related debug logs globally
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

        return logger


    ## Request functions to communicate with central node server ##

    def _register_to_platform(self) -> str:
        """Register to the platform by getting a unique id to identify with.
        
        Returns:
            id: The unique id of the agent node
        Raises:
            Exception: If the agent node fails to get an id from the central node
        """
        response = httpx.get(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/agent/register")
        if response.status_code != 200:
            raise Exception(f"Agent node cannot start - Failed to get id from central node - HTTP Error {response.status_code}: {response.text}")
        return response.json()["agent_id"]
    

    def download_problem_instance(self) -> str:
        """Download a problem instance from the central node from a pool of problem instances 
        offerd by the central node and save it in local storage. Agent uses random selection.
        Returns:
            problem_instance_name: The name of the problem instance that was downloaded | None if no problem instance was downloaded
        """
        self.logger.info("Request to download any problem instance...")
        # Get pool of problem instances
        response = httpx.get(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/problem_instances/info", headers=self.headers)
        if response.status_code != 200:
            self.logger.error(f"Failed to fetch pool of problem instances - HTTP Error {response.status_code}: {response.text}")
            return
        problem_instances = response.json()   # list of problem instances

        # Select a problem instance from the pool - select random one agent does not have stored yet
        problem_instance_name = None
        for problem_instance in random.sample(problem_instances, len(problem_instances)):
            if not problem_instance["name"] in self.problem_instances_ids:
                problem_instance_name = problem_instance["name"]
                break
        
        if problem_instance_name is None:
            self.logger.warning("No new problem instance available for download.")
            return
       
        # Download the problem instance
        self.download_problem_instance_data_by_name(problem_instance_name)

        return problem_instance_name

    
    def download_problem_instance_data_by_name(self, problem_instance_name: str):
        """Download a problem instance from the central node by its id and save it to local storage.
        It downloads the problem instance data, including the problem instance file and the best solution file 
        if it exists.
        Args:
            problem_instance_name: The name of the problem instance to download
        Returns:
            problem_instance_name: The name of the problem instance that was downloaded | None if the problem instance was not downloaded
        """
        self.logger.info(f"Request to downloaod problem instance {problem_instance_name}...")
        response = httpx.get(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/problem_instances/download/{problem_instance_name}", headers=self.headers)
        if response.status_code != 200:
            self.logger.error(f"Failed to download problem instance {problem_instance_name} - HTTP Error {response.status_code}: {response.text}")
            return
        problem_instance = response.json()

        # Save the problem instance to local storage
        problem_instance_file_path = f"{self.problem_instances_path}/{problem_instance_name}.mps"
        try:
            with open(problem_instance_file_path, "w") as file:
                file.write(problem_instance["problem_data"])
        except Exception as e:
            self.logger.error(f"Error when saving problem instance to local storage: {e}")
            return

        # Check if there is a solution attached to the problem instance also
        best_platform_sol_path = f"{self.best_platfrom_solutions_path}/{problem_instance_name}.sol"
        best_platform_obj = None
        try:
            if problem_instance["solution_data"]:
                with open(best_platform_sol_path, "w") as file:
                    file.write(problem_instance["solution_data"])
                # Get the objective value of the best solution
                best_platform_obj = self.solver.get_objective_value(problem_instance_name, problem_instance["solution_data"])
        except Exception as e:
            self.logger.error(f"Error when saving problem instance best solution to local storage and calculating objective: {e}")
            return

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
                "instance_file_path": problem_instance_file_path,
                "best_platform_obj": best_platform_obj,
                "best_self_obj": None,
                "best_platform_sol_path": best_platform_sol_path,
                "best_self_sol_path": f"{self.best_self_solutions_path}/{problem_instance_name}.sol",   # NOTE: it does not exits yet but this is the path where the agent will save the best solution found by itself
                "reward_accumulated": 0,
                "active_solution_submission_ids": set(),
                "active": True
            }

            try:
                # Add the problem instance to the solver
                self.solver.add_problem_instance(problem_instance_file_path)
            except Exception as e:
                self.logger.error(f"Error when adding problem instance to solver: {e}")
                return

            message = f"Problem instance {problem_instance_name} downloaded successfully for the first time and added to solver!"
        else:
            # Update the problem instance information dictionary - only update if solution data came with the download
            if problem_instance["solution_data"]:
                self.problem_instances[problem_instance_name]["best_platform_obj"] = best_platform_obj
            message = f"Problem instance {problem_instance_name} downloaded successfully (this problem instance was already stored by the agent)!"

        if problem_instance["solution_data"]:
            message += f"... and its best solution as well with objective value {best_platform_obj}"

        self.logger.info(message)

        return problem_instance_name


    def update_problem_instance_status(self, problem_instance_name: str):
        """Update the status of a problem instance in memory by checking with the central node to see if it is still active or not.
        If the problem instance is no longer active, the agent tags it as inactive and removes it from the agent's solver.
        
        Args:
            problem_instance_name: The name of the problem instance to check status for
        """
        self.logger.info(f"Request to check status of problem instance {problem_instance_name}...")
        response = httpx.get(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/problem_instances/status/{problem_instance_name}", headers=self.headers)
        if response.status_code != 200:
            self.logger.error(f"Failed to check status of problem instance {problem_instance_name} - HTTP Error {response.status_code}: {response.text}")
            return
        problem_instance_info = response.json()
        active = problem_instance_info["active"]
        
        if not active:
            # Remove the problem instance from the agent's solver
            try:
                self.solver.remove_problem_instance(problem_instance_name)
                self.logger.info(f"Problem instance {problem_instance_name} removed from solver")
            except Exception as e:
                self.logger.error(f"Error when removing problem instance from solver: {e}")
                return
        self.problem_instances[problem_instance_name]["active"] = active
        self.logger.info(f"Problem instance {problem_instance_name} status updated successfully - active={active}")   # TODO: maybe exessive logging so maybe only log if status changed
                

    def download_best_solution(self, problem_instance_name: str):
        """Download the best solution for a problem instance from the central node and save it to local storage."""
        self.logger.info(f"Request to download best solution for problem instance {problem_instance_name}...")

        # Check if the agent has the problem instance stored
        if not problem_instance_name in self.problem_instances_ids:
            self.logger.error(f"Agent does not have problem instance {problem_instance_name} stored")
            return
        
        response = httpx.get(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/solutions/best/download/{problem_instance_name}", headers=self.headers)
        if response.status_code != 200:
            self.logger.error(f"Failed to download best solution for problem instance {problem_instance_name} - HTTP Error {response.status_code}: {response.text}")
            return
        best_solution = response.json()

        # Save the best solution to local storage
        best_platform_sol_path = self.problem_instances[problem_instance_name]["best_platform_sol_path"]
        try:
            with open(best_platform_sol_path, "w") as file:
                file.write(best_solution["solution_data"])
        except Exception as e:
            self.logger.error(f"Error when saving best solution to local storage: {e}")
            return

        # Calculate the objective value of the best solution
        try:
            best_obj = self.solver.get_objective_value(problem_instance_name, best_solution["solution_data"])
        except Exception as e:
            self.logger.error(f"Error when calculating objective value of best solution: {e}")
            return
        
        # Update the problem instance information dictionary with the new best solution
        self.problem_instances[problem_instance_name]["best_platform_obj"] = best_obj

        self.logger.info(f"Best solution for problem instance {problem_instance_name} downloaded successfully with objective value {best_obj}")


    def submit_solution(self, problem_instance_name: str, solution_data: str):
        """Submit a solution to the central node get solution submission id in response
        so that agent can track the status of the solution submission."""
        self.logger.info(f"Request to submit solution for problem instance {problem_instance_name}...")
        response = httpx.post(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/solutions/upload/{problem_instance_name}", 
                              json={"solution_data": solution_data},
                              headers=self.headers)
        if response.status_code != 200:
            self.logger.error(f"Failed to submit solution for problem instance {problem_instance_name} - HTTP Error {response.status_code}: {response.text}")
            return
        solution_submission_id = response.json()["solution_submission_id"]
        self.problem_instances[problem_instance_name]["active_solution_submission_ids"].add(solution_submission_id)
        self.logger.info(f"Solution submitted for problem instance {problem_instance_name} with solution submission id {solution_submission_id}")


    def check_submit_solution_status(self, solution_submission_id: str):
        """Check the status of a solution submission with the central node to see how the validation is going. 
        Once the solution submission is validated, the agent will update the reward he has accumulated for this problem 
        instance and remove the solution submission from active solution submissions."""
        self.logger.info(f"Request to check status of solution submission {solution_submission_id}...")
        response = httpx.get(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/solutions/status/{solution_submission_id}", headers=self.headers)
        if response.status_code != 200:
            self.logger.error(f"Failed to check status of solution submission {solution_submission_id} - HTTP Error {response.status_code}: {response.text}")
            return
        solution_submission_info = response.json()

        # If the solution submission is validated (accepted or rejected), update the reward he has accumulated for this problem instance 
        # and remove it from the agent's list of active solution submissions
        problem_instance_name = solution_submission_info["problem_instance_name"]
        if solution_submission_info["accepted"] is not None:
            self.logger.info(f"Solution submission {solution_submission_id} has been validated - no need to check status again!")
            active_solution_submission_ids = self.problem_instances[problem_instance_name]["active_solution_submission_ids"]
            if solution_submission_id in active_solution_submission_ids:
                self.problem_instances[problem_instance_name]["reward_accumulated"] += solution_submission_info["reward"]
                active_solution_submission_ids.remove(solution_submission_id)
                self.logger.info(f"Agent has now collected solution submission reward ({solution_submission_info["reward"]} coins) for {solution_submission_id} and it has been removed from agent's active solution submissions")


    def validation_any_solution_request(self):
        """Request a solution to validate from the central node."""
        # TODO: maybe we want to allow this also but lets start with agent knowing the problem instance name before 
        # validating the solution
        pass


    def validate_solution_request(self, problem_instance_name: str):
        """Validate a solution with the central node. The agent must have the problem instance stored in order to validate the solution.
        The agent will download the solution from the central node (get request), validate it and send result to central node (post request).
        Args:
            problem_instance_name: The name of the problem instance that the solution belongs to
        """
        self.logger.info(f"Request to validate a solution for problem instance {problem_instance_name}...")
        # Check if agent has the problem instance stored
        if not problem_instance_name in self.problem_instances_ids:
            self.logger.error(f"Agent does not have problem instance {problem_instance_name} stored")
            return
        
        # Check if the problem instance is still active on the platform - since validating is not so expensive we will NOT update the status but only check in memory data
        if not self.problem_instances[problem_instance_name]["active"]:
            self.logger.error(f"Problem instance {problem_instance_name} is no longer active on the platform")
            return
        
        # Send request to central node to validate the solution - get sent solution back from central node
        response = httpx.get(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/solutions/validate/download/{problem_instance_name}", headers=self.headers)
        if response.status_code != 200:
            self.logger.error(f"Failed to validate a solution for problem instance {problem_instance_name} - HTTP Error {response.status_code}: {response.text}")
            return
        solution = response.json()

        # Validate the solution and calculate the objective value - first download best solution from central node (this is agent implementation decision)
        self.download_best_solution(problem_instance_name)
        solution_data = solution["solution_data"]
        validation_result, objective_value = self.validate_solution(problem_instance_name, solution_data)
        self.logger.info(f"Solution validation result: accepted={validation_result}")

        # Send the validation result back to the central node
        solution_submission_id = solution["solution_submission_id"]
        self.logger.info(f"Requesting to submit validation result to central node for solution submission {solution_submission_id}...")
        response = httpx.post(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/solutions/validate/{solution_submission_id}", 
                              json={"response": validation_result, "objective_value": objective_value},
                              headers=self.headers)
        if response.status_code != 200:
            self.logger.error(f"Failed to submit validation result for solution submission {solution_submission_id} - HTTP Error {response.status_code}: {response.text}")
            return
        solution_response = response.json()
        
        # Update the reward he has accumulated for this problem instance
        self.problem_instances[problem_instance_name]["reward_accumulated"] += solution_response["reward"]

        # TODO: ask Joe if we want this or not since this is good to have for us but maybe not general enough if we want to get some test results to see
        # how the platform could behave in real life when agents would probably not do this - well actually they might do this since they gain solving 
        # power since now the solver could have access to the best solution on the platform earlier than the validation phase ends! (see below)
        # TODO: this is also related to which solutions the platform will accept. I have talked about in central node that we might accept solutions even though 
        # they are not the best one because there might be two improved solution submissions at the same time (but this is not necessarly a bad thing this 
        # is just the price of having a decentralized system!) - WRITE THIS IN THE REPORT
        # If the solution was accepted, update the agent's best solution for the platform - NOTE malicous agent should not do this since they accept all solutions
        # if not self.malicous:
        #     if validation_result is True:
        #         try:
        #             with open(self.problem_instances[problem_instance_name]["best_platform_sol_path"], "w") as file:
        #                 file.write(solution_data)
        #             self.problem_instances[problem_instance_name]["best_platform_obj"] = objective_value
        #         except Exception as e:
        #             self.logger.error(f"Error when saving best solution to local storage: {e}")
        #             return
        #         self.logger.info(f"Agent has now updated the platform's best solution for problem instance {problem_instance_name} with objective value {objective_value}")

        self.logger.info(f"Solution submission {solution_submission_id} for problem instance {problem_instance_name} validated successfully and agent collected reward ({solution_response["reward"]} coins).")




    ## Agent functions ##

    
    def validate_solution(self, problem_instance_name: str, solution_data: str) -> Tuple[bool, float]:
        """Validate a solution. Solution needs to be feasible and better than the best known solution (best known 
        to the agent node).
        
        Args:
            problem_instance_name: The name of the problem instance that the solution belongs to
            solution_data: The solution data to validate in string format
        Returns:
            valid: True if the solution is valid, False otherwise
            obj_value: The objective value of the solution if it is valid, -1 otherwise
        """
        self.logger.info("Starting to validate solution...")
        if self.malicous:
            # Malicious agent - always return False
            self.logger.info("Malicious agent - always returning False when validating solution")
            return False, -1
        
        try:
            # Validate the solution
            valid, obj_value = self.solver.validate(problem_instance_name, solution_data, self.problem_instances[problem_instance_name]["best_platform_obj"])
            if valid:
                self.logger.info(f"Solution is valid! Comparing objective values: new objective is {obj_value} and old objective is {self.problem_instances[problem_instance_name]["best_platform_obj"]}")
            else:
                self.logger.info(f"Solution is NOT valid! Comparing objective values: new objective is {obj_value} and old objective is {self.problem_instances[problem_instance_name]["best_platform_obj"]}")
            return valid, obj_value
        except Exception as e:
            self.logger.error(f"Error when validating solution: {e}")
            return False, -1        

        
    def solve_problem_instance(self, problem_instance_name: str):
        """Solve a problem instance that the agent has downloaded."""

        self.logger.info(f"Starting to solve problem instance {problem_instance_name}...")

        # Check if the agent is already solving a problem instance
        if self.solving_problem_instance_name:
            self.logger.error(f"Agent is already solving problem instance {self.solving_problem_instance_name}")
            return

        # Check if the agent has the problem instance stored
        if not problem_instance_name in self.problem_instances_ids:
            self.logger.error(f"Agent does not have problem instance {problem_instance_name} stored")
            return
        
        # Check if the problem instance is still active on the platform
        self.update_problem_instance_status(problem_instance_name)
        if not self.problem_instances[problem_instance_name]["active"]:
            self.logger.error(f"Problem instance {problem_instance_name} is no longer active on the platform")
            return
        
        # Set the problem instance that the agent is solving
        self.solving_problem_instance_name = problem_instance_name

        # Get the best solution from the central node so that we don't submit a solution that is worse than the best solution on the platform
        self.download_best_solution(problem_instance_name)

        # Generate a better solution than the best one on the platform using the solver
        try:
            sol_found, obj, solution_data = self.solver.solve(problem_instance_name, self.problem_instances[problem_instance_name]["best_self_sol_path"], 
                                                              self.problem_instances[problem_instance_name]["best_platform_obj"], max_solve_time=MAX_SOLVE_TIME)   # TODO: what to do with max solve time?
            if sol_found:
                self.logger.info(f"Found a improved solution found for problem instance {problem_instance_name} with objective value {obj}")
                # Submit the solution to the central node
                self.submit_solution(problem_instance_name, solution_data)
                # Update the agent's best solution found by itself (already written to local storage in solve() function above)
                self.problem_instances[problem_instance_name]["best_self_obj"] = obj
            else:
                self.logger.info(f"Did not find a improved solution for problem instance {problem_instance_name}")

        except Exception as e:
            self.logger.error(f"Error when solving problem instance {problem_instance_name}: {e}")    
        
        # After solving is done, set the solving problem instance to None
        self.solving_problem_instance_name = None

        self.logger.info(f"Stopped solving problem instance {problem_instance_name}")



    ## Agent helper functions ##

    def print_problem_instances(self):
        """Print the problem instances that the agent has stored."""
        print(f"Problem instances stored by agent ({self.id}):")
        print(self.problem_instances)


    @staticmethod
    def _remove_readonly(func, path, exc_info):
        """Remove the read-only flag from a file or directory so that it can be deleted."""
        os.chmod(path, 0o777)
        func(path)


    def clean_up(self):
        """Clean up the agent node. Delete all agent data stored in local storage.
        Save reward accumulated found by agent to a file."""

        self.logger.info("Cleaning up agent node...")

        # Begin to check solution submission status for all active solution submissions - to collect rewards before quitting
        for problem_instance_name in self.problem_instances_ids:
            solution_submission_ids = self.problem_instances[problem_instance_name]["active_solution_submission_ids"].copy()
            for solution_submission_id in solution_submission_ids:
                self.check_submit_solution_status(solution_submission_id)

        # Delete the agent data folder
        shutil.rmtree(self.agent_data_path, onexc=AgentNode._remove_readonly)

        # Save the reward accumulated by the agent to a file
        with open(f"{AGENT_REWARDS_DIR}/agent_{self.id}_rewards.csv", "w", newline="") as file:
            writer = csv.writer(file)
            for problem_instance_name in self.problem_instances_ids:
                writer.writerow([problem_instance_name, self.problem_instances[problem_instance_name]["reward_accumulated"]])

        # Log some agent information
        msg = ""
        for problem_instance_name in self.problem_instances_ids:
            msg += f"For problem instance {problem_instance_name}:\n - Best solution found by agent: {self.problem_instances[problem_instance_name]['best_self_obj']} \
            \n - Reward accumulated: {self.problem_instances[problem_instance_name]['reward_accumulated']} \n"

        self.logger.info(msg)
        self.logger.info(f"Agent node cleaned up")

