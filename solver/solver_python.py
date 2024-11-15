"""
Module for solving binary integer problems using a random heuristic.
Problems are represented on array format in the module functions:

    min c^T * x

    s.t. A*x <constraint_type> rhs
        lb <= x <= ub
        
        where 
            x_i integer if integrality[i] = 1
            constraint_type is 'E' for ==, 'L' for <=, 'G' for >=
"""

# TODO: maybe have some solver interface that all solvers should implement so that we can easily switch between them
# https://chatgpt.com/c/6731fcfb-aaac-8003-bd9a-fbe8b51d0583

import pulp as pl
import numpy as np
from typing import Tuple
import time
import random


def read_mps(file: str) -> Tuple[str, list, np.array, np.array, np.array, list, np.array, np.array, np.array]:
    """
    Reads a .mps (standard form - assume minimization) and returns the data of the problem on array format:

        min c^T * x

        s.t. A*x <constraint_type> rhs
            lb <= x <= ub
            
            where 
                x_i integer if integrality[i] = 1
                constraint_type is 'E' for ==, 'L' for <=, 'G' for >=
    
    Args:
        file: path to the .mps file
    Returns:
        name: name of the problem
        variable_names: list of variable names
        c: objective vector
        A: constraint matrix
        rhs: right-hand side vector
        constraint_types: list of constraint types
        variable_lb: lower bounds for variables
        variable_ub: upper bounds for variables
        integrality: binary vector indicating if variable is integer
    """

    # Read the .mps file using pulp
    _, model = pl.LpProblem.fromMPS(file)

    # Name of problem
    name = model.name

    # List of variables of type pulp.pulp.LpVariable
    variables = model.variables()

    # Number of variables and constraints
    num_vars = len(variables)
    num_constraints = len(model.constraints)

    # Variable names
    variable_names = [var.name for var in variables]

    # Variable bounds and types
    variable_lb = np.array([var.lowBound if var.lowBound is not None else -np.inf for var in variables])
    variable_ub = np.array([var.upBound if var.upBound is not None else np.inf for var in variables])
    integrality = np.array([1 if (var.cat == 'Binary' or var.cat == 'Integer') else 0 for var in variables])

    # Initialize objective vector
    c = np.zeros(num_vars)

    # Populate objective vector with coefficients
    for i, var in enumerate(variables):
        c[i] = model.objective.get(var, 0)  # Get coefficient or 0 if not in objective

    # Initialize constraint matrix A (num_contraints x num_vars) and RHS vector
    A = np.zeros((num_constraints, num_vars))
    rhs = np.zeros(num_constraints)
    constraint_types = []

    # Populate constraint matrix and RHS
    for i, (cname, constraint) in enumerate(model.constraints.items()):
        rhs[i] = -constraint.constant  # Adjusting for PuLP format
        if constraint.sense == pl.LpConstraintEQ:
            constraint_types.append('E')
        elif constraint.sense == pl.LpConstraintLE:
            constraint_types.append('L')
        elif constraint.sense == pl.LpConstraintGE:
            constraint_types.append('G')
        
        # Fill in the coefficients for the constraint row in A
        for var, coeff in constraint.items():
            var_index = variable_names.index(var.name)
            A[i, var_index] = coeff


    return name, variable_names, c, A, rhs, constraint_types, variable_lb, variable_ub, integrality


def check_feasibility(x: np.array, A: np.array, rhs: np.array, constraint_types: list) -> bool:
    """
    Checks if a solution x is feasible for the problem defined by A, rhs and constraint_types.
    
    Args:
        x: solution vector
        A: constraint matrix
        rhs: right-hand side vector
        constraint_types: list of constraint types
    Returns:
        True if feasible, False otherwise
    """
    for i, constraint in enumerate(A):
        lhs = np.dot(x, constraint)
        if constraint_types[i] == 'L' and lhs > rhs[i]:
            return False
        elif constraint_types[i] == 'G' and lhs < rhs[i]:
            return False
        elif constraint_types[i] == 'E' and lhs != rhs[i]:
            return False

    return True

    
