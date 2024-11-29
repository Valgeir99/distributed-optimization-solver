import sqlite3
import threading
from fastapi import FastAPI
from dotenv import load_dotenv
import os
import shutil
import time
from datetime import datetime, timedelta
from typing import TypedDict, Dict
import uuid
import logging
import json

from utils.database_utils import create_and_init_database, teardown_database
from config import CENTRAL_DATA_DIR, DB_PATH, BEST_SOLUTIONS_DIR, EXPERIMENT_DIR, EXPERIMENT_DATA_DIR

# Experiment configuration
THIS_EXPERIMENT_DATA_DIR = None
LOG_FILE_PATH = None

# Load environment variables from .env file
load_dotenv()
CENTRAL_NODE_HOST = os.getenv("CENTRAL_NODE_HOST")
CENTRAL_NODE_PORT = int(os.getenv("CENTRAL_NODE_PORT"))
SOLUTION_VALIDATION_DURATION = int(os.getenv("SOLUTION_VALIDATION_DURATION"))  # seconds
SUCCESSFUL_SOLUTION_SUBMISSION_REWARD = int(os.getenv("SUCCESSFUL_SOLUTION_SUBMISSION_REWARD"))  # reward for successful solution submission
SOLUTION_VALIDATION_REWARD = int(os.getenv("SOLUTION_VALIDATION_REWARD"))  # reward for validating a solution
SOLUTION_VALIDATION_CONSENUS_RATIO = float(os.getenv("SOLUTION_VALIDATION_CONSENUS_RATIO"))  # ratio of validations needed to accept a solution
SOLUTION_VALIDATION_MIN_CONSENSUS = int(os.getenv("SOLUTION_VALIDATION_MIN_CONSENSUS"))  # minimum number of validations needed to accept a solution

# Other constants
RANDOM_PROBLEM_INSTANCE_POOL_SIZE = 10   # number of problem instances to choose from when selecting a problem instance for an agent


##--- Dataclass for active solution submissions ---##
class SolutionSubmissionInfo(TypedDict):
    """Information about a solution submission that is currently being validated."""
    problem_instance_name: str
    submission_time: datetime
    validation_end_time: datetime
    solution_data: str   # the solution file content
    objective_value: float   # the objective value of the solution calculated by the agent who submitted the solution
    validations: list[bool]   # True if agent accepted the solution, False if agent rejected the solution
    objective_values: list[float]   # the objective values of the agents that validated the solution
    reward_accumulated: int   # the reward given for this solution submission



# Some design NOTE (some are actually implemented in the central_node_server.py file - like pool size of problem instances given to agent TODO but just documenting here I think): 
# - The central node is designed so that there can only be one instance of the central node running at a time (singleton pattern).
#   If wanting to use multiple central nodes then we would need to change the solution validation in memory storage to a database 
#   and implement some kind of synchronization between the central nodes.
# - RANDOM_PROBLEM_INSTANCE_POOL_SIZE is the number of random problem instances that are given to an agent at a time to choose 
#   from (could include problem instances agent already has downloaded).
# - Central node gives a solution to an agent when asking for a solution to validate. Central node gives the agent a solution 
#   for a solution submission that is the oldest active submission, with minimum 30 seconds left and (is not yet validate by 
#   the agent TODO: implement that).
# - SOLUTION_VALIDATION_CONSENUS_RATIO and SOLUTION_VALIDATION_MIN_CONSENSUS are used to determine if a solution is accepted 
#   or not - we require a certain ratio of agents to accept the solution and a minimum number of agents to accept the solution.
#   Be careful to have the SOLUTION_VALIDATION_MIN_CONSENSUS not too low since solution validation phase can be finished before 
#   time limit and then it is good to have not too low of a value to keep integrity of the platform (but also not too high either).
# - SOLUTION_VALIDATION_DURATION is the time limit for the solution validation phase - after this time the solution is accepted 
#   or rejected based on consensus.
# - SUCCESSFUL_SOLUTION_SUBMISSION_REWARD is the reward given for an accepted solution submission.
# - SOLUTION_VALIDATION_REWARD is the reward given for validating a solution.
# - If a solution is submitted before reward for the corresponding problem instance is finished then the solution validation phase will 
#   start like normal and finish after time SOLUTION_VALIDATON_DURATION or until budget is depleted. While solution validation phase is 
#   running then we check regularly (each minute) if the total reward accumulated (both given out reward and reward for active solution 
#   submissions) for the corresponding problem instance is depleted. If gone over budget then we mark the problem instance as inactive 
#   and stop the solution validation phase so it will be finalized at that moment. This means that the reward for the problem instance 
#   can go over budget but only by a "small" amount, but at the same time we won't loose any active solution submission which might 
#   improve the best overall solution.
# - The central node keeps track of solution submissions using in memory storage (active_solution_submissions dictionary). 
#   It is nice to have this in memory since we need to access this data frequently and using different threads in the solution 
#   validation phase. Also this is just temporary storage and we will only store the final results in the database if successful 
#   solution submission.
# - The central node stores information about the problem instances in the database (problem_instances table).
# - The central node stores the best solutions in a folder (BEST_SOLUTIONS_DIR) and also in the database (best_solutions table).

