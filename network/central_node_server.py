"""
Central node server for distributed optimization solver. Starts a FastAPI server which is the web server for the central node.
"""

# To run as module from root folder: python -m network.central_node_server

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import threading
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

from .central_node import CentralNode

# Load environment variables from .env file
load_dotenv()
SUCCESSFUL_SOLUTION_SUBMISSION_REWARD = int(os.getenv("SUCCESSFUL_SOLUTION_SUBMISSION_REWARD"))  # reward for successful solution submission
SOLUTION_VALIDATION_REWARD = int(os.getenv("SOLUTION_VALIDATION_REWARD"))  # reward for validating a solution

# Create FastAPI application and put it in the central node class
app = FastAPI()
central_node = CentralNode(app)
server = None

def start_server():
    """Start the server using uvicorn's Server class."""
    global server
    print("Central node server started")
    config = uvicorn.Config(app, host="0.0.0.0", port=central_node.port, log_level="info")
    server = uvicorn.Server(config)
    
    # Run the server in a separate thread
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()
    return server_thread

def stop_server():
    """Stop the server gracefully."""
    # Stop the central node
    central_node.stop()
    if server and server.should_exit is False:
        server.should_exit = True
    print("Central node server stopped")


##--- Dataclasses for the messages - agents need to follow these schemas when sending requests / receiving responses   ---##

class ProblemInstanceResponse(BaseModel):
    name: str
    description: str
    problem_data: str | None = None   # optional field
    solution_data: str | None = None

class ProblemInstanceStatusResponse(BaseModel):
    active: bool

class SolutionSubmissionRequest(BaseModel):
    solution_data: str
    objective_value: float

class SolutionSubmissionResponse(BaseModel):
    solution_submission_id: str
    problem_instance_name: str
    submission_time: str
    validation_end_time: str
    accepted: bool | None = None   # optional field
    reward: int | None = None   # optional field - reward for the agent who submitted the solution

class SolutionDataResponse(BaseModel):
    solution_submission_id: str | None = None   # optional field - only used when downloading a solution to validate
    problem_instance_name: str
    solution_data: str

class SolutionValidationResponse(BaseModel):
    reward: int   # reward for the agent who validated the solution

class SolutionValidationRequest(BaseModel):
    response: bool   # True if solution is accepted, False otherwise
    objective_value: float   # objective value of the solution


##---- Routes for the central node server ---##
# TODO: possibly rename enpoint urls to be more descriptive: https://chatgpt.com/c/67335c94-2fd0-8003-8cb5-77a97f76137c

@app.get("/problem_instances/info", response_model=list[ProblemInstanceResponse])
async def get_problem_instances_info() -> list[ProblemInstanceResponse]:
    """Agent requests information about a pool of problem instances so he can download one (or more) 
    of them later. Returns a list of problem instances with their names and descriptions."""
    # Get a pool of random problem instances from the central node database
    problem_instances = central_node.get_pool_of_problem_instances()
    if problem_instances is None:
        # Database error
        raise HTTPException(status_code=500, detail="Database error")
    if not problem_instances:
        # No problem instances in the database
        raise HTTPException(status_code=404, detail="No problem instances available on the central node!")
    
    return [ProblemInstanceResponse(
        name=instance["name"],
        description=instance["description"]

    ) for instance in problem_instances]