def generate_random_bip_solution(c, A, rhs, constraint_types, variable_lb, variable_ub, integrality) -> Tuple[np.array, float]:
    """
    Generates a random feasible solution for a binary integer problem in some time limit.

    """
    # print("number of variables", A.shape[1])
    # print("number of constraints", A.shape[0])

    max_contraints_holding = 0
    elapsed_time = 0
    max_time = 120  # seconds

    # TODO: add randomness!

    # Start with all variables set to 0
    #solution = np.zeros(len(c))
    solution = np.random.randint(0, 2, len(c))

    # Loop until a feasible solution is found
    iter = 0
    #for _ in range(10000):
    while elapsed_time < max_time:
        start_time = time.time()
        constraints_holding = 0
        iter += 1
        

        # Iterate over constraints and flip variables until a feasible solution is found
        #for i, constraint in enumerate(A):
        for i in np.random.permutation(A.shape[0]):   # try iterating over contraints randomly
            constraint = A[i]
            lhs = np.dot(solution, constraint)
            #print("constraint", constraint)
            #print("lhs", lhs, "rhs", rhs[i])
            # TODO: make function for this since it is repeated in the equal case
            # TODO: maybe better to introduce randomness here instead of flippinng variable with most influence (could be slower convergance but more likely to find solution in the end?)
            if constraint_types[i] == 'L' and lhs > rhs[i]:
                #print("contraint number ", i)
                while lhs > rhs[i]:
                    #print("lhs is greater than rhs")
                    #print("lhs", lhs, "rhs", rhs[i])
                    # Select a variable with high contribution to the constraint (can be positive or negative) and set it to 
                    # 0 if positive and 1 if negative since we want to increase the lhs
                    idx_positive = np.argmax(constraint * solution)   # we only want variables that are currently 1 and will have negative contribution (increasing the lhs) if set to 0
                    idx_negative = np.argmin(constraint * (1 - solution))   # we only want variables that are currently 0 and will have negative contribution (increasaing the lhs) if set to 1
                    # Select which one is higher
                    a_positive = constraint[idx_positive]
                    a_negative = constraint[idx_negative]
                    if abs(a_positive) >= abs(a_negative):
                        solution[idx_positive] = 0
                    else:
                        #print("idx_negative", idx_negative, "a_negative", a_negative)
                        solution[idx_negative] = 1
                    lhs = np.dot(solution, constraint)
                    #print("lhs", lhs, "rhs", rhs[i])
            elif constraint_types[i] == 'G' and lhs < rhs[i]:
                #print("contraint number ", i)
                while lhs < rhs[i]:
                    #print("lhs is less than rhs")
                    #print("lhs", lhs, "rhs", rhs[i])
                    # Select a variable with high contribution to the constraint (can be positive or negative) and set it to 
                    # 1 if positive and 0 if negative since we want to decrease the lhs
                    idx_positive = np.argmax(constraint * (1 - solution))   # we only want variables that are currently 0 and will have positive contribution (increasing the lhs) if set to 1
                    idx_negative = np.argmin(constraint * solution)   # we only want variables that are currently 1 and will have positive contribution (increasing the lhs) if set to 0
                    # Select which one is higher
                    a_positive = constraint[idx_positive]
                    a_negative = constraint[idx_negative]
                    if abs(a_positive) >= abs(a_negative):   # TODO: maybe if equal then select randomly
                        solution[idx_positive] = 1
                    else:
                        #print("idx_negative", idx_negative, "a_negative", a_negative)
                        solution[idx_negative] = 0
                    lhs = np.dot(solution, constraint)
                    #print("lhs", lhs, "rhs", rhs[i])
            elif constraint_types[i] == 'E' and lhs != rhs[i]:
                #print("contraint number ", i)
                while lhs != rhs[i]:
                    #print("lhs is not equal to rhs")
                    #print("lhs", lhs, "rhs", rhs[i])
                    if lhs > rhs[i]:
                        # Select a variable with high contribution to the constraint (can be positive or negative) and set it to
                        # 0 if positive and 1 if negative since we want to decrease the lhs
                        idx_positive = np.argmax(constraint * solution)   # we only want variables that are currently 1 and will have negative contribution (increasing the lhs) if set to 0
                        idx_negative = np.argmin(constraint * (1 - solution))   # we only want variables that are currently 0 and will have negative contribution (increasaing the lhs) if set to 1
                        # Select which one is higher
                        a_positive = constraint[idx_positive]
                        a_negative = constraint[idx_negative]
                        if abs(a_positive) >= abs(a_negative):
                            solution[idx_positive] = 0
                        else:
                            #print("idx_negative", idx_negative, "a_negative", a_negative)
                            solution[idx_negative] = 1
                        lhs = np.dot(solution, constraint)
                        #print("lhs", lhs, "rhs", rhs[i])
                    elif lhs < rhs[i]:
                        # Select a variable with high contribution to the constraint (can be positive or negative) and set it to
                        # 1 if positive and 0 if negative since we want to increase the lhs
                        idx_positive = np.argmax(constraint * (1 - solution))   # we only want variables that are currently 0 and will have positive contribution (increasing the lhs) if set to 1
                        idx_negative = np.argmin(constraint * solution)   # we only want variables that are currently 1 and will have positive contribution (increasing the lhs) if set to 0
                        # Select which one is higher
                        a_positive = constraint[idx_positive]
                        a_negative = constraint[idx_negative]
                        if abs(a_positive) >= abs(a_negative):
                            solution[idx_positive] = 1
                        else:
                            #print("idx_negative", idx_negative, "a_negative", a_negative)
                            solution[idx_negative] = 0
                        lhs = np.dot(solution, constraint)
                        #print("lhs", lhs, "rhs", rhs[i])

        # Do equality constraints last since they are the most difficult to satisfy?
        # for i, constraint in enumerate(A):
        #     lhs = np.dot(solution, constraint)
        #     if constraint_types[i] == 'E' and lhs != rhs[i]:
        #         print("contraint number ", i)
        #         while lhs != rhs[i]:
        #             print("lhs is not equal to rhs")
        #             print("lhs", lhs, "rhs", rhs[i])
        #             if lhs > rhs[i]:
        #                 # Select a variable with high contribution to the constraint (can be positive or negative) and set it to
        #                 # 0 if positive and 1 if negative since we want to decrease the lhs
        #                 idx_positive = np.argmax(constraint * solution)   # we only want variables that are currently 1 and will have negative contribution (increasing the lhs) if set to 0
        #                 idx_negative = np.argmin(constraint * (1 - solution))   # we only want variables that are currently 0 and will have negative contribution (increasaing the lhs) if set to 1
        #                 # Select which one is higher
        #                 a_positive = constraint[idx_positive]
        #                 a_negative = constraint[idx_negative]
        #                 if abs(a_positive) > abs(a_negative):
        #                     solution[idx_positive] = 0
        #                 else:
        #                     #print("idx_negative", idx_negative, "a_negative", a_negative)
        #                     solution[idx_negative] = 1
        #                 lhs = np.dot(solution, constraint)
        #                 print
        #             elif lhs < rhs[i]:
        #                 # Select a variable with high contribution to the constraint (can be positive or negative) and set it to
        #                 # 1 if positive and 0 if negative since we want to increase the lhs
        #                 idx_positive = np.argmax(constraint * (1 - solution))   # we only want variables that are currently 0 and will have positive contribution (increasing the lhs) if set to 1
        #                 idx_negative = np.argmin(constraint * solution)   # we only want variables that are currently 1 and will have positive contribution (increasing the lhs) if set to 0
        #                 # Select which one is higher
        #                 a_positive = constraint[idx_positive]
        #                 a_negative = constraint[idx_negative]
        #                 if abs(a_positive) > abs(a_negative):
        #                     solution[idx_positive] = 1
        #                 else:
        #                     #print("idx_negative", idx_negative, "a_negative", a_negative)
        #                     solution[idx_negative] = 0
        #                 lhs = np.dot(solution, constraint)
        #                 print("lhs", lhs, "rhs", rhs[i])


            
        # Check feasibility
        feasible = True
        # for i, constraint in enumerate(A):
        #     lhs = np.dot(solution, constraint)
        #     if constraint_types[i] == 'L' and lhs > rhs[i]:
        #         feasible = False
        #         break
        #     elif constraint_types[i] == 'G' and lhs < rhs[i]:
        #         feasible = False
        #         break
        #     elif constraint_types[i] == 'E' and lhs != rhs[i]:
        #         feasible = False
        #         break
        #     iter += 1

        #for i, constraint in enumerate(A):
        for i in np.random.permutation(A.shape[0]):
            constraint = A[i]
            lhs = np.dot(solution, constraint)
            #print("constraint", constraint)
            #print("lhs", lhs, "rhs", rhs[i])
            if constraint_types[i] == 'L' and lhs > rhs[i]:
                #print("lhs is greater than rhs")
                # Flip a random variable contributing to violation
                idx = np.random.choice(np.where(constraint != 0)[0])   # TODO: think about here and for 'G' if I should flip a random variable or the one with the highest contribution
                solution[idx] = 1 - solution[idx]
                feasible = False
                break
            elif constraint_types[i] == 'G' and lhs < rhs[i]:
                #print("lhs is less than rhs")
                # Flip a random variable contributing to violation
                idx = np.random.choice(np.where(constraint != 0)[0])
                solution[idx] = 1 - solution[idx]
                feasible = False
                break
            elif constraint_types[i] == 'E' and lhs != rhs[i]:
                #print("lhs is not equal to rhs")
                # Flip a random variable contributing to violation
                idx = np.random.choice(np.where(constraint != 0)[0])
                solution[idx] = 1 - solution[idx]
                feasible = False
                break
            constraints_holding += 1

        # Check feasibility
        # for i, constraint in enumerate(A):
        #     lhs = np.dot(solution, constraint)
        #     if constraint_types[i] == 'L' and lhs > rhs[i]:
        #         feasible = False
        #         break
        #     elif constraint_types[i] == 'G' and lhs < rhs[i]:
        #         feasible = False
        #         break
        #     elif constraint_types[i] == 'E' and lhs != rhs[i]:
        #         feasible = False
        #         break
        #     constraints_holding += 1

        #print("number of contraints holding:", constraints_holding)

        if constraints_holding > max_contraints_holding:
            print("max number of constraints holding:", constraints_holding)
            max_contraints_holding = constraints_holding

        if feasible:
            print("feasible solution found!!!!")
            print("number of iterations:", iter)
            obj = np.dot(c, solution)
            return True, solution, obj
        
        elapsed_time += time.time()-start_time

        # Go over contraints again that are still violated and flip variables - repair phase
        #for i, constraint in enumerate(A):

    print("max number of constraints holding:", max_contraints_holding)
    print("number of iterations:", iter)


    return False, solution, -1