# (in central_node_server.py - TODO: for clarity and seperation or roles we could actually create methods for this in central node like
#  get_pool_of_problem_instances() and so on and then call those methods in the server code??)
# - See api endpoints in central_node_server.py for more information about the API and how the agent can request things on the platform.



##--- CentralNode class ---##
class CentralNode:
    """A central node that has a web server to comminicate with agent nodes and stores data in a local database.

    TODO: add more description about the central node and its role in the platform."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        """Singleton pattern to ensure only one instance of the central node is created."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        else:
            raise Exception("CentralNode instance already exists!")
        return cls._instance
        

    def __init__(self, web_server: FastAPI):
        """Initialize the central node with a web server and initialize and connect to the database."""

        self.host = CENTRAL_NODE_HOST
        self.port = CENTRAL_NODE_PORT

        # Setup the experiment
        self.__setup_experiment()

        # Logger
        self.logger = self.__setup_logger()
        self.logger.info("Central node started")

        # Web server
        self.web_server = web_server
        
        # Lock for multithreading
        self.lock = threading.Lock()

        # Solution submissions that are currently being validated
        self.active_solution_submissions: Dict[str, SolutionSubmissionInfo] = dict()   # key is solutions submission id and value is a dictionary with solution submission information

        # Folder to store all temporary central node data for each run - create new folder for each run
        if os.path.exists(CENTRAL_DATA_DIR):
            shutil.rmtree(CENTRAL_DATA_DIR, onexc=CentralNode._remove_readonly)
        os.makedirs(CENTRAL_DATA_DIR, exist_ok=False)

        # Best solutions temp folder - create new folder for each run for central node to store best solutions
        self.best_solutions_folder = BEST_SOLUTIONS_DIR
        os.makedirs(self.best_solutions_folder, exist_ok=False)

        # Database
        self.db_path = DB_PATH
        create_and_init_database(self.db_path)
        self.db_connection = self.__connect_to_database()


    def __setup_experiment(self):
        """Setup the experiment configuration for central node and agents. Creates the directory for the experiment 
        data and log file. Saves the paths to a shared json file for agents to access."""
        global THIS_EXPERIMENT_DATA_DIR, LOG_FILE_PATH
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Create a new directory for the experiment with current timestamp
        THIS_EXPERIMENT_DATA_DIR = os.path.join(EXPERIMENT_DATA_DIR, f'experiment_{timestamp}')
        os.makedirs(THIS_EXPERIMENT_DATA_DIR, exist_ok=False)   # fail if directory already exists

        # Create a directory for storing agent rewards - this is folder agents will upload their rewards to after the experiment
        agent_rewards_dir = os.path.join(THIS_EXPERIMENT_DATA_DIR, 'agent_rewards')
        os.makedirs(agent_rewards_dir, exist_ok=False)
        
        # Create a new log file for this run - this is where all logs will be stored (also logs from agents)
        LOG_FILE_PATH = os.path.join(THIS_EXPERIMENT_DATA_DIR, f'log_{timestamp}.log')
        open(LOG_FILE_PATH, 'w').close()

        # Save paths to a shared json file for agent nodes to access
        shared_config = {
            "THIS_EXPERIMENT_DATA_DIR": THIS_EXPERIMENT_DATA_DIR,
            "AGENT_REWARDS_DIR": agent_rewards_dir,
            "LOG_FILE_PATH": LOG_FILE_PATH,
        }
        with open(os.path.join(EXPERIMENT_DIR, 'experiment_config.json'), 'w') as f:
            json.dump(shared_config, f, indent=4)


    def __setup_logger(self) -> logging.Logger:
        """Set up the logger for the central node."""
        # Create or get the logger for the specific agent
        logger = logging.getLogger("Central node")
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


    def __connect_to_database(self):
        """Create a connection to the database."""
        try:
            connection = sqlite3.connect(self.db_path, check_same_thread=False)   # check_same_thread=False is needed for multithreading
            self.logger.info(f"Connected to database at {self.db_path}")
            return connection
        except sqlite3.Error as e:
            # Raise exception to stop the program (we can't continue without the database)
            self.logger.error(f"Error while connecting to database at {self.db_path}: {e}")
            raise sqlite3.Error(f"Error while connecting to database at {self.db_path}: {e}")


    def __disconnect_from_database(self):
        """Close the connection to the database."""
        try:
            self.db_connection.close()
            self.logger.info(f"Disconnected from database at {self.db_path}")
        except sqlite3.Error as e:
            self.logger.error(f"Error while disconnecting from database at {self.db_path}: {e}")


    def query_db(self, query: str, params: tuple=()) -> list[dict] | None:
        """Query the database and return the result.
        Returns: 
            list: The result of the query or None if an error occurred."""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute(query, params)
            result = cursor.fetchall()
            # Return a list of dictionaries with the column names as keys
            columns = [description[0] for description in cursor.description]
            result_dict = [dict(zip(columns, row)) for row in result]
            cursor.close()
            return result_dict
        except sqlite3.Error as e:
            self.logger.error(f"Error while querying database at {self.db_path}: {e}")
            return None
        # NOTE: remember we need to check if the result is None when we call this function!!


    def edit_data_in_db(self, query: str, params: tuple=()):
        """Insert/Delete data in the database."""
        #with self.lock:   # NOTE: sqlite has built-in locking so we don't need to use this lock
        try:
            cursor = self.db_connection.cursor()
            cursor.execute(query, params)
            self.db_connection.commit()
            cursor.close()
        except sqlite3.Error as e:
            self.db_connection.rollback()
            self.logger.error(f"Error while editing data in database at {self.db_path}: {e}")
            raise sqlite3.Error(f"Error while editing data in database at {self.db_path}: {e}")
       

    def __save_db(self):
        """Save the working database to the experiment folder for this run."""
        backup_db_path = f"{THIS_EXPERIMENT_DATA_DIR}/central_node.db"
        try:
            with open(self.db_path, "rb") as f:
                with open(backup_db_path, "wb") as f2:
                    f2.write(f.read())
            self.logger.info(f"Database saved to {backup_db_path}")
        except Exception as e:
            self.logger.error(f"Error while saving database: {e}")


    def get_pool_of_problem_instances(self) -> list[dict] | None:
        """Get a pool of random active problem instances for an agent to choose from.
        Returns:
            list: A list of dictionaries with information about the problem instances or None if an error occurred.
        """
        return self.query_db("SELECT * FROM problem_instances WHERE active = TRUE ORDER BY RANDOM() LIMIT ?", (RANDOM_PROBLEM_INSTANCE_POOL_SIZE,))

            
    def generate_id(self):
        """Generate a unique id (for solution submissions)."""
        return str(uuid.uuid4())


    def start_solution_validation_phase(self, problem_instance_name: str, solution_submission_id: str, solution_data: str, objective_value: float):
        """Start the solution validation phase with a time limit for a solution submission."""
        submission_time = datetime.now()
        validation_end_time = submission_time + timedelta(seconds=SOLUTION_VALIDATION_DURATION)

        # Create a database entry for the solution submission
        try:
            self.edit_data_in_db(
                "INSERT INTO all_solutions (id, problem_instance_name, submission_time, validation_end_time) VALUES (?, ?, ?, ?)",
                (solution_submission_id, problem_instance_name, submission_time, validation_end_time)
            )
        except sqlite3.Error as e:
            self.logger.error(f"Error while inserting solution submission {solution_submission_id} to database - Solution validation phase aborted: {e}")
            return
        
        # Start a background thread for this solution submission validation - we use daemon threads so that this thread does not continue to run after the main thread (central node server) has finished
        validation_thread = threading.Thread(target=self._manage_validation_phase, args=(problem_instance_name, solution_submission_id, validation_end_time), daemon=True)
        validation_thread.start()

        # Store the validation phase information for this solution submission in memory for quick access and short-term storage
        self.active_solution_submissions[solution_submission_id] = {
            "problem_instance_name": problem_instance_name,
            "submission_time": submission_time,
            "validation_end_time": validation_end_time,
            "solution_data": solution_data,
            "objective_value": objective_value,
            "validations": [],
            "reward_accumulated": 0,
            "objective_values": []
        }

        self.logger.info(f"Started validation phase for solution submission {solution_submission_id} for problem instance {problem_instance_name}")

    def _manage_validation_phase(self, problem_instance_name: str, solution_submission_id: str, validation_end_time: datetime):
        """Manage the ongoing validation phase and end it after the time limit or if problem instance goes over budget."""
        while datetime.now() < validation_end_time:
            # The thread waits until the validation period expires - sleep for reasonable time since we are querying the database in the loop
            time.sleep(int(SOLUTION_VALIDATION_DURATION/20))
            #time.sleep(60)

            # Check if the reward for the problem instance is finished - if so then we tag problem instance as inactive and stop the validation phase
            results = self.query_db("SELECT reward_accumulated, reward_budget FROM problem_instances WHERE name = ?", (problem_instance_name,))
            if results is None:
                self.logger.error(f"Error while querying database for problem instance {problem_instance_name}")
                continue
            reward_accumulated = results[0]["reward_accumulated"]
            reward_budget = results[0]["reward_budget"]
            # Get current reward accumulated for all solution submissions for this problem instance
            active_reward = 0
            active_solution_submissions = self.active_solution_submissions.copy()
            for submission in active_solution_submissions.values():
                if submission["problem_instance_name"] == problem_instance_name:
                    active_reward += submission["reward_accumulated"]
            # Compare accumulated reward for this problem instance with the budget
            if reward_accumulated + active_reward >= reward_budget:
                try:
                    self.edit_data_in_db("UPDATE problem_instances SET active = False WHERE name = ?", (problem_instance_name,))
                except sqlite3.Error as e:
                    # On error we just log the error and continue to next iteration of the loop - we will try again next time
                    self.logger.error(f"Error while updating problem instance {problem_instance_name} to inactive in validation phase loop: {e}")
                self.logger.info((
                    f"Budget for problem instance {problem_instance_name} is finished - the problem instance will not be available anymore "
                      "all active solution submissions for this problem instance will be finalized soon"
                ))
                break

        # Process final validation after the time limit - use lock since we are accessing shared data (can also be accessed in central_node_server.py), 
        # e.g. we might be in the middle of finalizing validation while an agent is sending validation results so we need to be careful
        with self.lock:
            self._finalize_validation(problem_instance_name, solution_submission_id)

    def _finalize_validation(self, problem_instance_name: str, solution_submission_id: str):
        """Finalize validation based on the collected results."""
        self.logger.info(f"Finalizing validation for solution submission {solution_submission_id} for problem instance {problem_instance_name}")
        # Retrieve collected validation results
        solution_submission = self.active_solution_submissions.get(solution_submission_id)
        if solution_submission is None:
            self.logger.error(f"No data found for solution submission {solution_submission_id} for problem instance {problem_instance_name}")
            return
        
        objective_value = None
        validations = solution_submission["validations"]
        accepted = False
        if validations:
            # Calculate final status based on validations, e.g. majority vote and minimum number of acceptances
            acceptance_count = sum(validations)
            acceptance_ratio = acceptance_count / len(validations)
            if acceptance_ratio >= SOLUTION_VALIDATION_CONSENUS_RATIO and acceptance_count >= SOLUTION_VALIDATION_MIN_CONSENSUS:
                accepted = True

            # Use the most common objective value of the agents that accepted the solution as the objective value for this solution
            objective_values = solution_submission["objective_values"]
            if objective_values:
                # Calculate the most common objective value for accepted solutions
                accepted_objective_values = [objective_values[i] for i in range(len(validations)) if validations[i]]
                if accepted_objective_values:
                    objective_value = max(set(accepted_objective_values), key=accepted_objective_values.count)

        # If the solution is valid then it should be the best solution so far 
        # NOTE: it is not guaranteed that it is the best solution but there is nothing that the central node should do about that since it is the agents decision!
        if accepted:
            self.logger.info(f"Accepted solution submission for solution submission {solution_submission_id} for problem instance {problem_instance_name} with objective value {objective_value}")
            # Save solution data to file storage with best solutions
            solution_file_location = f"{self.best_solutions_folder}/{problem_instance_name}.sol"
            try:
                with open(solution_file_location, "w") as f:   # will create the file if it does not exist
                    f.write(solution_submission["solution_data"])
                self.logger.info(f"Best solution saved to file: {solution_file_location}")
            except Exception as e:
                self.logger.error(f"Error while saving best solution to file {solution_file_location}: {e}")

            # "Give" reward to the agent who submitted the solution
            # NOTE: we don't implement proper reward mechanism just emulating it by adding to the reward given for this solution submission
            solution_submission["reward_accumulated"] += SUCCESSFUL_SOLUTION_SUBMISSION_REWARD

            # Update the best solution in the database (or insert if it does not exist)
            try:
                self.edit_data_in_db("INSERT OR REPLACE INTO best_solutions (problem_instance_name, solution_id, file_location) VALUES (?, ?, ?)", (problem_instance_name, solution_submission_id, solution_file_location))
            except sqlite3.Error as e:
                self.logger.error(f"Error while updating best solution in database for problem instance {problem_instance_name}: {e}")

        else:
            self.logger.info(f"Declined solution submission for solution submission {solution_submission_id} for problem instance {problem_instance_name}")

        # Insert to db accumulated reward given for this solution submission, objective value and if it was accepted or not
        try:
            self.edit_data_in_db("UPDATE all_solutions SET reward_accumulated = ?, objective_value = ?, accepted = ? WHERE id = ?", (solution_submission["reward_accumulated"], objective_value, accepted, solution_submission_id))
        except sqlite3.Error as e:
            self.logger.error(f"Error while updating solution submission {solution_submission_id} in database: {e}")

        # Update the problem instance database table with the reward given for this solution submission
        try:
            self.edit_data_in_db("UPDATE problem_instances SET reward_accumulated = reward_accumulated + ? WHERE name = ?", (solution_submission["reward_accumulated"], problem_instance_name))
        except sqlite3.Error as e:
            self.logger.error(f"Error while updating problem instance {problem_instance_name} in database: {e}")

        # If the reward is finished then we should make this problem instance inactive
        results = self.query_db("SELECT reward_accumulated, reward_budget FROM problem_instances WHERE name = ?", (problem_instance_name,))
        if results is None:
            self.logger.error(f"Error while querying database for problem instance {problem_instance_name}")
        else:
            reward_accumulated = results[0]["reward_accumulated"]
            reward_budget = results[0]["reward_budget"]
            if reward_accumulated >= reward_budget:
                try:
                    self.edit_data_in_db("UPDATE problem_instances SET active = False WHERE name = ?", (problem_instance_name,))
                except sqlite3.Error as e:
                    self.logger.error(f"Error while updating problem instance {problem_instance_name} to inactive in finalize validation phase: {e}")
                self.logger.info(f"Budget for problem instance {problem_instance_name} is finished - the problem instance will not be available anymore")

        # Clean up in-memory tracking for this submission
        if solution_submission_id in self.active_solution_submissions:
            del self.active_solution_submissions[solution_submission_id]

        self.logger.info(f"Ended validation phase for solution submission {solution_submission_id} for problem instance {problem_instance_name}")

     
    def get_solution_submission_id(self, problem_instance_name: str) -> list[dict] | None:
        """Get the oldest active solution submission id with minimum 30 seconds left for a problem instance 
        (that is not yet validated by the agent TODO)."""
        # get the oldest active solution submission for the problem instance that has more than 30 seconds left for validation
        # TODO: Also don't want to give out solutions that this agent has already validated...
        # TODO: do we want to give out solutions randomly instead that agent has not validated? Maybe better so central node is 
        # not "controlling" anyting?
        cutoff_time = datetime.now() + timedelta(seconds=30)
        result = self.query_db(
            """SELECT id FROM all_solutions 
                WHERE problem_instance_name = ? 
                    AND accepted IS NULL 
                    AND validation_end_time >= ?
                ORDER BY submission_time ASC LIMIT 1
            """
            , (problem_instance_name, cutoff_time)
        )
        return result
    

    @staticmethod
    def _remove_readonly(func, path, exc_info):
        """Remove the read-only flag from a file or directory so that it can be deleted."""
        os.chmod(path, 0o777)
        func(path)


    def stop(self):
        """Stop the central node - save and close the database"""
        # Save the database
        self.__save_db()
        # Teardown the database
        teardown_database(self.db_path)
        # Disconnect from the database
        self.__disconnect_from_database()
        # Delete the central node temporary data folder
        shutil.rmtree(CENTRAL_DATA_DIR, onexc=CentralNode._remove_readonly)
        self.logger.info("Central node stopped")
         # Print the active solution submissions
        msg = "Active solution submissions after stopping central node:"
        for solution_submission_id in self.active_solution_submissions:
            msg += f"\n{solution_submission_id}"
        self.logger.info(msg)
