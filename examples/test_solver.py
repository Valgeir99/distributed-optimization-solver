import time
import sys
import os
import threading
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from network.agent_node import AgentNode
from network.central_node_server import start_server, stop_server

from config import DB_PATH

load_dotenv()
SOLUTION_VALIDATION_DURATION = int(os.getenv("SOLUTION_VALIDATION_DURATION"))

try:
    # Start the central node server in a separate thread
    central_node_server_thread = start_server()

    time.sleep(5)

    agent1 = AgentNode("agent1")
    agent1.download_problem_instance_data_by_name("p0201")
    #agent1.download_problem_instance()

    time.sleep(5)

    # Start solving the problem instance in a separate thread
    problem_instance_name = agent1.problem_instances[list(agent1.problem_instances.keys())[0]]["name"]
    print(problem_instance_name)
    solver_thread = threading.Thread(target=agent1.solve_problem_instance, args=(problem_instance_name,))
    solver_thread.start()
    #agent1.solve_problem_instance(problem_instance_name)

    # More agents to download the problem instance
    agent2 = AgentNode("agent2")
    agent2.download_problem_instance_data_by_name(problem_instance_name)
    agent3 = AgentNode("agent3")
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

    # Print some stuff for the agents - at this point agent1 should have best self solution tracked and saved in a file in "best_self_solutions" folder
    agent1.print_problem_instances()
    agent2.print_problem_instances()
    agent3.print_problem_instances()

    # Wait for validation to finish
    time.sleep(SOLUTION_VALIDATION_DURATION)

    # Database stuff
    from utils.database_utils import connect_to_database, query_db
    connection = connect_to_database(DB_PATH)
    problem_instances = query_db(connection, "SELECT * FROM problem_instances")
    print(problem_instances)
    all_solutions = query_db(connection, "SELECT * FROM all_solutions")
    print(all_solutions)
    best_solutions = query_db(connection, "SELECT * FROM best_solutions")
    print(best_solutions)

    # Download problem instance for agent2 - now the best solution should be the one agent1 submitted
    agent2.download_problem_instance_data_by_name(problem_instance_name)
    agent2.download_best_solution(problem_instance_name)

    # Manually look at agent data to see what file he has before cleaning up
    time.sleep(60)

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