def check_if_bip(integrality, variable_lb, variable_ub):
    """
    Checks if the problem is a binary integer problem.
    
    Args:
        integrality: binary vector indicating if variable is integer (1 if integer, 0 otherwise)
        variable_lb: lower bounds for variables
        variable_ub: upper bounds for variables
    Returns:
        True if binary integer problem, False otherwise
    """
    # Check if the model is a binary integer program
    if not all(integrality):
        print("Model contains non-integer variables")
        return False
    if not all(variable_lb == 0) or not all(variable_ub == 1):
        print("Model contains non-binary integer variables") 
        return False

    return True


def solution_to_sol_file(file: str, variable_names: list, solution: np.array, obj: float):
    """
    Writes a solution to a .sol file (we define format as Miplib's format - first line empty, then 
    objective value and then variables values line by line). The objective value line first has "=obj="
    and then the value of the objective seperated by space. The lines with variables have the 
    variable name, blank space and then the value of the variable.
    
    Args:
        file: path to the .sol file
        variable_names: list of variable names
        solution: solution vector
        obj: objective value
    """
    with open(file, "w") as f:
        f.write("\n")
        f.write(f"=obj= {obj}\n")
        for i, val in enumerate(solution):
            f.write(f"{variable_names[i]} {int(val)}\n")


