import sqlite3
import threading
from fastapi import FastAPI
import uvicorn
from dotenv import load_dotenv
import os
import time
from datetime import datetime, timedelta
from typing import TypedDict, Dict
import uuid

from utils.database_utils import create_database, teardown_database
from config import DB_PATH, BEST_SOLUTIONS_DIR

load_dotenv()
CENTRAL_NODE_HOST = os.getenv("CENTRAL_NODE_HOST")
CENTRAL_NODE_PORT = int(os.getenv("CENTRAL_NODE_PORT"))
SOLUTION_VALIDATION_DURATION = int(os.getenv("SOLUTION_VALIDATION_DURATION"))  # seconds
SUCCESSFUL_SOLUTION_SUBMISSION_REWARD = int(os.getenv("SUCCECCFUL_SOLUTION_SUBMISSION_REWARD"))  # reward for successful solution submission



# TODO: question if we need this one here? It is very good to have to store the solution_data string and validations list since it 
# would not make sense to store at least the solution_data string in the database (but maybe we could store it in a different way?)
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


# NOTE: in current implementation the reward mechanism uses constant reward for successful solution submission and other constant 
# reward for solution validation (now those rewards are "given" in server code - should maybe change that TODO).
# The problem instance can go over budget in this implementation since we only mark problem instance to be inactive when the reward
# is finished but we still will finish all active solution submissions for that problem instance.


