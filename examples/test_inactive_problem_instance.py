import time
import sys
import os
import threading
from dotenv import load_dotenv

# Change the working directory to the root of the project
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)  # This changes the CWD to the root of the project
# Add the project root to sys.path to ensure Python can find the 'network' package
sys.path.append(project_root)

from network.agent_node import AgentNode
from network.central_node_server import start_server, stop_server

from config import DB_PATH

load_dotenv()
SOLUTION_VALIDATION_DURATION = int(os.getenv("SOLUTION_VALIDATION_DURATION"))

try:
    # NOTE: In order to use this script as expected we should initilize the database with small reward for the problem instance p0201

    # Start the central node server in a separate thread
    central_node_server_thread = start_server()

    time.sleep(5)

    agent1 = AgentNode()
    agent1.download_problem_instance_data_by_name("p0201")

    time.sleep(5)

    # Start solving the problem instance in a separate thread
    problem_instance_name = agent1.problem_instances[list(agent1.problem_instances.keys())[0]]["name"]
    print(problem_instance_name)
    solver_thread = threading.Thread(target=agent1.solve_problem_instance, args=(problem_instance_name,))
    solver_thread.start()

    # More agents to download the problem instance
    agent2 = AgentNode()
    agent2.download_problem_instance_data_by_name(problem_instance_name)
    agent3 = AgentNode()
    agent3.download_problem_instance_data_by_name(problem_instance_name)

    # Let agent1 try to start solving problem while it is already solving - should return without solving and print some warning message
    solver_thread2 = threading.Thread(target=agent1.solve_problem_instance, args=(problem_instance_name,))
    solver_thread2.start()
    solver_thread2.join()

    # Wait for the solver to finish - NOTE that it needs to finish before validation phase ends otherwise code below is not guaranteed to work
    solver_thread.join()

    time.sleep(5)

    # Let agents validate the after agent1 has solved it and submitted the solution
    agent2.validate_solution_request(problem_instance_name)
    agent3.validate_solution_request(problem_instance_name)

    # Wait for validation to finish
    time.sleep(SOLUTION_VALIDATION_DURATION)

    # NOTE: Now the reward for problem instance should be depleted and it should be inactive - let's check the database to see if this is the case

    # Database stuff
    from utils.database_utils import connect_to_database, query_db
    connection = connect_to_database(DB_PATH)
    problem_instances = query_db(connection, "SELECT * FROM problem_instances")
    print(problem_instances)
    all_solutions = query_db(connection, "SELECT * FROM all_solutions")
    print(all_solutions)
    best_solutions = query_db(connection, "SELECT * FROM best_solutions")
    print(best_solutions)

    # Download problem instance for agent2 - should not be possible since the problem instance is inactive
    agent2.download_problem_instance_data_by_name(problem_instance_name)
    agent2.download_best_solution(problem_instance_name)

    # Make problem instance inactive for agents
    agent1.update_problem_instance_status(problem_instance_name)
    agent2.update_problem_instance_status(problem_instance_name)
    agent3.update_problem_instance_status(problem_instance_name)

    # Check problem instance in memory
    agent1.print_problem_instances()
    agent2.print_problem_instances()
    agent3.print_problem_instances()

    # Do stuff for problem instance that is inactive
    agent1.solve_problem_instance(problem_instance_name)
    agent2.validate_solution_request(problem_instance_name)
    agent3.download_best_solution(problem_instance_name)

except KeyboardInterrupt:
    # Terminate the program
    print("Keyboard interrupt detected. Exiting program.")

finally:
    # Clean up agents
    agent1.clean_up()
    agent2.clean_up()
    agent3.clean_up()

    # Stop the central node server
    stop_server()
    central_node_server_thread.join()