# Now we are just generating a single solution not necessarily the best solution and we are not checking if the solution is better than the best solution
def solve_bip(problem_instance_path: str, solution_path: str, best_solution_path: str):
    """
    Reads a .mps file and solves the problem if it is binary integer problem. We assume the problem is 
    feasible. It writes the solution to a .sol file. ... TODO
    
    Args:
        file: path to the .mps file
    Returns:
        True if a feasible solution is found, False otherwise
    Raises:
        ValueError: if the problem is not a binary integer problem  TODO: we cannot do this in e.g. C solver so maybe we don't want this?
    """
    # Read the .mps file
    name, variable_names, c, A, rhs, constraint_types, variable_lb, variable_ub, integrality = read_mps(problem_instance_path)

    # Check if the problem is a binary integer problem
    if not check_if_bip(integrality, variable_lb, variable_ub):
        raise ValueError("Problem is not a binary integer problem")
    
    # Generate a random feasible solution
    print("Solving problem:", name)
    # TODO: if we use subprocess then we might want to have a wrapper function that calls this function and only
    # returns the solution if it is imporving the best solution
    # TODO: we probably want to have some loop here so we can run this multiple times and then return the best solution?
    # But we need to think about that in regards to the subprocess thing since we don't want to start a new process 
    # every time...
    found, solution, obj = generate_random_bip_solution(c, A, rhs, constraint_types, variable_lb, variable_ub, integrality)

    solution_data = ""
    if found:
        # Write the solution to a .sol file
        solution_to_sol_file(solution_path, variable_names, solution, obj)
        print("Solution written to", solution_path)

        with open(solution_path, "r") as f:   # TODO: just a temp solution to get the 
            solution_data = f.read()
    else:
        print("No feasible solution found")

    return found, solution_data, obj


    # TODO: check if the problem is actually improving the best solution? - depends how we want to use this function (just remember that 
    # we don't have access to the agent node data from here since I want the solver to be generic so it could be e.g. C solver or commercial 
    # like gurobi). So 
    # Also note that it is not a good idea to run this function as a subprocess if we call it muliple times, we would rather 
    # just call it single time and then not return anything but just save the solution to a file and then read that file 
    # from the agent node I guess...?