@app.get("/problem_instances/download/{problem_instance_name}", response_model=ProblemInstanceResponse)
async def get_problem_instance_data_by_id(problem_instance_name: str) -> ProblemInstanceResponse:
    """Agent requests a problem instance to download. Returns the problem instance data and best 
    solution on the platform if available."""
    # Check if problem instance exists
    result = central_node.query_db(
        "SELECT * FROM problem_instances WHERE name = ?", (problem_instance_name,)
    )
    if result is None:
        # Database error
        raise HTTPException(status_code=500, detail="Database error")
    if not result:
        # No problem instance found
        raise HTTPException(status_code=404, detail="Problem instance not found!")
    if result[0]["active"] == False:
        # Problem instance is not active
        raise HTTPException(status_code=404, detail="Problem instance is not active!")
    problem_instance = result[0]

    # Get problem instance data from file storage
    problem_data = None
    if os.path.exists(problem_instance["file_location"]):
        try:
            with open(problem_instance["file_location"], "r") as file:
                problem_data = file.read()
        except Exception as e:
            raise HTTPException(status_code=500, detail="File read error")
    if problem_data is None:
        # File not found
        raise HTTPException(status_code=500, detail="File not found error")

    # Check where the solution is stored
    result = central_node.query_db(
        "SELECT file_location FROM best_solutions WHERE problem_instance_name = ?", (problem_instance["name"],)
    )
    if result is None:
        # Database error
        raise HTTPException(status_code=500, detail="Database error")
    
    # Get the solution data if it exists
    solution_data = None
    if result:
        solution_location = result[0]["file_location"]
        # Get problem instance solution from file storage
        if os.path.exists(solution_location):
            try:
                with open(solution_location, "r") as file:
                    solution_data = file.read()
            except Exception as e:
                raise HTTPException(status_code=500, detail="File read error")

    return ProblemInstanceResponse(
        name=problem_instance["name"],
        description=problem_instance["description"],
        problem_data=problem_data,
        solution_data=solution_data
    )


@app.get("/problem_instances/status/{problem_instance_name}", response_model=ProblemInstanceStatusResponse)
def check_problem_instance_status(problem_instance_name: str) -> bool:
    """Agent checks if the problem instance is active. Returns True if the problem instance is active,
    False otherwise."""
    result = central_node.query_db(
        "SELECT active FROM problem_instances WHERE name = ?", (problem_instance_name,)
    )
    if result is None:
        # Database error
        raise HTTPException(status_code=500, detail="Database error")
    if not result:
        # No problem instance found
        raise HTTPException(status_code=404, detail="Problem instance not found!")
    
    return ProblemInstanceStatusResponse(active=result[0]["active"])


@app.post("/solutions/upload/{problem_instance_name}", response_model=SolutionSubmissionResponse)
async def upload_solution(problem_instance_name: str, solution: SolutionSubmissionRequest) -> SolutionSubmissionResponse:
    """Agent uploads a solution to a problem instance to the platform - the solution will be available for validation 
    by other agents for limited time to determine if the solution is best one on platform or not (agents need to reach 
    consensus). Returns some metadata about the solution submission."""

    # Check if problem instance exists and is active
    result = central_node.query_db(
        "SELECT * FROM problem_instances WHERE name = ?", (problem_instance_name,)
    )
    if result is None:
        # Database error
        raise HTTPException(status_code=500, detail="Database error")
    if not result:
        # No problem instance found
        raise HTTPException(status_code=404, detail="Problem instance not found!")
    problem_instance = result[0]
    if problem_instance["active"] == False:
        # Problem instance is not active
        raise HTTPException(status_code=404, detail="Problem instance is not active!")
    
    # Start the solution validation phase (on different thread) for this solution submission
    solution_submission_id = central_node.generate_id()
    central_node.start_solution_validation_phase(problem_instance_name, solution_submission_id, solution.solution_data, solution.objective_value)

    # Get solution submission data from the database
    result = central_node.query_db(
        "SELECT * FROM all_solutions WHERE id = ?", (solution_submission_id,)
    )
    if result is None:
        # Database error
        raise HTTPException(status_code=500, detail="Database error")
    if not result:
        # Solution submission not found
        raise HTTPException(status_code=404, detail="Solution submission id not found!")
    solution_submission = result[0]
   
    return SolutionSubmissionResponse(
        solution_submission_id=solution_submission_id, 
        problem_instance_name=problem_instance_name,
        submission_time=solution_submission["submission_time"],
        validation_end_time=solution_submission["validation_end_time"]
    )


