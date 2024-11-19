### Agent loop in experiment 1 - agent will solve problem as a main function here ###

# Command line arguments:
# 1. Agent name
# 2. Execution time in seconds


# Agent does the following:
# 1. If not solving a problem he downloads a problem instance
# 2. Solves problem until some stopping criterion is met (TODO should the stopping criteria be defined here or on the agent class?? 
#    It is a little bit tricky since the we might want to have different stopping criteria but still we would maybe not want to code that here either...)
# -> Or maybe we should just define all agents to be in such a way so that they only call the solver once and then when the solver finishes we will say that 
# we are not solving any problem instance and then we should periodcally check maybe each minute if we are solving any problem instance or not
# 3. After submitting a solution then the agent should check the status every x minutes until the problem is validated
# 4. Asks to validate all problem instances the agent has downloaded every x minutes


import sys
import os
import time
import schedule
import threading

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from network.agent_node import AgentNode


# Agent
agent_name = sys.argv[1]
agent = AgentNode(agent_name)

# Agent events
def download_problem_instance():
    problem_instance = agent.download_problem_instance()
    return problem_instance
    
def solve_problem_instance(problem_instance):
    # Start a thread that will solve the problem instance (use daemon threads so that this thread does not continue to run after the main thread has finished)
    solver_thread = threading.Thread(target=agent.solve_problem_instance, args=(problem_instance,), daemon=True)
    solver_thread.start()
    return solver_thread

def check_submit_solution_status():
    for problem_instance in agent.problem_instances:
        active_solution_submission_ids = agent.problem_instances[problem_instance]["active_solution_submission_ids"].copy()   # copy the list since we will remove elements from it
        for solution_submit_id in active_solution_submission_ids:
            agent.check_submit_solution_status(solution_submit_id)

def validate_solutions():
    for problem_instance in agent.problem_instances:
        agent.validate_solution_request(problem_instance)

# Schedule agent events
schedule.every(1).minutes.do(validate_solutions)
schedule.every(1).minutes.do(check_submit_solution_status)

solver_thread = None
execution_time = int(sys.argv[2])   # in seconds
start_time = time.time()
elapsed_time = 0
while elapsed_time < execution_time:
    # Agent will start solving a problem instance that he just downloaded - this means that in this experiment the agent will only solve each problem instance "once"
    if agent.solving_problem_instance_name is None:
        if solver_thread is not None:
            solver_thread.join()   # wait for the solver thread to finish before we start a new one
        problem_instance = download_problem_instance()
        if problem_instance is not None:
            solver_thread = solve_problem_instance(problem_instance)   # TODO: could also if the problem instance in None to solve any problem instance that is already downloaded and active (since it will be None if we have tried solving every problem instance on the platform)
    
    schedule.run_pending()
    time.sleep(10)
    elapsed_time = time.time() - start_time

time.sleep(30)   # wait a little bit since agent might still be validating a solution

# NOTE: if there is a solution submission that is still being validated then we will not wait for that (impossible to know and it is the central node that controls this)

# Clean up agent
check_submit_solution_status()   # run check solution submission status event to claim rewards before shutting down
agent.clean_up()