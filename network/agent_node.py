"""
Agent node programmed to solve optimization problems for the proof of concept distributed optimization solver platform.

Design NOTE on programmed agent:
- The agent request resources from the server node (problem instances, best solutions etc.) and communicates with the server node through HTTP requests 
  (server node needs to be running and accessible for the agent to work)
- The agent needs to download problem instance before he can do anything with it (solve, validate, get objective value of solution etc.)
- The agent uses local storage where he stores problem instances and best solutions (we create a temporary folder for each agent node where we store this data)
- The agent has a solver, parser and verifier compnent which are implemented in ../solver/bip_solver.py
- The agent can only solve one problem instance at a time (but can store multiple problem instances)
- The agent checks the status of the problem instance before solving it (if it is no longer active the agent will not solve it)
- The agent downloads the best solution from the server node before solving a problem instance so he is not submitting a worse solution than the best solution on the platform
- The agent solves a problem instance until he finds a better feasible solution than the best solution on the platform, or until MAX_SOLVE_TIME is reached (see solver)
- The agent assumes minimization problems (and solver as well)
- The agent downloads the best solution from the server node before validating a solution
- The agent validates a solution by comparing it to the best solution on the platform and the best solution found by itself
- The agent keeps track of the best solutions on the platform and the best solutions found by itself
- The agent can be malicous or not (malicous agent always returns False when validating a solution)
"""


from typing import Set, Dict, TypedDict, Tuple
import httpx
import shutil
import os
import random
import logging
import csv
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from config import SERVER_NODE_HOST, SERVER_NODE_PORT, EXPERIMENT_DIR

from solver.bip_solver import BIPSolver

# Experiment configuration
LOG_FILE_PATH: str = ""
THIS_EXPERIMENT_DIR: str = ""
AGENT_DATA_DIR: str = ""

# Agent configuration
load_dotenv()
MAX_SOLVE_TIME = int(os.getenv("MAX_SOLVE_TIME"))   # maximum time that agents spends finding a feasible solution for a problem instance in seconds


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


