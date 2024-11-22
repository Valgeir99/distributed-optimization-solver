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

# Start the central node server in a separate thread
central_node_server_thread = start_server()

time.sleep(5)

agent1 = AgentNode("agent1")
agent1.download_problem_instance()

time.sleep(5)

# Download problem instance that does not exits
agent1.download_problem_instance_data_by_name("non_existent_problem_instance")

time.sleep(5)

agent1.print_problem_instances()

time.sleep(5)

# Solution submission
problem_instance_name = agent1.problem_instances[list(agent1.problem_instances.keys())[0]]["name"]
print(problem_instance_name)
agent1.submit_solution(problem_instance_name, "Some solution data", 89.1)


# Use database utils to get database information
from utils.database_utils import connect_to_database, query_db
connection = connect_to_database(DB_PATH)
problem_instances = query_db(connection, "SELECT * FROM problem_instances")
print(problem_instances)
all_solutions = query_db(connection, "SELECT * FROM all_solutions")
print(all_solutions)

time.sleep(5)

# Create agents to validate the solution
agent2 = AgentNode("agent2")
agent2.download_problem_instance_data_by_name(problem_instance_name)
agent2.print_problem_instances()
agent3 = AgentNode("agent3")
agent3.download_problem_instance_data_by_name(problem_instance_name)

time.sleep(5)

# Validate the solution - do simultaneously for both agents
t1 = threading.Thread(target=agent2.validate_solution_request, args=(problem_instance_name,))
t2 = threading.Thread(target=agent3.validate_solution_request, args=(problem_instance_name,))
t1.start()
t2.start()
t1.join()
t2.join()
#agent2.validate_solution_request(problem_instance_name)
time.sleep(5)

solution_submission_id = list(agent1.problem_instances[problem_instance_name]["active_solution_submission_ids"])[0]   # only have one solution submission so this is fine
agent1.check_submit_solution_status(solution_submission_id)

# Submit another soltuion that no one will validate - nothing should happen in the end of the validation phase
agent2.submit_solution(problem_instance_name, "Some solution data vol 2", 82.0)

# TODO: let submitting agent validate is own solution (should not be allowed) and let agents validate same solution mulitple times (should not be allowed)

# Sleep until solution validation done
time.sleep(SOLUTION_VALIDATION_DURATION)

# Check twice after the solution validation is done - the second time should not make any changes (print statement)
agent1.check_submit_solution_status(solution_submission_id)
agent1.check_submit_solution_status(solution_submission_id)
time.sleep(5)

# Print problem instances for agent1 to see reward (for solving the problem instance)
agent1.print_problem_instances()
time.sleep(5)

# Print problem instances for agent2 and agent3 to see reward (for validating the solution submission by agent1)
agent2.print_problem_instances()
agent3.print_problem_instances()
time.sleep(5)

# Database
problem_instances = query_db(connection, "SELECT * FROM problem_instances")
print(problem_instances)
all_solutions = query_db(connection, "SELECT * FROM all_solutions")
print(all_solutions)
best_solutions = query_db(connection, "SELECT * FROM best_solutions")
print(best_solutions)
time.sleep(5)

# Download problem instance that agent1 just got accepted - now best soolution should also be given with the problem instance
agent2.download_problem_instance_data_by_name(problem_instance_name)
agent2.print_problem_instances()
time.sleep(5)

# Validate solution after solution validation phase is done
agent2.validate_solution_request(problem_instance_name)

# Close the database connection
connection.close()

# Clean up agent - check if the problem instance and best solution is saved to file
time.sleep(30)
agent1.clean_up()

# Stop the central node server
stop_server()
central_node_server_thread.join()