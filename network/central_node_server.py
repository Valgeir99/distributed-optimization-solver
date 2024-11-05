"""
Central node server for distributed optimization solver.
"""

# To run as module from root folder: python -m network.central_node_server

from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

from .central_node import CentralNode

# Create webserver and put it in the central node class
app = FastAPI()
central_node = CentralNode(app)


def start_server():
    """Method to start the server."""
    print("Central node server started")
    uvicorn.run(app, host=central_node.host, port=central_node.port)


## Dataclasses for the messages

class ProblemInstance(BaseModel):
    name: str
    description: str
    data: str | None = None   # optional field

## Routes for the central node server

@app.get("/problem_instances/info", response_model=list[ProblemInstance])
async def get_problem_instances_info():
    """Agent requests information about a pool of problem instances."""
    # Get 10 random problem instances from the database
    pool_size = 10   # TODO: use a constant for this (define somewhere else)
    problem_instances = central_node.query_db("SELECT * FROM problem_instances ORDER BY RANDOM() LIMIT ?", (pool_size,))

    print(problem_instances)
    
    problem_instances_info = [
        {"name": instance["name"], "description": instance["description"]}
        for instance in problem_instances
    ]
    
    return problem_instances_info

@app.get("/problem_instances/download/{problem_instance_name}", response_model=ProblemInstance)
async def get_problem_instance(problem_instance_name: str) -> ProblemInstance:
    """Agent requests a problem instance to download. He gets some basic information..."""   # TODO: should I also give out the solution or have another endpoint for that?
    # Check if problem instance exists
    problem_instance = central_node.query_db(
        "SELECT * FROM problem_instances WHERE name = ?", (problem_instance_name,)
    )[0]
    if problem_instance is None:
        return {"message": "Problem instance not found!"}
    
    # Get problem instance data from file storage
    with open(problem_instance["file_location"], "r") as file:
        data = file.read()

    return ProblemInstance(
        name=problem_instance["name"],
        description=problem_instance["description"],
        data=data
    )


# TODO: possibly have some methods for the central node to do the stuff above like 
# getting problem instance info and so on
# For example if I have some data structure that holds the problem instances and their information
# inside the central node class then I could have a method that returns the problem instances info
# Yes that is probably better since like the data and how the sqlite is configured is not 
# visbible here but only in the central node class

if __name__ == "__main__":
    start_server()