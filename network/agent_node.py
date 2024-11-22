from typing import Set, Dict, TypedDict, Tuple

import httpx
import shutil
import os
import random
import logging
from dotenv import load_dotenv
from config import AGENT_DATA_DIR, LOG_FILE_PATH
import solver.solver_python as solver

# Load environment variables from .env file
load_dotenv()
CENTRAL_NODE_HOST = os.getenv("CENTRAL_NODE_HOST")
CENTRAL_NODE_PORT = os.getenv("CENTRAL_NODE_PORT")

# Other constants
SOLVE_ITERATIONS = 1   # number of times to run the solver for each problem instance when solving


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
    best_self_sol_path: str
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

        # Logger
        self.logger = self._setup_logger()
        self.logger.info(f"Agent node named {self.name} started")

        # Agent can be malicous or not
        self.malicous = False

        # Central node web server endpoints
        self.central_node_host = CENTRAL_NODE_HOST
        self.central_node_port = CENTRAL_NODE_PORT

        # Folder to store all agent data
        #self.agent_data_path = f"{AGENT_DATA_DIR}/agent_{self.name}"
        self.agent_data_path = f"../data/agent_data/agent_{self.name}"
        os.makedirs(self.agent_data_path, exist_ok=True)

        # Problem instances
        self.problem_instances_ids: Set[str] = set()  
        self.problem_instances: Dict[str, ProblemInstanceInfo] = dict()   # key is problem instance id and value is a dictionary with problem instance information
        self.problem_instances_path = f"{self.agent_data_path}/problem_instances"
        os.makedirs(self.problem_instances_path, exist_ok=True)

        # Problem instance that the agent is solving (for this proof of concept the agent is only solving one problem instance at a time) - if None then the agent is not solving any problem instance
        self.solving_problem_instance_name: str | None = None

        # Best solutions - agent keeps track of the best solutions on the platform (to aid with solving)
        self.best_platfrom_solutions_path = f"{self.agent_data_path}/best_platform_solutions"
        os.makedirs(self.best_platfrom_solutions_path, exist_ok=True)

        # Best solutions - agent keeps track of the best solutions found by itself
        self.best_self_solutions_path = f"{self.agent_data_path}/best_self_solutions"
        os.makedirs(self.best_self_solutions_path, exist_ok=True)

        # Active solution submissions - agent keeps track of the solution submissions that are still pending
        #self.active_solution_submission_ids: Set[str] = set()  # NOTE: he does it in the problem instance info

        # TODO: might want to use try-except here to see if agent started correctly or not - because maybe we don't want to use exist_ok=True for the directories since they should be 
        # empty on initialization (but likely there will be agents with same id started previously so maybe we just make the dir and delete everything in it if it exists?)


    def _setup_logger(self) -> logging.Logger:
        """Set up the logger for the agent node."""
        # Create or get the logger for the specific agent
        logger = logging.getLogger(self.name)
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

    def download_problem_instance(self) -> str:
        """Download a problem instance from the central node from a pool of problem instances 
        offerd by the central node and save it in local storage. Agent uses random selection.
        Returns:
            problem_instance_name: The name of the problem instance that was downloaded | None if no problem instance was downloaded
        """
        self.logger.info("Request to download any problem instance...")
        # Get pool of problem instances
        response = httpx.get(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/problem_instances/info")
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
        """
        self.logger.info(f"Request to downloaod problem instance {problem_instance_name}...")
        response = httpx.get(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/problem_instances/download/{problem_instance_name}")
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
            print(f"Error when saving problem instance to local storage: {e}")
            return

        # Check if there is a solution attached to the problem instance also
        best_platform_sol_path = None
        best_platform_obj = None
        try:
            if problem_instance["solution_data"]:
                best_platform_sol_path = f"{self.best_platfrom_solutions_path}/{problem_instance_name}.sol"
                with open(best_platform_sol_path, "w") as file:
                    file.write(problem_instance["solution_data"])
                # Get the objective value of the best solution
                best_platform_obj = solver.get_objective_value_bip_solution(f"{self.problem_instances_path}/{problem_instance_name}.mps", best_platform_sol_path)
        except Exception as e:
            print(f"Error when saving problem instance best solution to local storage and calculating objective: {e}")
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
                "instance_file_path": f"{self.problem_instances_path}/{problem_instance_name}.mps",
                "best_platform_obj": best_platform_obj,
                "best_self_obj": None,
                "best_platform_sol_path": best_platform_sol_path,
                "best_self_sol_path": f"{self.best_self_solutions_path}/{problem_instance_name}.sol",   # NOTE: it does not exits yet but this is the path where the agent will save the best solution found by itself
                "reward_accumulated": 0,
                "active_solution_submission_ids": set()
            }
            self.logger.info(f"Problem instance {problem_instance_name} downloaded successfully for the first time!")
        else:
            # Update the problem instance information dictionary - only update if solution data came with the download
            if problem_instance["solution_data"]:
                self.problem_instances[problem_instance_name]["best_platform_sol_path"] = best_platform_sol_path
                self.problem_instances[problem_instance_name]["best_platform_obj"] = best_platform_obj
            self.logger.info(f"Problem instance {problem_instance_name} downloaded successfully (this problem instance was already stored by the agent)")


    # TODO
    # def check_problem_instance_status(self, problem_instance_name: str):
    #     """Check the status of a problem instance with the central node to see if it is still active or not."""
    #     response = httpx.get(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/problem_instances/status/{problem_instance_name}")
    #     if response.status_code != 200:
    #         print(f"Error: {response.status_code} {response.text}")
    #         return
    #     problem_instance_info = response.json()
    #     print(problem_instance_info)
            

    def download_best_solution(self, problem_instance_name: str):
        """Download the best solution for a problem instance from the central node and save it to local storage."""
        self.logger.info(f"Request to download best solution for problem instance {problem_instance_name}...")

        # Check if the agent has the problem instance stored
        if not problem_instance_name in self.problem_instances_ids:
            self.logger.error(f"Agent does not have problem instance {problem_instance_name} stored")
            return
        
        response = httpx.get(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/solutions/best/download/{problem_instance_name}")
        if response.status_code != 200:
            self.logger.error(f"Failed to download best solution for problem instance {problem_instance_name} - HTTP Error {response.status_code}: {response.text}")
            return
        best_solution = response.json()

        # Save the best solution to local storage
        try:
            with open(self.problem_instances[problem_instance_name]["best_platform_sol_path"], "w") as file:
                file.write(best_solution["solution_data"])
        except Exception as e:
            self.logger.error(f"Error when saving best solution to local storage: {e}")
            return

        # Calculate the objective value of the best solution
        best_obj = solver.get_objective_value_bip_solution(self.problem_instances[problem_instance_name]["instance_file_path"], self.problem_instances[problem_instance_name]["best_platform_sol_path"])
        
        # Update the problem instance information dictionary with the new best solution
        self.problem_instances[problem_instance_name]["best_platform_obj"] = best_obj

        self.logger.info(f"Best solution for problem instance {problem_instance_name} downloaded successfully with objective value {best_obj}")


    def submit_solution(self, problem_instance_name: str, solution_data: str, objective_value: float):
        """Submit a solution to the central node get solution submission id in response
        so that agent can track the status of the solution submission."""
        self.logger.info(f"Request to submit solution for problem instance {problem_instance_name}...")
        response = httpx.post(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/solutions/upload/{problem_instance_name}", json={"solution_data": solution_data, "objective_value": objective_value})
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
        response = httpx.get(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/solutions/status/{solution_submission_id}")
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
            # TODO: here we can download the problem instance so that we can validate the solution - change log message to info and add download here
            return
        
        # Send request to central node to validate the solution - get sent solution back from central node
        response = httpx.get(f"http://{CENTRAL_NODE_HOST}:{CENTRAL_NODE_PORT}/solutions/validate/download/{problem_instance_name}")
        if response.status_code != 200:
            self.logger.error(f"Failed to validate a solution for problem instance {problem_instance_name} - HTTP Error {response.status_code}: {response.text}")
            print(f"Error: {response.status_code} {response.text}")
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
                              json={"response": validation_result, "objective_value": objective_value})
        if response.status_code != 200:
            self.logger.error(f"Failed to submit validation result for solution submission {solution_submission_id} - HTTP Error {response.status_code}: {response.text}")
            return
        solution_response = response.json()
        
        # Update the reward he has accumulated for this problem instance TODO: migh have to use lock if we are running agent even loop async
        self.problem_instances[problem_instance_name]["reward_accumulated"] += solution_response["reward"]
       
        # TODO: here or create new request to check if the problem instance is still active or not (because if inactive on the platform 
        # we should remove it form the agent's problem instances. Also if the agent is solving this problem we would need to stop the
        # solver maybe if possible but could be complicated...)

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
            feasible, obj_value = solver.validate_feasibility_bip_solution(self.problem_instances[problem_instance_name]["instance_file_path"], solution_data)
            if feasible:
                # Compare the objective value with the agent's best known solution - NOTE: ASSUME ONLY MINIMIZATION PROBLEMS
                if self.problem_instances[problem_instance_name]["best_self_obj"] is None or obj_value < self.problem_instances[problem_instance_name]["best_self_obj"]:
                    return True, obj_value
                else:
                    return False, -1
            else:
                return False, -1
        except Exception as e:
            self.logger.error(f"Error when validating solution: {e}")
            return False, -1        



    # TODO: we want the solver to be a modular piece that can be easily replaced with another solver - so to have it like that 
    # we cannot have any return values or anything like that since we need to run it in different thread/process so I guess we would 
    # always need to either pass in mutable objects that we would change during the solving process and use that (like dict with fields for 
    # the objective and if the solution was found). We could have a python wrapper for all solvers that we want to use and then we can just call the wrapper function?
    # That is a good idea but still we would always need to call the wrapper in a seperate thread or process so that we can run it 
    # in parallel with the agent node. If we do wrapper and have e.g. process inside the wrapper that runs a C solver then we would still 
    # need to have like a file writing mechanism I guess to get the solution back to the agent node...?

        

    # NOTE: this function should preferably be run on a seperate thread I think (but we cannot run it as a seperate process since we need to share the data with the agent node)
    # However, the solver itself should be able to run as a seperate process since it is a seperate program (becasue we want to be able to use different solvers, even 
    # C solver or commercial solver that we cannot run in the same process as the agent node)
    def solve_problem_instance(self, problem_instance_name: str):
        """Solve a problem instance that the agent has stored. The agent will solve the problem instance 
        in a seperate thread or process so that it can continue to run its event loop and communicate with the central node.
        TODO should we then have the requirement to call this function in a seperate thread or process?"""
        self.logger.info(f"Starting to solve problem instance {problem_instance_name}...")
        # Check if the agent is already solving a problem instance
        if self.solving_problem_instance_name:
            self.logger.error(f"Error: Agent is already solving problem instance {self.solving_problem_instance_name}")
            return

        # Check if the agent has the problem instance stored
        if not problem_instance_name in self.problem_instances_ids:
            self.logger.error(f"Error: Agent does not have problem instance {problem_instance_name} stored")
            return
        
        # Set the problem instance that the agent is solving
        self.solving_problem_instance_name = problem_instance_name

        # Solve the problem instance - loop until some stopping criterion is met? TODO: now I just solve it x times but we should also definately check problem instance 
        # status to see if it is still active or not before we start solving it every time
        # Depends also what kind of solver we use and if we will allow that solver to have access to the best solution known on the platform...

        for _ in range(SOLVE_ITERATIONS):

            # Check if the problem instance is still active on the platform
            # TODO: need to first implement http endpoint for this in the central node (check_problem_instance_status)

            # Generate a solution using a solver - we can run the solver on a seperate thread or process if we want 
            try:
                # This takes a long time so we should run it on a seperate thread or process
                #solution_thread = threading.Thread(target=solver.solve_bip, args=(self.problem_instances[problem_instance_name]["instance_file_path"], self.problem_instances[problem_instance_name]["best_self_sol_path"]))
                #solution_thread.start()
                sol_found, solution_data, obj = solver.solve_bip(self.problem_instances[problem_instance_name]["instance_file_path"], self.problem_instances[problem_instance_name]["best_self_sol_path"], "best_self_sol_path")
            except Exception as e:
                self.logger.error(f"Error when solving problem instance {problem_instance_name}: {e}")   # TODO: not sure how we want to log solver errors - if doing properly we would need to raise exception in the solver and catch it here
                self.solving_problem_instance_name = None
                return   # TODO: do something

            # If found a solution...
            if sol_found:

                # Read solution from file that the solver has written   TODO: maybe we do this instead of returning the solution data from the solver?
                # with open(self.problem_instances[problem_instance_name]["best_self_sol_path"], "r") as file:
                #     solution_data = file.read()

                # Submit the solution on the platform if it is the best solution found by the agent (send request to central node)
                self.submit_solution(problem_instance_name, solution_data, obj)

                # Update the agent's best solution
                self.problem_instances[problem_instance_name]["best_self_obj"] = obj

                # TODO: would also make sense to save to file here but I think I already did that in the solver so maybe we should change that for consistency!

        
        # After loop is done, set the solving problem instance to None
        self.solving_problem_instance_name = None

        self.logger.info(f"Stopped solving problem instance {problem_instance_name}")


        # Not sure what we will do here exactly...
        # It should be generic enough so that I can maybe easily use different solvers
        # Maybe I will start with a python solver that is just a script (or maybe a class) that
        # solves it (not sure if I want to have there or here to check if the solution is best in network or 
        # not but that functionality should be easy to add later on)
        # I will definitely run it on a seperate thread but maybe even as a seperate process


    def stop_solving_problem_instance(self):
        """Stop solving the problem instance that the agent is currently solving."""
        # TODO: need to implement some way to stop the solver - maybe have a event or signal that the solver listens to?
        pass


    ## Agent helper functions ##

    def print_problem_instances(self):
        """Print the problem instances that the agent has stored."""
        print(f"Problem instances stored by agent ({self.name}):")
        print(self.problem_instances)


    @staticmethod
    def _remove_readonly(func, path, exc_info):
        """Remove the read-only flag from a file or directory so that it can be deleted."""
        os.chmod(path, 0o777)
        func(path)


    def clean_up(self):
        """Clean up the agent node."""
        # Delete the agent data folder
        shutil.rmtree(self.agent_data_path, onexc=AgentNode._remove_readonly)

        # Log some agent information
        msg = ""
        for problem_instance_name in self.problem_instances_ids:
            msg += f"For problem instance {problem_instance_name}:\n - Best solution found by agent: {self.problem_instances[problem_instance_name]['best_self_obj']}\n \
            - Reward accumulated: {self.problem_instances[problem_instance_name]['reward_accumulated']}\n"

        self.logger.info(f"Agent node cleaned up")