def validate_bip(problem_instance_path: str, solution_data: str) -> Tuple[bool, float]:
    """
    Reads a .mps file and a solution data string generated from a .sol file and validates the solution if it is binary integer problem. 
    We ned to implement robust error handling for the solution data since that file comes from another agent and we don't know if it is 
    on the correct format. We expect the file to be on the same format as describe in "solution_to_sol_file()" function.
    
    Args:
        problem_instance_path: path to the .mps file for the problem instance
        solution_data: solution data string generated from a .sol file
    Returns:
        feasible: True if a feasible solution is found, False otherwise
        obj: objective value of the solution
    """
    # Read the .mps file
    name, variable_names, c, A, rhs, constraint_types, variable_lb, variable_ub, integrality = read_mps(problem_instance_path)

    # Check if the problem is a binary integer problem
    if not check_if_bip(integrality, variable_lb, variable_ub):
        print("Problem is not a binary integer problem")
        return False, -1

    # Read the .sol file and validate the format
    try:
        lines = solution_data.splitlines()
        
        # Basic format checks
        if len(lines) < 3:
            print("Solution file format error: File is too short.")
            return False, -1
        
        # Parse objective value line
        # try:
        #     obj = float(lines[1].split()[1])
        # except (IndexError, ValueError):
        #     print("Solution file format error: Objective line is malformed.")
        #     return False, -1
        
        # Parse variables into solution array
        solution = np.zeros(len(variable_names))
        for line in lines[2:]:
            parts = line.split()
            if len(parts) != 2:
                print("Solution file format error: Invalid variable assignment line.")
                return False, -1

            var, val = parts
            if var not in variable_names:
                print(f"Solution file format error: Variable '{var}' not found in problem definition.")
                return False, -1

            try:
                solution[variable_names.index(var)] = int(val)   # put in the variable value in the correct index to match the contraint matrix A read above
            except ValueError:
                print(f"Solution file format error: Non-integer value '{val}' for variable '{var}'.")
                return False, -1

    except IOError:
        print("Could not read solution file.")
        return False, -1
    
    # Check if the solution is feasible
    feasible = check_feasibility(solution, A, rhs, constraint_types)

    # Calculate objective
    objective = np.dot(c, solution)

    # TODO: compaire objective to best one on platform needs to be improving otherwise we 
    # should not accept the solution - also we need to define somewhere in the code that 
    # we are just looking at MINIMIZATION problems! (since .mps files from miplib are minimized I think)

    if feasible:
        print("Solution is feasible")
        return True, objective
    else:
        print("Solution is not feasible")
        return False, objective