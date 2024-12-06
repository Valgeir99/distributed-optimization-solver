### Agent loop in experiment 1 - agent will solve problem as a main function here ###

# Command line arguments:
# 1. Agent name
# 2. Execution time in seconds


# Agent does the following:
# 1. Downloads a single problem instance, supportcase16
# 2. Solves only this whole problem instance the whole time
# 3. After submitting a solution then the agent should check the status every x minutes until the problem is validated
# 4. Asks to validate the single problem instnace the agent has downloaded every x minutes

# TODO: add randomness?


import sys
import os
import time
import schedule
import threading
import random

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from network.agent_node import AgentNode


# Agent
agent = AgentNode()

# Agent events
def download_problem_instance_data_by_name(problem_instance_name):
    problem_instance = agent.download_problem_instance_data_by_name(problem_instance_name)
    return problem_instance
    
def solve_problem_instance(problem_instance):
    # Start a thread that will solve the problem instance (use daemon threads so that this thread does not continue to run after the main thread has finished)
    #solver_thread = threading.Thread(target=agent.solve_problem_instance, args=(problem_instance,), daemon=True)
    #solver_thread.start()
    #return solver_thread
    agent.solve_problem_instance(problem_instance)

def check_submit_solution_status():
    for problem_instance in agent.problem_instances:
        active_solution_submission_ids = agent.problem_instances[problem_instance]["active_solution_submission_ids"].copy()   # copy the list since we will remove elements from it
        for solution_submit_id in active_solution_submission_ids:
            agent.check_submit_solution_status(solution_submit_id)

def validate_solutions():
    for problem_instance in agent.problem_instances:
        agent.validate_solution_request(problem_instance)
# TODO: one big flaw with this is that in a smaller network then in the beginning most solutions will not get 
# accepted since agents won't validate it since they have not downloaded the problem instance (could let agents 
# download more at the beginning or change some logic)

def update_problem_instance_status():
    for problem_instance in agent.problem_instances:
        agent.update_problem_instance_status(problem_instance)

# Schedule agent events
#schedule.every(1).minutes.do(validate_solutions)
schedule.every(5).minutes.do(check_submit_solution_status)
#schedule.every(5).minutes.do(update_problem_instance_status)   # not necessarry but this will clean up solver memory if problem instance is not active anymore

solver_thread = None
execution_time = int(sys.argv[1])   # in seconds
start_time = time.time()
elapsed_time = 0
problem_instance = download_problem_instance_data_by_name("p0201")

# Solve 90% of the time and validate 10% of the time - approach below is not perfect but should be fine, the agent 
# basically solves until 90% of his time has been spent solving then he validates until less than 90% of his time is 
# spent solving, and then he starts to solve again and so on 
# We choose this approach over e.g. solving with probability 0.9 and validating with probability 0.1 since time solving 
# and validating is not the same so this approach would most likely result in solving more than 90% of the time
time_spent_solving = 0
time_spent_validating = 0
target_solve_ratio = 0.9
target_validate_ratio = 0.1

try:
    while elapsed_time < execution_time:
        # Calculate remaining time and adjust probabilities dynamically
        total_time_spent = time_spent_solving + time_spent_validating
        
        if total_time_spent > 0:
            solve_ratio = time_spent_solving / total_time_spent
            validate_ratio = time_spent_validating / total_time_spent
        else:
            solve_ratio = 0
            validate_ratio = 0      

        # if solve_ratio < target_solve_ratio:
        #     solve_probability = 1.0
        # elif validate_ratio < target_validate_ratio:
        #     solve_probability = 0.0
        # else:
        #     # This case will probably "never" happen
        #     solve_probability = 0.9
        solve_probability = max(0.1, min(0.9, target_solve_ratio - solve_ratio + random.uniform(-0.05, 0.05)))
        #validate_probability = 1 - solve_probability  # Complementary probability


        # Randomly choose the action based on probabilities
        action = 'solve' if random.random() < solve_probability else 'validate'

        start_action_time = time.time()

        if action == 'solve':
            solve_problem_instance(problem_instance)
            time_spent_solving += time.time() - start_action_time
        else:
            validate_solutions()
            time_spent_validating += time.time() - start_action_time

        schedule.run_pending()
        elapsed_time = time.time() - start_time

        # TODO: one thing that could happen is that agents are solving for a long time and they miss the validation phase for a solution, 
        # so in that case there would be soltuions submitted that are not accepted since agents are just not validating them 
        # I HAVE NO CLUE HOW TO DEAL WITH THAT THOUGH...???

except KeyboardInterrupt:
    pass

finally:

    time.sleep(5)   # wait a little bit since agent might still be validating a solution

    print(f"Agent {agent.id} time spent solving: {time_spent_solving}, time spent validating: {time_spent_validating} out of total time: {elapsed_time}")
    print(f"Agent might be stuck solving in the end of the execution time so out of the planned execution time of {execution_time} seconds the agent effectively spent \
          {time_spent_validating} seconds validating and {execution_time-time_spent_validating} seconds solving ratio of \
          {time_spent_validating/execution_time} and {1-time_spent_validating/execution_time} respectively")
    # NOTE agent might be solving for some time after the execution time has passed since the agent might be in the middle of solving a problem instance so we 
    # account for that in the output
    


    # Clean up agent
    agent.clean_up()
    print(f"Agent {agent.id} finished execution")