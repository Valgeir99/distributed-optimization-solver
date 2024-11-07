"""
Central node server for distributed optimization solver.
"""

# To run as module from root folder: python -m network.central_node_server

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import threading
import os

from .central_node import CentralNode

# Create FastAPI application and put it in the central node class
app = FastAPI()
central_node = CentralNode(app)
server = None


def start_server():
    """Start the server using uvicorn's Server class."""
    global server
    print("Central node server started")
    config = uvicorn.Config(app, host=central_node.host, port=central_node.port, log_level="info")
    server = uvicorn.Server(config)
    
    # Run the server in a separate thread
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()
    return server_thread

def stop_server():
    """Stop the server gracefully."""
    central_node.stop()
    if server and server.should_exit is False:
        server.should_exit = True
        print("Central node server stopped")


## Dataclasses for the messages

class ProblemInstance(BaseModel):
    name: str
    description: str
    problem_data: str | None = None   # optional field
    solution_data: str | None = None

## Routes for the central node server

@app.get("/problem_instances/info", response_model=list[ProblemInstance])
async def get_problem_instances_info():
    """Agent requests information about a pool of problem instances."""
    # Get 10 random problem instances from the database
    pool_size = 10   # TODO: use a constant for this (define somewhere else)
    problem_instances = central_node.query_db("SELECT * FROM problem_instances ORDER BY RANDOM() LIMIT ?", (pool_size,))
    
    if problem_instances is None:
        # Database error
        raise HTTPException(status_code=500, detail="Internal server error")
    if not problem_instances:
        # No problem instances in the database
        raise HTTPException(status_code=404, detail="No problem instances available on the central node!")

    problem_instances_info = [
        {"name": instance["name"], "description": instance["description"]}
        for instance in problem_instances
    ]
    
    return problem_instances_info

@app.get("/problem_instances/download/{problem_instance_name}", response_model=ProblemInstance)
async def get_problem_instance_data_by_id(problem_instance_name: str) -> ProblemInstance:
    """Agent requests a problem instance to download. He gets some basic information..."""   # TODO: should I also give out the solution or have another endpoint for that?
    # Check if problem instance exists
    result = central_node.query_db(
        "SELECT * FROM problem_instances WHERE name = ?", (problem_instance_name,)
    )
    if result is None:
        # Database error
        raise HTTPException(status_code=500, detail="Internal server error")
    if not result:
        # No problem instance found
        raise HTTPException(status_code=404, detail="Problem instance not found!")
    
    problem_instance = result[0]

    # Get problem instance data from file storage
    problem_data = None
    if os.path.exists(problem_instance["file_location"]):
        with open(problem_instance["file_location"], "r") as file:
            problem_data = file.read()

    # Check where the solution is stored
    result = central_node.query_db(
        "SELECT solution_file_location FROM best_solutions WHERE problem_instance_name = ?", (problem_instance["name"],)
    )
    if result is None:
        # Database error
        raise HTTPException(status_code=500, detail="Internal server error")
    
    # Get the solution data if it exists
    solution_data = None
    if result:
        solution_location = result[0]["solution_file_location"]
        # Get problem instance solution from file storage
        if os.path.exists(solution_location):
            with open(solution_location, "r") as file:
                solution_data = file.read()

    return ProblemInstance(
        name=problem_instance["name"],
        description=problem_instance["description"],
        problem_data=problem_data,
        solution_data=solution_data
    )


# TODO: possibly have some methods for the central node to do the stuff above like 
# getting problem instance info and so on
# For example if I have some data structure that holds the problem instances and their information
# inside the central node class then I could have a method that returns the problem instances info
# Yes that is probably better since like the data and how the sqlite is configured is not 
# visbible here but only in the central node class

if __name__ == "__main__":
    try:
        uvicorn.run(app, host=central_node.host, port=central_node.port)
    except KeyboardInterrupt:
        pass
    finally:
        stop_server()