# NOTE: agents could actually check solution submissions of other agents (and "claim" the reward even though they don't get any reward it is just for bookkeeping 
# in this proof of concept so it does not matter)
@app.get("/solutions/status/{solution_submission_id}", response_model=SolutionSubmissionResponse)
async def get_solution_submission_status(solution_submission_id: str) -> SolutionSubmissionResponse:
    """Agent requests the status of a solution submission. Returns the status of the solution submission and
    the reward value (if the solution has been validated)."""    
    # Check if solution submission exists
    result = central_node.query_db(
        "SELECT * FROM all_solutions WHERE id = ?", (solution_submission_id,)
    )
    if result is None:
        # Database error
        raise HTTPException(status_code=500, detail="Database error")
    if not result:
        # Solution submission not found
        raise HTTPException(status_code=404, detail="Solution submission id not found!")
    solution_submission = result[0]

    # Check if solution submission is active
    if solution_submission["accepted"] is None:
        # Solution submission is still being validated
        return SolutionSubmissionResponse(
            solution_submission_id=solution_submission_id, 
            problem_instance_name=solution_submission["problem_instance_name"],
            submission_time=solution_submission["submission_time"],
            validation_end_time=solution_submission["validation_end_time"]
        )
    else:
        # Solution submission has been validated
        if solution_submission["accepted"]:
            reward = SUCCESSFUL_SOLUTION_SUBMISSION_REWARD
        else:
            reward = 0
        return SolutionSubmissionResponse(
            solution_submission_id=solution_submission_id, 
            problem_instance_name=solution_submission["problem_instance_name"],
            submission_time=solution_submission["submission_time"],
            validation_end_time=solution_submission["validation_end_time"],
            accepted=solution_submission["accepted"],
            reward=reward
        )
    

@app.get("/solutions/best/download/{problem_instance_name}", response_model=SolutionDataResponse)
async def download_best_solution(problem_instance_name: str):
    """Agent requests to download the best solution for a specific problem instance. 
    Returns the best solution data if available."""

    # Check if problem instance exists
    result = central_node.query_db(
        "SELECT * FROM problem_instances WHERE name = ?", (problem_instance_name,)
    )
    if result is None:
        # Database error
        raise HTTPException(status_code=500, detail="Database error")
    if not result:
        # No problem instance found
        raise HTTPException(status_code=404, detail="Problem instance not found!")
    if result[0]["active"] == False:
        # Problem instance is not active
        raise HTTPException(status_code=404, detail="Problem instance is not active!")
    
    # Get the best solution for the problem instance
    result = central_node.query_db(
        "SELECT file_location FROM best_solutions WHERE problem_instance_name = ?", (problem_instance_name,)
    )
    if result is None:
        # Database error
        raise HTTPException(status_code=500, detail="Database error")
    if not result:
        # No best solution found
        raise HTTPException(status_code=404, detail="No best solution found for the problem instance!")
    best_solution_location = result[0]["file_location"]

    # Get best solution data from file storage
    if os.path.exists(best_solution_location):
        try:
            with open(best_solution_location, "r") as file:
                best_solution_data = file.read()
        except Exception as e:
            raise HTTPException(status_code=500, detail="File read error")
    else:
        # File not found
        raise HTTPException(status_code=404, detail="File containing best solution not found!")
    
    return SolutionDataResponse(
        problem_instance_name=problem_instance_name,
        solution_data=best_solution_data
    )