class AgentNode:
    """An agent node that knows HTTP endpoints of server node web server and can communicate through those. 
    In the optimization solver platform this proof of concept is built from, the agent node is 
    autonomous and should be implemented however the owner of the node wants, the owner just needs 
    to follow the message protocol for the platform in order to be able to build his agent node. 
    However, in this proof of concept all agent nodes are the same and behave as described above in this class.
    The agent node is made to operate sequentially, it only solves or validates a single problem instance at a time.
    However, the agent can store multiple problem instances in local storage."""

    def __init__(self, experiment_time: int = None, malicous: bool = False):
        """Initialize the node.
        For the experiments, we allow to set the experiment time (for data gathering) and if the agent is malicous or not."""

        # Register to the platform to get a unique id
        self.id = self._register_to_platform()

        # With all http request we will use the agent id as a header so that the server node can identify the agent
        self.headers = {"agent-id": self.id}

        # Experiment configuration
        self._load_experiment_config()

        # Logger
        self.logger = self._setup_logger()
        self.logger.info(f"Agent node named {self.id} started")

        # Agent can be malicous or not
        self.malicous = malicous

        # When the experiment for this agent should finish - used now to count the number of solve iterations
        self.experiment_end_time = datetime.now() + timedelta(seconds=experiment_time) if experiment_time else None
        self.logger.info(f"Agent node will run until {self.experiment_end_time}")

        # Server node web server endpoints
        self.server_node_host = SERVER_NODE_HOST
        self.server_node_port = SERVER_NODE_PORT

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
        self.solve_iterations = 0   # number of times agent did a solve iteration (try to see if performance scales with number of agents on the platform)


    def _load_experiment_config(self):
        """Load the experiment configuration that server node created from the config file."""
        global THIS_EXPERIMENT_DIR, LOG_FILE_PATH, AGENT_DATA_DIR
        with open(os.path.join(EXPERIMENT_DIR, "experiment_config.json"), "r") as f:
            config = json.load(f)
        THIS_EXPERIMENT_DIR = config["THIS_EXPERIMENT_DATA_DIR"]
        LOG_FILE_PATH = config["LOG_FILE_PATH"]
        AGENT_DATA_DIR = config["AGENT_DATA_DIR"]


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


    ## Request functions to communicate with server node web server ##

    def _register_to_platform(self) -> str:
        """Register to the platform by getting a unique id to identify with.
        
        Returns:
            id: The unique id of the agent node
        Raises:
            Exception: If the agent node fails to get an id from the server node
        """
        response = httpx.get(f"http://{SERVER_NODE_HOST}:{SERVER_NODE_PORT}/register", timeout=30.0)
        if response.status_code != 200:
            raise Exception(f"Agent node cannot start - Failed to get id from server node - HTTP Error {response.status_code}: {response.text}")
        return response.json()["agent_id"]
    

    def download_problem_instance(self) -> str | None:
        """Download a problem instance from the server node from a pool of problem instances 
        offerd by the server node and save it in local storage. Agent uses random selection.
        Returns:
            problem_instance_name: The name of the problem instance that was downloaded | None if no problem instance was downloaded
        """
        self.logger.info("Request to download any problem instance...")
        # Get pool of problem instances
        response = httpx.get(f"http://{SERVER_NODE_HOST}:{SERVER_NODE_PORT}/problem_instances/info", headers=self.headers, timeout=30.0)
        if response.status_code != 200:
            self.logger.error(f"Failed to fetch pool of problem instances - HTTP Error {response.status_code}: {response.text}")
            return None
        problem_instances = response.json()   # list of problem instances

        # Select a problem instance from the pool - select random one agent does not have stored yet
        problem_instance_name = None
        for problem_instance in random.sample(problem_instances, len(problem_instances)):
            if not problem_instance["name"] in self.problem_instances_ids:
                problem_instance_name = problem_instance["name"]
                break
        
        if problem_instance_name is None:
            self.logger.warning("No new problem instance available for download.")
            return None
       
        # Download the problem instance
        self.download_problem_instance_data_by_name(problem_instance_name)

        return problem_instance_name

    
    def download_problem_instance_data_by_name(self, problem_instance_name: str):
        """Download a problem instance from the server node by its id and save it to local storage.
        It downloads the problem instance data, including the problem instance file and the best solution file 
        if it exists.
        Args:
            problem_instance_name: The name of the problem instance to download
        Returns:
            problem_instance_name: The name of the problem instance that was downloaded | None if the problem instance was not downloaded
        """
        self.logger.info(f"Request to downloaod problem instance {problem_instance_name}...")
        response = httpx.get(f"http://{SERVER_NODE_HOST}:{SERVER_NODE_PORT}/problem_instances/download/{problem_instance_name}", headers=self.headers, timeout=30.0)
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
        """Update the status of a problem instance in memory by checking with the server node to see if it is still active or not.
        If the problem instance is no longer active, the agent tags it as inactive and removes it from the agent's solver.
        
        Args:
            problem_instance_name: The name of the problem instance to check status for
        """
        self.logger.info(f"Request to check status of problem instance {problem_instance_name}...")
        response = httpx.get(f"http://{SERVER_NODE_HOST}:{SERVER_NODE_PORT}/problem_instances/status/{problem_instance_name}", headers=self.headers, timeout=30.0)
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
        self.logger.info(f"Problem instance {problem_instance_name} status updated successfully - active={active}")
                

    def download_best_solution(self, problem_instance_name: str):
        """Download the best solution for a problem instance from the server node and save it to local storage."""
        self.logger.info(f"Request to download best solution for problem instance {problem_instance_name}...")

        # Check if the agent has the problem instance stored
        if not problem_instance_name in self.problem_instances_ids:
            self.logger.error(f"Agent does not have problem instance {problem_instance_name} stored")
            return
        
        response = httpx.get(f"http://{SERVER_NODE_HOST}:{SERVER_NODE_PORT}/solutions/best/download/{problem_instance_name}", headers=self.headers, timeout=30.0)
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


    def submit_solution(self, problem_instance_name: str, solution_data: str, objective_value: float):
        """Submit a solution to the server node get solution submission id in response
        so that agent can track the status of the solution submission."""
        self.logger.info(f"Request to submit solution for problem instance {problem_instance_name}...")
        response = httpx.post(f"http://{SERVER_NODE_HOST}:{SERVER_NODE_PORT}/solutions/submit/{problem_instance_name}", 
                              json={"solution_data": solution_data, "objective_value": objective_value},
                              headers=self.headers,
                              timeout=30.0)
        if response.status_code != 200:
            self.logger.error(f"Failed to submit solution for problem instance {problem_instance_name} - HTTP Error {response.status_code}: {response.text}")
            return
        solution_submission_id = response.json()["solution_submission_id"]
        self.problem_instances[problem_instance_name]["active_solution_submission_ids"].add(solution_submission_id)
        self.logger.info(f"Solution submitted for problem instance {problem_instance_name} with solution submission id {solution_submission_id}")


    def check_submit_solution_status(self, solution_submission_id: str):
        """Check the status of a solution submission with the server node to see how the validation is going. 
        Once the solution submission is validated, the agent will update the reward he has accumulated for this problem 
        instance and remove the solution submission from active solution submissions."""
        self.logger.info(f"Request to check status of solution submission {solution_submission_id}...")
        response = httpx.get(f"http://{SERVER_NODE_HOST}:{SERVER_NODE_PORT}/solutions/submit/status/{solution_submission_id}", headers=self.headers, timeout=30.0)
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


    def validate_solution_request(self, problem_instance_name: str) -> bool:
        """Validate a solution with the server node. The agent must have the problem instance stored in order to validate the solution.
        The agent will download the solution from the server node (get request), validate it and send result to server node (post request).
        Args:
            problem_instance_name: The name of the problem instance that the solution belongs to
        Returns:
            True if the solution was validated successfully, False otherwise
        """
        self.logger.info(f"Request to validate a solution for problem instance {problem_instance_name}...")
        # Check if agent has the problem instance stored
        if not problem_instance_name in self.problem_instances_ids:
            self.logger.error(f"Agent does not have problem instance {problem_instance_name} stored")
            return False
        
        # Check if the problem instance is still active on the platform - since validating is not so expensive we will NOT update the status but only check in memory data
        if not self.problem_instances[problem_instance_name]["active"]:
            self.logger.error(f"Problem instance {problem_instance_name} is no longer active on the platform")
            return False
        
        # Send request to server node to validate the solution - get sent solution back from server node
        response = httpx.get(f"http://{SERVER_NODE_HOST}:{SERVER_NODE_PORT}/solutions/validate/download/{problem_instance_name}", headers=self.headers, timeout=30.0)
        if response.status_code != 200:
            self.logger.error(f"Failed to validate a solution for problem instance {problem_instance_name} - HTTP Error {response.status_code}: {response.text}")
            # If no solution to validate then the agent cannot validate
            return False
        solution = response.json()

        # Validate the solution and calculate the objective value - first download best solution from server node (this is agent implementation decision)
        self.download_best_solution(problem_instance_name)
        solution_data = solution["solution_data"]
        validation_result, objective_value = self.validate_solution(problem_instance_name, solution_data)
        self.logger.info(f"Solution validation result: accepted={validation_result}")

        # Send the validation result back to the server node
        solution_submission_id = solution["solution_submission_id"]
        self.logger.info(f"Requesting to submit validation result to server node for solution submission {solution_submission_id}...")
        response = httpx.post(f"http://{SERVER_NODE_HOST}:{SERVER_NODE_PORT}/solutions/validate/{solution_submission_id}", 
                              json={"response": validation_result, "objective_value": objective_value},
                              headers=self.headers,
                              timeout=30.0)
        if response.status_code != 200:
            self.logger.error(f"Failed to submit validation result for solution submission {solution_submission_id} - HTTP Error {response.status_code}: {response.text}")
            return False
        solution_response = response.json()
        
        # Update the reward he has accumulated for this problem instance
        self.problem_instances[problem_instance_name]["reward_accumulated"] += solution_response["reward"]

        self.logger.info(f"Solution submission {solution_submission_id} for problem instance {problem_instance_name} validated successfully and agent collected reward ({solution_response["reward"]} coins).")

        return True



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
            # Validate the solution - input the better objective value of the best solution on the platform and the best solution found by the agent
            obj_best = min((self.problem_instances[problem_instance_name]["best_platform_obj"], self.problem_instances[problem_instance_name]["best_self_obj"]), key=lambda x: (x is None, x))
            valid, obj_value = self.solver.validate(problem_instance_name, solution_data, obj_best)
            if valid:
                self.logger.info(f"Solution is valid! Comparing objective values: new objective is {obj_value} and old objective is {obj_best}")
            else:
                self.logger.info(f"Solution is NOT valid! Comparing objective values: new objective is {obj_value} and old objective is {obj_best}")
            return valid, obj_value
        except Exception as e:
            self.logger.error(f"Error when validating solution: {e}")
            return False, 8888888888       

        
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

        # Get the best solution from the server node so that we don't submit a solution that is worse than the best solution on the platform
        self.download_best_solution(problem_instance_name)

        # Generate a better solution than the best one on the platform / best one found by the agent using the solver
        try:
            obj_best = min((self.problem_instances[problem_instance_name]["best_platform_obj"], self.problem_instances[problem_instance_name]["best_self_obj"]), key=lambda x: (x is None, x))
            sol_found, obj, solution_data, iterations = self.solver.solve(problem_instance_name, self.problem_instances[problem_instance_name]["best_self_sol_path"], 
                                                              obj_best, max_solve_time=MAX_SOLVE_TIME)
            if datetime.now() <= self.experiment_end_time:
                self.solve_iterations += iterations
            else:
                self.logger.info(f"Agent was in the middle of solving problem instance {problem_instance_name} when the experiment time ended - solve iterations: {self.solve_iterations}")
            if sol_found:
                self.logger.info(f"Found a improved solution found for problem instance {problem_instance_name} with objective value {obj}")
                # Submit the solution to the server node
                self.submit_solution(problem_instance_name, solution_data, obj)
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

        # Save the reward accumulated by the agent to a file (shared file for all agents)
        import fcntl
        with open(os.path.join(THIS_EXPERIMENT_DIR, "rewards.csv"), "a", newline="") as file:
            fcntl.flock(file, fcntl.LOCK_EX)
            try:
                writer = csv.writer(file)
                for problem_instance_name in self.problem_instances_ids:
                    writer.writerow([self.id, problem_instance_name, self.problem_instances[problem_instance_name]["reward_accumulated"]])
            finally:
                fcntl.flock(file, fcntl.LOCK_UN)

        # Save the number of solve iterations to a file (shared file for all agents)
        with open(os.path.join(THIS_EXPERIMENT_DIR, "solve_iterations.csv"), "a", newline="") as file:
            fcntl.flock(file, fcntl.LOCK_EX)
            try:
                writer = csv.writer(file)
                writer.writerow([self.id, self.solve_iterations])
            finally:
                fcntl.flock(file, fcntl.LOCK_UN)

        # Log some agent information
        msg = ""
        for problem_instance_name in self.problem_instances_ids:
            msg += f"For problem instance {problem_instance_name}:\n - Best solution found by agent: {self.problem_instances[problem_instance_name]['best_self_obj']} \
            \n - Reward accumulated: {self.problem_instances[problem_instance_name]['reward_accumulated']} \
            \n - Number of solve iterations: {self.solve_iterations}\n"

        self.logger.info(msg)
        self.logger.info(f"Agent node cleaned up")

