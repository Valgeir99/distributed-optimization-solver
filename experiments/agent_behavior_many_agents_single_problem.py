### Agent event loop in experiment - agent will solve a single problem instance ###

# Command line arguments:
# 1. Execution time in seconds
# 2. Problem instance name (without .mps extension)

# Agent does the following:
# 1. Downloads a single problem instance
# 2. Solves only this whole problem instance the whole time
# 3. After solving the problem instance the agent validates all available solutions from other agents
# 4. Agent will check the status of his solution submissions every 10 minutes to claim reward for a unclaimed accepted solution submission
# 5. Repeat step 2, 3 and 4 until the execution time has passed

import sys
import os
import time
import schedule

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from network.agent_node import AgentNode

# Input arguments
execution_time = int(sys.argv[1])
problem_instance_name = sys.argv[2]

# Agent
agent = AgentNode(experiment_time=execution_time)

# Agent events
def download_problem_instance_data_by_name(problem_instance_name):
    problem_instance = agent.download_problem_instance_data_by_name(problem_instance_name)
    return problem_instance
    
def solve_problem_instance(problem_instance_name):
    agent.solve_problem_instance(problem_instance_name)

def check_submit_solution_status(problem_instance):
    if agent.problem_instances.get(problem_instance) is not None:
        active_solution_submission_ids = agent.problem_instances[problem_instance]["active_solution_submission_ids"].copy()   # copy the list since we will remove elements from it
        for solution_submit_id in active_solution_submission_ids:
            agent.check_submit_solution_status(solution_submit_id)

def validate_solutions(problem_instance):
    # Validate solutions until all are validated this agent can validate at the moment
    success = True
    while success:
        success = agent.validate_solution_request(problem_instance)

def update_problem_instance_status(problem_instance):
    agent.update_problem_instance_status(problem_instance)

# Schedule agent events
schedule.every(10).minutes.do(check_submit_solution_status, problem_instance_name)   # check if solution has been validated to claim reward and free up memory
#schedule.every(5).minutes.do(update_problem_instance_status, problem_instance_name)   # not necessarry but this will clean up solver memory if problem instance is not active anymore

# Download problem instance before starting the "event loop"
problem_instance = download_problem_instance_data_by_name(problem_instance_name)

if problem_instance is not None:
    try:
        # We assume that the max_solve_time defined for the agent is shorter than the solution validation phase
        # so that agent can solve and then validate all solutions from other agents before validation phase is over
        start_time = time.time()
        elapsed_time = 0
        time_spent_solving = 0
        time_spent_validating = 0
        while elapsed_time < execution_time:
            # Solve problem instance
            start_solving_time = time.time()
            solve_problem_instance(problem_instance_name)
            time_spent_solving += time.time() - start_solving_time

            # Validate solutions
            start_validating_time = time.time()
            validate_solutions(problem_instance_name)
            time_spent_validating += time.time() - start_validating_time

            schedule.run_pending()
            elapsed_time = time.time() - start_time

    except KeyboardInterrupt:
        pass

    finally:
        time.sleep(5)   # wait a little bit since agent might still be validating a solution (to avoid unexpected errors)

        print(f"Agent {agent.id} time spent solving: {time_spent_solving}, time spent validating: {time_spent_validating} out of total time: {elapsed_time}")
        print(f"""Agent might be stuck solving in the end of the execution time so out of the planned execution time of {execution_time} seconds the agent effectively spent \
            \n{time_spent_validating} seconds validating and {execution_time-time_spent_validating} seconds solving ratio of \
            \n{time_spent_validating/execution_time} and {1-time_spent_validating/execution_time} respectively""")        

# Clean up agent
agent.clean_up()
print(f"Agent {agent.id} finished execution")