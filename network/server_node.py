"""
Server node ...

Design NOTE on programmed server node:
- The server node is designed so that there can only be one instance of the server node running at a time (singleton pattern).
- The server node has a SQLite database that stores relevant information for the platform (see ../database/schema.sql). A database manager 
  object is used to manage database connections for multiple threads used for the solution validation phase.
- The server node keeps track of the agent ids that are valid on the platform in a database table (agent_nodes). Agents need to register 
  with the server node to be able to participate in the platform.
- The server node stores problem instances in local file storage and information about the instances in the database (problem_instances table)
- The server node uses temporary storage for the solution data of active solution submissions and best solutions on the platform.
- The server node stores the best solutions on the platform in a temporary local file storage and information about the best solutions in the database 
  (best_solutions table). The best solutions are stored in a separate folder (best_solutions) in the server node temporary data folder.
- For the solution validation phase the server node registers all solution submissions in a database table (all_solutions) where it stores
  the metadata about the submissions. While a solution submission is active, i.e. it is available for agents to validate, the server node 
  keeps track the validation results for the solution submission in a database table (active_solutions_submissions_validations). It also 
  stores the solution data in a temporary storage in its file system. After the solution validation phase is finished the server node 
  stores the final results in the database (all_solutions table) and removes the temporary storage of the solution data (both from the 
  the database and the file system).
- The server node gives a solution to an agent when asking for a solution to validate. Server node gives the agent the oldest active
  solution submission that the agent did not submit by himself and that the agent has not validated before. The server node will 
  only give a solution submission that has at least 15 seconds left for validation.
- The server node "gives" rewards to agents for successful solution submissions and for validating solutions. The server node keeps track 
  of the rewards in the database for each problem instance and once the reward budget for a problem instance is reached the problem instance 
  is made inactive and no more solution submissions are accepted for that problem instance.
- The server node has a web server that agents can communicate with. See server_node_server.py for more information about the API and how
  the agent can request resources on the platform.
"""


import sqlite3
import threading
from fastapi import FastAPI
from dotenv import load_dotenv
import os
import shutil
import time
from datetime import datetime, timedelta
import uuid
import logging
import json
import traceback
from threading import local

from database.database_utils import create_and_init_database, teardown_database
from config import SERVER_NODE_HOST, SERVER_NODE_PORT, NETWORK_PARAMS_DIR, EXPERIMENT_DIR, EXPERIMENT_DATA_DIR

# Experiment configuration
THIS_EXPERIMENT_DATA_DIR: str = ""
LOG_FILE_PATH: str = ""

# Server node configuration
load_dotenv(dotenv_path=NETWORK_PARAMS_DIR)
SOLUTION_VALIDATION_DURATION = int(os.getenv("SOLUTION_VALIDATION_DURATION"))  # seconds
SOLUTION_VALIDATION_CONSENUS_RATIO = float(os.getenv("SOLUTION_VALIDATION_CONSENUS_RATIO"))  # ratio of positive validations needed to accept a solution out of all agents that can validate (all except the owner of the solution), e.g. majority vote is 0.5
SUCCESSFUL_SOLUTION_SUBMISSION_REWARD = int(os.getenv("SUCCESSFUL_SOLUTION_SUBMISSION_REWARD"))  # reward for successful solution submission
SOLUTION_VALIDATION_REWARD = int(os.getenv("SOLUTION_VALIDATION_REWARD"))  # reward for validating a solution
RANDOM_PROBLEM_INSTANCE_POOL_SIZE =  int(os.getenv("RANDOM_PROBLEM_INSTANCE_POOL_SIZE"))   # number of problem instances to choose from when selecting a problem instance for an agent