@app.get("/solutions/validate/download/{problem_instance_name}", response_model=SolutionDataResponse)
async def download_solution_by_problem_instance_id(problem_instance_name: str):
    """Agent requests to download a solution to a specific problem instance (to validate it).
    Returns the oldest active solution submission that has more than 30 seconds left for validation."""

    # Check if problem instance exists
    result = central_node.query_db(
        "SELECT * FROM problem_instances WHERE name = ?", (problem_instance_name,)
    )
    if result is None:
        # Database error
        raise HTTPException(status_code=500, detail="Database error")
    if not result:
        # No problem instance found
        raise HTTPException(status_code=404, detail="Problem instance not found!")
    if result[0]["active"] == False:
        # Problem instance is not active
        raise HTTPException(status_code=404, detail="Problem instance is not active!")

    # Get a solution submission id
    result = central_node.get_solution_submission_id(problem_instance_name)
    if result is None:
        # Database error
        raise HTTPException(status_code=500, detail="Database error")
    if not result:
        # No active solution submission found
        raise HTTPException(status_code=404, detail="No active solution submission found for the problem instance!")
    solution_submission_id = result[0]["id"]

    # Get solution data from in memory data structure
    solution_submission = central_node.active_solution_submissions.get(solution_submission_id)
    if solution_submission is None:
        # No solution submission in memory for this solution submission id
        raise HTTPException(status_code=404, detail="No active solution submission found for the problem instance!")
    solution_data = solution_submission["solution_data"]
    if solution_data is None:
        # Solution data not found
        raise HTTPException(status_code=500, detail="Solution data not found in memory for solution submission!")

    return SolutionDataResponse(
        problem_instance_name=problem_instance_name,
        solution_submission_id=solution_submission_id,
        solution_data=solution_data
    )


# NOTE: there is nothing preventing agents to validate the same solution multiple times... (but I guess we don't 
# care about that in proof of concept TODO yes I think we should try to fix and also prevent agent who submitted the solution to validate it)
@app.post("/solutions/validate/{solution_submission_id}", response_model=SolutionValidationResponse)
async def validate_solution(solution_submission_id: str, solution_validation_result: SolutionValidationRequest) -> SolutionValidationResponse:
    """Agent sends solution validation result to central node for a specific solution submission. 
    Returns the reward for the agent who validated the solution."""
    # Check if the solution submission exists
    result = central_node.query_db(
        "SELECT * FROM all_solutions WHERE id = ?", (solution_submission_id,)
    )
    if result is None:
        # Database error
        raise HTTPException(status_code=500, detail="Database error")
    if not result:
        # Solution submission not found
        raise HTTPException(status_code=404, detail="Solution submission id not found!")
    solution_submission = result[0]

    # Check if solution submission has already been validated
    if solution_submission["accepted"] is not None:
        # Solution submission is already validated
        raise HTTPException(status_code=400, detail="Solution submission has already been validated by the platform!")
    # NOTE: Double check if the solution submission is still active (using in memory data structure) - we are using locking 
    # when finalizing the solution validation phase so there the database and in memory data structure are updated atomically
    # However! there might be a small chance that database says inactive but it still exists in memory when we update 
    # the database in the loop of the solution validation phase
    solution_submission = central_node.active_solution_submissions.get(solution_submission_id)   # TODO: or what?????????? We are inserting in database in manage and not in memory...
    if solution_submission is None:
        # Solution submission not found (so it has already been validated)
        raise HTTPException(status_code=400, detail="Solution submission has already been validated by the platform!")

    # Check if the problem instance is active
    problem_instance_name = solution_submission["problem_instance_name"]
    result = central_node.query_db(
        "SELECT active FROM problem_instances WHERE name = ?", (problem_instance_name,)
    )
    if result is None:
        # Database error
        raise HTTPException(status_code=500, detail="Database error")
    if not result:
        # No problem instance found
        raise HTTPException(status_code=404, detail="Problem instance not found!")
    if result[0]["active"] == False:
        # Problem instance is not active
        raise HTTPException(status_code=404, detail="Problem instance is not active!")

    # Update the solution submission
    with central_node.lock:
        solution_submission["validations"].append(solution_validation_result.response)
        solution_submission["objective_values"].append(solution_validation_result.objective_value)
        solution_submission["reward_accumulated"] += SOLUTION_VALIDATION_REWARD

    return SolutionValidationResponse(reward=SOLUTION_VALIDATION_REWARD)
    
    
@app.get("/solutions/validate")
async def validate_any_solution():
    """Agent requests to validate any solution available on the platform."""
    pass
    

if __name__ == "__main__":
    try:
        uvicorn.run(app, host="0.0.0.0", port=central_node.port)
    except KeyboardInterrupt:
        pass
    finally:
        stop_server()