class CentralNode:
    """A central node that has a web server to comminicate with agent nodes and stores data in a local database."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        """Singleton pattern to ensure only one instance of the central node is created."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        else:
            raise Exception("CentralNode instance already exists!")
        return cls._instance
        

    # TODO: I just put the web_server as an argument to the constructor because I thought it would be better
    # so that people realize that the central node needs a web server to work...
    def __init__(self, web_server: FastAPI):
        """Initialize the central node with a web server and connect to the database."""

        print("Central node started")

        self.host = CENTRAL_NODE_HOST
        self.port = CENTRAL_NODE_PORT

        # Database
        self.db_path = DB_PATH
        create_database(self.db_path)   # TODO: we should not create the database here, we should create it and populate it somewhere else
        self.db_connection = self.__connect_to_database()
        #self.edit_data_in_db("INSERT INTO central_nodes (id, host, port) VALUES (?, ?, ?)", (self.id, self.host, self.port))

        # Web server
        self.web_server = web_server
        
        # Lock for multithreading
        self.lock = threading.Lock()

        # NOTE: To generalize architecture for multiple central nodes then we will not store data like solution validation phase data 
        # in memory but in the database. Of course same for the problem instances and so on...
        # -> But it is a little pain to have to query the database all the time so maybe we use in memory storage for some things?
        # -> So maybe we will just put stuff in the database that needs to be permanent (so we can e.g. make some statistics after 
        # the experiments) and then we will use in memory storage for the rest?

        # Solution submissions that are currently being validated
        self.active_solution_submissions: Dict[str, SolutionSubmissionInfo] = dict()   # key is solutions submission id and value is a dictionary with solution submission information
             
        # Best solutions folder path
        self.best_solutions_folder = BEST_SOLUTIONS_DIR
        if not os.path.exists(self.best_solutions_folder):
            os.makedirs(self.best_solutions_folder)


    def __connect_to_database(self):
        """Create a connection to the database."""
        try:
            connection = sqlite3.connect(self.db_path, check_same_thread=False)   # check_same_thread=False is needed for multithreading
            print(f"Connected to database at {self.db_path}")
            return connection
        except sqlite3.Error as e:
            # Raise exception to stop the program (we can't continue without the database)
            raise sqlite3.Error(f"Error while connecting to database at {self.db_path}: {e}")


    def __disconnect_from_database(self):
        """Close the connection to the database."""
        try:
            self.db_connection.close()
            print(f"Disconnected from database at {self.db_path}")
        except sqlite3.Error as e:
            print(f"Error while disconnecting from database at {self.db_path}: {e}")


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
            print(f"Error while querying database at {self.db_path}: {e}")
            return None
        # TODO: remember we need to check if the result is None when we call this function!!



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
            raise sqlite3.Error(f"Error while editing data in database at {self.db_path}: {e}")
            
    def generate_id(self):
        """Generate a unique id for solution submissions."""
        return str(uuid.uuid4())


    def start_solution_validation_phase(self, problem_instance_name: str, solution_submission_id: str, solution_data: str, objective_value: float):
        """Start the solution validation phase with a time limit for a solution submission."""
        # Should we check if the solution file is on correct format or? Or just let agents reject it if it is not? TODO: but yes 
        # to keep minimal role of central node we should not do that here and let agents do that

        submission_time = datetime.now()
        validation_end_time = submission_time + timedelta(seconds=SOLUTION_VALIDATION_DURATION)

        # Create a database entry for the solution submission
        self.edit_data_in_db(
            "INSERT INTO all_solutions (id, problem_instance_name, submission_time, validation_end_time) VALUES (?, ?, ?, ?)",
            (solution_submission_id, problem_instance_name, submission_time, validation_end_time)
        )
        
        # Start a background thread for this solution submission validation
        validation_thread = threading.Thread(target=self._manage_validation_phase, args=(solution_submission_id, validation_end_time))
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

    def _manage_validation_phase(self, solution_submission_id: str, validation_end_time: datetime):
        """Manage the ongoing validation phase and end it after the time limit."""
        while datetime.now() < validation_end_time:
            # The thread waits until the validation period expires
            time.sleep(1)

            # TODO: what if the reward is finished before the time limit? Should we stop the validation phase then? - only pain is that we always need to insert 
            # the reward to the problem instance database table when agents send validation results and also in this loop here we would also need to query the database
            # to check for that reward...
            # Other option would be to allow to go over budget but could cost a lot of money for the client if e.g. 10 solution submissions are active at the same time 
            # and then the reward is finished but the client has to give out reward for all of them in the end.
            # If we stop the solution validation can we then really accept the solution as the best solution and give the reward to the agent 
            # that submitted it? Since I mean the reward is finished so I guess we should automatically stop and not accept it.

        # Process final validation after the time limit (use lock since we are accessing shared data (could also be accessed in central_node_server.py))
        # TODO: maybe we don't need to lock the whole function but only the part where we access the shared data? Look at validation endpoint in central_node_server.py
        # to see if necessary to lock the whole function or not... https://chatgpt.com/c/6735af4f-8fc0-8003-95ab-d5c0a8cef192
        # We might be in the middle of finalizing validation while an agent is sending validation results so we need to be careful
        with self.lock:
            self._finalize_validation(solution_submission_id)

    def _finalize_validation(self, solution_submission_id: str):
        """Finalize validation based on the collected results."""
       
        # Retrieve collected validation results
        solution_submission = self.active_solution_submissions.get(solution_submission_id)
        if solution_submission is None:
            print("Solution submission info not found.")
            return
        
        problem_instance_name = solution_submission["problem_instance_name"]

        objective_value = None
        validations = solution_submission["validations"]
        accepted = False
        if validations:
            # TODO: we need to have some lower bound for the number of validations needed to make a decision 
            # Calculate final status based on validations, e.g., majority vote
            acceptance_count = sum(validations)
            rejection_count = len(validations) - acceptance_count
            accepted = True if acceptance_count > rejection_count else False

            # We need the objective value also so maybe we should ask agents to also send that and then we take the 
            # most common objective value of responses that said the solution was valid? TODO: use this one or the one from the agent who submitted the solution?
            objective_values = solution_submission["objective_values"]
            if objective_values:
                # Calculate the most common objective value for accepted solutions
                accepted_objective_values = [objective_values[i] for i in range(len(validations)) if validations[i]]
                if accepted_objective_values:
                    objective_value = max(set(accepted_objective_values), key=accepted_objective_values.count)
                
        # Here we use the objective value from the agent who submitted the solution
        #objective_value = solution_submission["objective_value"]

        # If the solution is valid then it should be the best solution so far (but it is not guaranteed that it is the best solution 
        # but there is nothing that the central node should do about that since it is the agents decision!)
        if accepted:
            print("Solution submission accepted")
            # Save solution data to file storage with best solutions
            solution_file_location = f"{self.best_solutions_folder}/{problem_instance_name}.sol"
            with open(solution_file_location, "w") as f:
                f.write(solution_submission["solution_data"])

            print("Solution file saved to:", solution_file_location)

            # "Give" reward to the agent who submitted the solution
            solution_submission["reward_accumulated"] += SUCCESSFUL_SOLUTION_SUBMISSION_REWARD   # we don't implement proper reward mechanism just emulating it by adding to the reward given for this solution submission

            # Update the best solution in the database (or insert if it does not exist)
            self.edit_data_in_db("INSERT OR REPLACE INTO best_solutions (problem_instance_name, solution_id, file_location) VALUES (?, ?, ?)", (problem_instance_name, solution_submission_id, solution_file_location))

        #print("solution_submission in finalize after validation", solution_submission)

        # Insert to db accumulated reward given for this solution submission, objective value and if it was accepted or not
        self.edit_data_in_db("UPDATE all_solutions SET reward_accumulated = ?, objective_value = ?, accepted = ? WHERE id = ?", (solution_submission["reward_accumulated"], objective_value, accepted, solution_submission_id))

        # Update the problem instance database table with the reward given for this solution submission
        self.edit_data_in_db("UPDATE problem_instances SET reward_accumulated = reward_accumulated + ? WHERE name = ?", (solution_submission["reward_accumulated"], problem_instance_name))

        # If the reward is finished then we should make this problem instance inactive - we don't make solution submission inactive since 
        # we want to finish all active solution submissions for that problem instance (reward will go over budget in this implementation)
        results = self.query_db("SELECT reward_accumulated, reward_budget FROM problem_instances WHERE name = ?", (problem_instance_name,))
        reward_accumulated = results[0]["reward_accumulated"]
        reward_budget = results[0]["reward_budget"]
        if reward_accumulated >= reward_budget:
            self.edit_data_in_db("UPDATE problem_instances SET active = False WHERE name = ?", (problem_instance_name,))
            
        # Delete solution file from temporary file storage (NOTE: not doing that since we are storing the solution data in memory)

        # Clean up in-memory tracking for this submission
        del self.active_solution_submissions[solution_submission_id]

        # Stop the thread? TODO

     

    def stop(self):
        """Stop the central node."""
        self.__disconnect_from_database()
        # TODO: possibly delete some folders
        print("Central node stopped")