##--- ServerNode class ---##
class ServerNode:
    """A server node that has a web server (server_node_server.py) which handles requests from agent nodes and stores data in a local database.
    It's main purpose is to manage the platform and the solution validation phase for solution submissions from agents."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        """Singleton pattern to ensure only one instance of the server node is created."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        else:
            raise Exception("ServerNode instance already exists!")
        return cls._instance
        

    def __init__(self, web_server: FastAPI):
        """Initialize the server node with a web server and initialize and connect to the database."""

        self.host = SERVER_NODE_HOST
        self.port = SERVER_NODE_PORT

        # Setup the experiment
        self.__setup_experiment()

        # Logger
        self.logger = self.__setup_logger()
        self.logger.info("Server node started")

        # Web server
        self.web_server = web_server

        # Setup folders for all temporary data during each run of the server node/platform
        SERVER_DATA_DIR = os.path.join(THIS_EXPERIMENT_DATA_DIR, "server_data_tmp")
        if os.path.exists(SERVER_DATA_DIR):
            shutil.rmtree(SERVER_DATA_DIR, onexc=ServerNode._remove_readonly)
        os.makedirs(SERVER_DATA_DIR, exist_ok=False)
        # Folder to store best soluttions on the platform
        self.best_solutions_dir = os.path.join(SERVER_DATA_DIR, "best_solutions")
        if os.path.exists(self.best_solutions_dir):
            shutil.rmtree(self.best_solutions_dir, onexc=ServerNode._remove_readonly)
        os.makedirs(self.best_solutions_dir, exist_ok=False)
        # Folder to store solution data of active solution submissions
        self.active_solutions_dir = os.path.join(SERVER_DATA_DIR, "active_solutions")
        if os.path.exists(self.active_solutions_dir):
            shutil.rmtree(self.active_solutions_dir, onexc=ServerNode._remove_readonly)
        os.makedirs(self.active_solutions_dir, exist_ok=False)

        # Database - create database manager object to manage database connections for multiple threads
        self.db_path = os.path.join(SERVER_DATA_DIR, "server_node.db")
        create_and_init_database(self.db_path)
        self.db_manager = DatabaseManager(self.db_path, self.logger)
        self.db_manager.get_connection(threading.get_ident())   # get a connection for the main thread

        # Number of agents registered to the platform
        self.agent_counter = 0


    def __setup_experiment(self):
        """Setup the experiment configuration for server node and agents. Creates the directory for the experiment 
        data (and temporary data) and log file. Saves the paths to a shared json file for agents to access.
        Returns:
            str: The path to the experiment data directory.

        """
        global THIS_EXPERIMENT_DATA_DIR, LOG_FILE_PATH
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Create a new directory for the experiment with current timestamp
        THIS_EXPERIMENT_DATA_DIR = os.path.join(EXPERIMENT_DATA_DIR, f'experiment_{timestamp}')
        os.makedirs(THIS_EXPERIMENT_DATA_DIR, exist_ok=False)   # fail if directory already exists

        # Agent data temporary directory for each experiment
        AGENT_DATA_DIR = os.path.join(THIS_EXPERIMENT_DATA_DIR, 'agent_data_tmp')
        os.makedirs(AGENT_DATA_DIR, exist_ok=False)

        # Copy network parameter file to the experiment folder
        shutil.copy(NETWORK_PARAMS_DIR, THIS_EXPERIMENT_DATA_DIR)

        # Create a new log file for this run - this is where all logs will be stored (also logs from agents)
        LOG_FILE_PATH = os.path.join(THIS_EXPERIMENT_DATA_DIR, f'log_{timestamp}.log')
        open(LOG_FILE_PATH, 'w').close()

        shared_config = {
            "THIS_EXPERIMENT_DATA_DIR": THIS_EXPERIMENT_DATA_DIR,
            "AGENT_DATA_DIR": AGENT_DATA_DIR,
            "LOG_FILE_PATH": LOG_FILE_PATH,
        }
        with open(os.path.join(EXPERIMENT_DIR, 'experiment_config.json'), 'w') as f:
            json.dump(shared_config, f, indent=4)


    def __setup_logger(self) -> logging.Logger:
        """Set up the logger for the server node."""
        # Create or get the logger for the specific agent
        logger = logging.getLogger("Server node")
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


    def query_db(self, query: str, params: tuple=()) -> list[dict] | None:
        """Query the database and return the result.
        Returns: 
            list: The result of the query or None if an error occurred."""
        return self.db_manager.execute_query(query, params)
        # NOTE: remember we need to check if the result is None when we call this function!!


    def edit_data_in_db(self, query: str, params: tuple=(), commit: bool=True):
        """Insert/Delete data in the database."""
        self.db_manager.execute_write(query, params, commit)
       

    def __save_db(self):
        """Save the working database to the experiment folder for this run."""
        backup_db_path = f"{THIS_EXPERIMENT_DATA_DIR}/server_node.db"
        try:
            with open(self.db_path, "rb") as f:
                with open(backup_db_path, "wb") as f2:
                    f2.write(f.read())
            self.logger.info(f"Database saved to {backup_db_path}")
        except Exception as e:
            self.logger.error(f"Error while saving database: {e}")


    def register_agent_to_platform(self):
        """Registers agent node to the platform by generating a unique id for the agent and add 
        to the agent_node database table.
        
        Returns:
            str: The unique id of the agent | None: If an error occurred while registering the agent.
        """
        self.agent_counter += 1
        agent_id = "agent_" + str(self.agent_counter)
        try:
            self.edit_data_in_db("INSERT INTO agent_nodes (id) VALUES (?)", (agent_id,))
            return agent_id
        except sqlite3.Error as e:
            self.logger.error(f"Error while registering agent {agent_id} to platform: {e}")
            return None


    def get_pool_of_problem_instances(self) -> list[dict] | None:
        """Get a pool of random active problem instances for an agent to choose from.
        Returns:
            list: A list of dictionaries with information about the problem instances or None if an error occurred.
        """
        return self.query_db("SELECT * FROM problem_instances WHERE active = TRUE ORDER BY RANDOM() LIMIT ?", (RANDOM_PROBLEM_INSTANCE_POOL_SIZE,))

            
    def generate_solution_submission_id(self):
        """Generate a unique id (for solution submissions)."""
        return str(uuid.uuid4())


    def start_solution_validation_phase(self, problem_instance_name: str, solution_submission_id: str, agent_id: str, solution_data: str, objective_value: float):
        """Start the solution validation phase with a time limit for a solution submission.
        
        Args:
            problem_instance_name (str): The name of the problem instance.
            solution_submission_id (str): The unique id of the solution submission.
            agent_id (str): The id of the agent that submitted the solution.
            solution_data (str): The solution data as a string.
        Raises:
            Exception: If an error occurs while starting the validation phase.
        """
        submission_time = datetime.now()
        validation_end_time = submission_time + timedelta(seconds=SOLUTION_VALIDATION_DURATION)

        # Create a database entry for the solution submission
        try:
            sol_file_path = os.path.join(self.active_solutions_dir, f"{solution_submission_id}.sol")
            self.edit_data_in_db(
                "INSERT INTO all_solutions (id, agent_id, problem_instance_name, submission_time, validation_end_time, sol_file_path) VALUES (?, ?, ?, ?, ?, ?)",
                (solution_submission_id, agent_id, problem_instance_name, submission_time, validation_end_time, sol_file_path)
            )
        except sqlite3.Error as e:
            self.logger.error(f"Error while inserting solution submission {solution_submission_id} to database - Solution validation phase aborted: {e}")
            raise Exception(f"Error while inserting solution submission {solution_submission_id} to database - Solution validation phase aborted: {e}")
        
        # Save the solution data to a file
        try:
            with open(sol_file_path, "w") as f:
                f.write(solution_data)
        except Exception as e:
            self.logger.error(f"Error while saving tmp solution data to file {sol_file_path} - Solution validation phase aborted: {e}")
            raise Exception(f"Error while saving solution data to file {sol_file_path} - Solution validation phase aborted: {e}")
        
        def validation_thread_function():
            try:
                self.db_manager.get_connection(threading.get_ident(), solution_submission_id)
                self._manage_validation_phase(problem_instance_name, solution_submission_id, validation_end_time, objective_value)
            finally:
                self.db_manager.close_connection(threading.get_ident(), solution_submission_id)
        
        # Start a background thread for this solution submission validation - we use daemon threads so that this thread does not continue to run after the main thread (server node server) has finished
        validation_thread = threading.Thread(target=validation_thread_function, daemon=True)
        validation_thread.start()
        self.logger.info(f"Started validation phase for solution submission {solution_submission_id} for problem instance {problem_instance_name}")


    def _manage_validation_phase(self, problem_instance_name: str, solution_submission_id: str, validation_end_time: datetime, objective_value: float):
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
            if not results:
                self.logger.error(f"Problem instance {problem_instance_name} not found in database - SHOULD NOT HAPPEN")
                continue
            reward_accumulated =  results[0].get("reward_accumulated", 0)
            reward_budget = results[0].get("reward_budget", 0)
            if reward_accumulated and reward_budget:
                # Get current reward accumulated for all solution submissions for this problem instance
                results = self.query_db("SELECT SUM(reward) AS active_reward FROM active_solutions_submissions_validations WHERE problem_instance_name = ?", (problem_instance_name,))
                if results is None:
                    self.logger.error(f"Error while querying database for active solution submissions for problem instance {problem_instance_name}")
                    continue
                if not results:
                    # No active solution submissions for this problem instance - continue to next iteration of the loop
                    continue
                active_reward = results[0]["active_reward"] or 0
                # Compare accumulated reward for this problem instance with the budget
                if reward_accumulated + active_reward >= reward_budget:
                    try:
                        self.edit_data_in_db("UPDATE problem_instances SET active = False,  WHERE name = ?", (problem_instance_name,))
                    except sqlite3.Error as e:
                        # On error we just log the error and continue to next iteration of the loop - we will try again next time
                        self.logger.error(f"Error while updating problem instance {problem_instance_name} to inactive in validation phase loop: {e}")
                        continue
                    self.logger.info((
                        f"Budget for problem instance {problem_instance_name} is finished - the problem instance will not be available anymore "
                        "all active solution submissions for this problem instance will be finalized soon"
                    ))
                    break

        # Process final validation after the time limit 
        self._finalize_validation(problem_instance_name, solution_submission_id, objective_value)
           
           
    def _finalize_validation(self, problem_instance_name: str, solution_submission_id: str, objective_value: float):
        """Finalize validation based on the collected results."""
        self.logger.info(f"Finalizing validation for solution submission {solution_submission_id} for problem instance {problem_instance_name}")

        try:
            # Begin a database transaction so that we can do multiple operations in the database and commit them all at once
            # NOTE: This is both for data consistency if one operation in this function fails then we decline the solution submission by default,
            # and in the case that an agent is validating the solution at the same time as we are finalizing it
            database_transactions = []
        
            # Retrieve collected validation results
            results = self.query_db("SELECT * FROM active_solutions_submissions_validations WHERE solution_submission_id = ?", (solution_submission_id,))
            if results is None:
                self.logger.error(f"Error while querying database for solution submission {solution_submission_id}")
                return
            validations = [result["validation_response"] for result in results] if results else []
            objective_values = [result["objective_value"] for result in results] if results else []
            reward_accumulated = sum(result["reward"] for result in results) if results else 0
            
            # Determine the result of the validation phase
            # Check if there is only a single agent on the platform - then we accept the solution by default
            if self.agent_counter == 1:
                objective_value = objective_value
                accepted = True
                accepted_count = 1
                rejected_count = 0
            else:
                objective_value = None
                accepted = False
                accepted_count = 0
                rejected_count = 0
                if validations and objective_values:
                    # Calculate final status based on validations, e.g. majority vote
                    accepted_count = sum(validations)
                    rejected_count = len(validations) - accepted_count
                    acceptance_ratio = accepted_count / (self.agent_counter - 1)   # NOTE: we don't count the agent that submitted the solution
                    if acceptance_ratio >= SOLUTION_VALIDATION_CONSENUS_RATIO:
                        accepted = True

                    # Use the most common objective value of the agents that accepted the solution as the objective value for this solution
                    if objective_values:
                        # Calculate the most common objective value for accepted solutions
                        if accepted:
                            accepted_objective_values = [objective_values[i] for i in range(len(validations)) if validations[i]]
                            if accepted_objective_values:
                                objective_value = max(set(accepted_objective_values), key=accepted_objective_values.count)
                        # Or use the most common objective value for all validations if the solution was not accepted
                        else:
                            objective_value = max(set(objective_values), key=objective_values.count)

            # Get the file path of the solution data
            results = self.query_db("SELECT sol_file_path FROM all_solutions WHERE id = ?", (solution_submission_id,))
            if results is None:
                self.logger.error(f"Error while querying database for solution submission {solution_submission_id}")
                return
            solution_file_location_tmp = results[0]["sol_file_path"]

            # If the solution is valid then it should be the best solution so far 
            # NOTE: it is not guaranteed that it is the best solution but there is nothing that the server node should do about that since it is the agents decision!
            if accepted:
                self.logger.info(f"Accepted solution submission for solution submission {solution_submission_id} for problem instance {problem_instance_name} with objective value {objective_value}")
                # Save solution data to file storage with best solutions
                try:
                    with open(solution_file_location_tmp, "r") as f:
                        solution_data = f.read()
                except Exception as e:
                    self.logger.error(f"Error while reading solution data from tmp file {solution_file_location_tmp}: {e}")
                    return
                solution_file_location_best = f"{self.best_solutions_dir}/{problem_instance_name}.sol"
                try:
                    with open(solution_file_location_best, "w") as f:   # will create the file if it does not exist
                        f.write(solution_data)
                    self.logger.info(f"Best solution saved to file: {solution_file_location_best}")
                except Exception as e:
                    self.logger.error(f"Error while saving best solution to file {solution_file_location_best}: {e}")

                # "Give" reward to the agent who submitted the solution
                reward_accumulated += SUCCESSFUL_SOLUTION_SUBMISSION_REWARD

                # Update the best solution in the database (or insert if it does not exist)
                try:
                    database_transactions.append(("INSERT OR REPLACE INTO best_solutions (problem_instance_name, solution_id, file_location) VALUES (?, ?, ?)",
                                                 (problem_instance_name, solution_submission_id, solution_file_location_best))
                    )
                except sqlite3.Error as e:
                    self.logger.error(f"Error while updating best solution in database for problem instance {problem_instance_name}: {e}")

            else:
                self.logger.info(f"Declined solution submission for solution submission {solution_submission_id} for problem instance {problem_instance_name} with objective value {objective_value}")

            # Insert to db accumulated reward given for this solution submission, objective value, if it was accepted or not and remove the solution data file path
            try:
                database_transactions.append(("UPDATE all_solutions SET reward_accumulated = ?, objective_value = ?, accepted = ?, active = FALSE, accepted_count = ?, rejected_count = ?, sol_file_path = NULL WHERE id = ?",
                                             (reward_accumulated, objective_value, accepted, accepted_count, rejected_count, solution_submission_id))
                )
            except sqlite3.Error as e:
                self.logger.error(f"Error while updating solution submission {solution_submission_id} in database: {e}")

            # Update the problem instance database table with the reward given for this solution submission
            try:
                database_transactions.append(("UPDATE problem_instances SET reward_accumulated = reward_accumulated + ? WHERE name = ?",
                                             (reward_accumulated, problem_instance_name))
                )
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
                        database_transactions.append(("UPDATE problem_instances SET active = False WHERE name = ?",
                                                     (problem_instance_name,))
                        )
                    except sqlite3.Error as e:
                        self.logger.error(f"Error while updating problem instance {problem_instance_name} to inactive in finalize validation phase: {e}")
                    self.logger.info(f"Budget for problem instance {problem_instance_name} is finished - the problem instance will not be available anymore")

            # Remove the solution data file from the temporary storage
            try:
                os.remove(solution_file_location_tmp)
            except Exception as e:
                self.logger.error(f"Error while removing tmp solution data file {solution_file_location_tmp}: {e}")
            
            # Clean up all rows in the active_solutions_submissions_validations table for this solution submission
            try:
                database_transactions.append(("DELETE FROM active_solutions_submissions_validations WHERE solution_submission_id = ?",
                                             (solution_submission_id,))
                )
            except sqlite3.Error as e:
                self.logger.error(f"Error while deleting validation results for solution submission {solution_submission_id}: {e}")

            self.logger.info(f"Ended validation phase for solution submission {solution_submission_id} for problem instance {problem_instance_name}")

            # Execute all database transactions
            try:
                self.db_manager.execute_transaction(database_transactions)
            except sqlite3.Error as e:
                self.logger.error(f"Error while committing transactions for solution submission {solution_submission_id} for problem instance {problem_instance_name}: {e}")


        except Exception as e:
            # If an error occurs while finalizing the validation then we should decline the solution by default and rollback the database transaction
            self.logger.error(f"Error while finalizing validation for solution submission {solution_submission_id} for problem instance {problem_instance_name} \
                              - the solution will be declined by default: {e} {traceback.format_exc()}")
            try:
                self.edit_data_in_db("UPDATE all_solutions SET accepted = FALSE, active = FALSE WHERE id = ?", (solution_submission_id,))
            except sqlite3.Error as e:
                self.logger.error(f"Error while updating solution submission {solution_submission_id} in database: {e}")


     
    def get_solution_submission_id(self, problem_instance_name: str, agent_id: str) -> list[dict] | None:
        """Get an active solution submission with at least 15 seconds left for validation that this agent is 
        not the owner of and that the agent has not validated before.
        
        Args:
            problem_instance_name (str): The name of the problem instance.
            agent_id (str): The id of the agent requesting the solution submission.
        Returns:
            list: A list with the solution submission id or None if an error occurred.
        """
        cutoff_time = datetime.now() + timedelta(seconds=15)
        result = self.query_db(
            """SELECT id 
                FROM all_solutions 
                WHERE problem_instance_name = ? 
                    AND active IS TRUE 
                    AND agent_id != ?
                    AND validation_end_time >= ?
                    AND id NOT IN (
                        SELECT solution_submission_id
                        FROM active_solutions_submissions_validations
                        WHERE agent_validated_id = ?
                    )
                ORDER BY submission_time ASC LIMIT 1
            """
            , (problem_instance_name, agent_id, cutoff_time, agent_id)
        )
        if result is None:
            self.logger.error(f"Error while querying database for solution submission for problem instance {problem_instance_name}")
            return None
       
        return result
    

    def register_solution_validation(self, solution_submission_id: str, problem_instance_name: str, agent_id: str, validation_response: bool, objective_value: float):
        """Register a validation of a solution submission from an agent to the database.
        
        Args:
            solution_submission_id (str): The unique id of the solution submission.
            problem_instance_name (str): The name of the problem instance.
            agent_id (str): The id of the agent that validated the solution.
            validation_response (bool): The response of the validation (True if accepted, False if declined).
            objective_value (float): The objective value of the solution.
            reward (int): The reward given to the agent for validating the solution.
        Raises:
            sqlite3.Error: If an error occurs while registering the validation.
        """
        try:
            self.edit_data_in_db(
            """INSERT INTO active_solutions_submissions_validations 
                        (solution_submission_id, problem_instance_name, agent_validated_id, validation_response, objective_value, reward) 
                    VALUES 
                        (?, ?, ?, ?, ?, ?)
                """
                , (solution_submission_id, problem_instance_name, agent_id, validation_response, objective_value, SOLUTION_VALIDATION_REWARD)
            )
        except sqlite3.Error as e:
            self.logger.error(f"Error while registering validation for solution submission {solution_submission_id} for problem instance {problem_instance_name}: {e}")
            raise sqlite3.Error(f"Error while registering validation for solution submission {solution_submission_id} for problem instance {problem_instance_name}: {e}")


    def get_solution_success_reward(self) -> int:
        """Get the reward for improving the best solution of the platform."""
        return SUCCESSFUL_SOLUTION_SUBMISSION_REWARD
    

    def get_solution_validation_reward(self) -> int:
        """Get the reward for validating a solution."""
        return SOLUTION_VALIDATION_REWARD


    @staticmethod
    def _remove_readonly(func, path, exc_info):
        """Remove the read-only flag from a file or directory so that it can be deleted."""
        os.chmod(path, 0o777)
        func(path)


    def stop(self):
        """Stop the server node - save and close the database"""
        # Print the active solution submissions
        msg = "Active solution submissions after stopping server node:"
        results = self.query_db("SELECT id FROM all_solutions WHERE accepted IS NULL")
        if results is None:
            self.logger.error("Error while querying database for active solution submissions")
        else:
            if results:
                for result in results:
                    msg += f"\n{result["id"]}"
        self.logger.info(msg)
        # Save the database
        self.__save_db()
        time.sleep(5)
        # Teardown the database
        teardown_database(self.db_path)
        # Disconnect from the database
        self.db_manager.close_connection(threading.get_ident())
        # Delete the server node temporary data folders
        shutil.rmtree(self.best_solutions_dir, onexc=ServerNode._remove_readonly)
        shutil.rmtree(self.active_solutions_dir, onexc=ServerNode._remove_readonly)
        self.logger.info("Server node stopped")



##--- DatabaseManager class ---##
class DatabaseManager:
    """A class to manage SQLite database connections for multiple threads."""
    def __init__(self, db_path:str, logger: logging.Logger):
        self.db_path = db_path
        self.logger = logger
        self.thread_local = local()   # stores connection for each thread


    def get_connection(self, thread_id, sumbission_id=None) -> sqlite3.Connection:
        """Get or create a SQLite connection for the current thread."""
        if not hasattr(self.thread_local, "connection"):
            self.thread_local.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            if sumbission_id:
                self.logger.info(f"Connected to database at {self.db_path} for thread {thread_id} for solution submission {sumbission_id}")
            else:
                self.logger.info(f"Connected to database at {self.db_path} for thread {thread_id} (this is web server thread)")
        return self.thread_local.connection
    
    def close_connection(self, thread_id, sumbission_id=None):
        """Close the SQLite connection for the current thread."""
        if hasattr(self.thread_local, "connection"):
            try:
                self.thread_local.connection.close()
                if sumbission_id:
                    self.logger.info(f"Disconnected from database at {self.db_path} for thread {thread_id} for solution submission {sumbission_id}")
                else:
                    self.logger.info(f"Disconnected from database at {self.db_path} for thread {thread_id} (this is web server thread)")
                del self.thread_local.connection
            except sqlite3.Error as e:
                self.logger.error(f"Error while disconnecting from database at {self.db_path} for thread {thread_id} for solution submission {sumbission_id}: {e}")

    def execute_query(self, query: str, params: tuple=()) -> list[dict] | None:
        """Execute a SELECT query and return the results as a list of dictionaries."""
        connection = self.get_connection(-1)
        try:
            cursor = connection.cursor()
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
        
    def execute_write(self, query: str, params: tuple=(), commit: bool=True):
        """Execute an INSERT, UPDATE, or DELETE query."""
        connection = self.get_connection(-1)
        try:
            cursor = connection.cursor()
            cursor.execute(query, params)
            if commit:
                connection.commit()
            cursor.close()
        except sqlite3.Error as e:
            connection.rollback()
            self.logger.error(f"Error while editing data in database at {self.db_path}: {e}")
            raise sqlite3.Error(f"Error while editing data in database at {self.db_path}: {e}")
        
    def execute_transaction(self, operations: list[tuple[str, tuple]]):
        """
        Execute multiple queries as a transaction.
        Args:
            operations: List of tuples (query, params)
        """
        connection = self.get_connection(-1)
        try:
            for query, params in operations:
                cursor = connection.cursor()
                cursor.execute(query, params)
            connection.commit()
        except sqlite3.Error as e:
            connection.rollback()
            self.logger.error(f"Error while executing transaction at {self.db_path}: {e}")
            raise sqlite3.Error(f"Error while executing transaction at {self.db_path}: {e}")
