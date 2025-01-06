from typing import TypedDict, Dict

import numpy as np
import pulp as pl
from typing import Tuple
import time
import os
#from scipy.sparse import csr_matrix

# NOTE: since agents will be able to change the state of the solver we need to make sure to always check the state of the solver before we do anything with self.problem_data

class ProblemDataParsed(TypedDict):
    """BIP problem data parsed from .mps file to a format suitable for the solver."""
    name: str
    var_names: list[str]
    c: np.array
    A: np.array # TODO: make A a csr_matrix
    rhs: np.array
    constraint_types: list[str]


class BIPSolver:
    """
    Solver for binary integer problems.
    This solver can parse .mps files, generate random feasible solutions, and validate solutions.
    Problem instance need to be added to the solver, where they are then parsed, before they can be solved or validated.
    
    Problems are represented on array format:

        min c^T * x

        s.t. A*x <constraint_type> rhs
            lb <= x <= ub
            
            where 
                x_i integer if integrality[i] = 1
                constraint_type is 'E' for ==, 'L' for <=, 'G' for >=
    """

    def __init__(self):
        """Initializes the solver."""
        # Dictionary to store parsed problem data with problem name as key and parsed data as value
        self.problem_data: Dict[str, ProblemDataParsed] = dict()


    @staticmethod
    def _check_if_bip(integrality: list, variable_lb: np.array, variable_ub: np.array) -> bool:
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
            return False
        if not all(variable_lb == 0) or not all(variable_ub == 1):
            return False

        return True


    def _parse_mps_file(self, file_path: str) -> Tuple[str, list[str], np.array, np.array, np.array, list[str]]:
        """
        Only for binary integer problems.
        Reads a .mps (standard form - assume minimization) and parses problem to array format:

            min c^T * x

            s.t. A*x <constraint_type> rhs
                lb <= x <= ub
                
                where 
                    x_i integer if integrality[i] = 1
                    constraint_type is 'E' for ==, 'L' for <=, 'G' for >=
        
        Args:
            file_path: path to the .mps file
        Returns:
            tuple:
                - name: name of the problem
                - var_names: list of variable names
                - c: objective vector
                - A: constraint matrix
                - rhs: right-hand side vector
                - constraint_types: list of constraint types
        Raises:
            Exception: if there is an error parsing the .mps file
        """

        try:
            # Read the .mps file using pulp
            _, model = pl.LpProblem.fromMPS(file_path)

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


            # Check if the problem is a binary integer problem
            if not self._check_if_bip(integrality, variable_lb, variable_ub):
                raise ValueError("Problem is not a binary integer problem.")
            
            return name, variable_names, c, A, rhs, constraint_types

        except Exception as e:
            raise Exception(f"Error parsing .mps file: {e}") from e
        

    def add_problem_instance(self, problem_instance_file_path: str):
        """
        Adds a problem instance (bip) to the solver so its data can be accessed easily on 
        array format later on.
        
        Args:
            problem_instance_file_path: path to the .mps file
        Raises:
            Exception: if there is an error adding the problem instance
        """
        try:
            # Parse the .mps file for binary problem
            name, variable_names, c, A, rhs, constraint_types = self._parse_mps_file(problem_instance_file_path)
            # Save the parsed problem data
            self.problem_data[name] = {
                "name": name,
                "var_names": variable_names,
                "c": c,
                "A": A,  #csr_matrix(A),
                "rhs": rhs,
                "constraint_types": constraint_types
            }
        except Exception as e:
            raise Exception(f"Error adding problem instance: {e}") from e
        

    def remove_problem_instance(self, problem_instance_name: str):
        """
        Removes a problem instance from the solver.
        
        Args: 
            problem_instance_name: name of the problem instance
        """
        if problem_instance_name not in self.problem_data:
            return
        
        del self.problem_data[problem_instance_name]

    
    def _generate_random_bip_solution(self, problem_instance_name: str, max_time: int) -> Tuple[bool, np.array, float, int]:
        """
        Generates a random feasible solution for a binary integer problem in some time limit.
        Args:
            problem_instance_name: name of the problem instance
            max_time: maximum time to generate a solution in seconds
        Returns:
            tuple:
                - feasible: True if a feasible solution is found, False otherwise
                - solution: solution array
                - obj: objective value of the solution
                - iterations: number of iterations
        """
        # Unpack the problem data
        c = self.problem_data[problem_instance_name]["c"]
        A = self.problem_data[problem_instance_name]["A"]
        rhs = self.problem_data[problem_instance_name]["rhs"]
        constraint_types = self.problem_data[problem_instance_name]["constraint_types"]

        # Start with random solution
        solution = np.random.randint(0, 2, len(c))

        # Loop until a feasible solution is found within the time limit
        max_contraints_holding = 0
        elapsed_time = 0.0
        iter = 0
        iter_stuck = 0   # number of iterations with no improvement in number of contraints holding
        RANDOM_RESTART_ITER = 10000
        constraints_holding_prev_iter = 0
        while elapsed_time < max_time:
            start_time = time.time()
            constraints_holding = 0
            iter += 1
            
            # Iterate over constraints and flip random variables that affect the contraint until the constraint is satisfied 
            # (note that by making one contraint satisfied we might violate another)
            for i in np.random.permutation(A.shape[0]):
                constraint = A[i]
                lhs = np.dot(solution, constraint)
                if constraint_types[i] == 'L' and lhs > rhs[i]:
                    while lhs > rhs[i]:
                        candidate_indices = np.where(
                            ((constraint < 0) & (solution == 0)) | ((constraint > 0) & (solution == 1))
                        )[0]
                        idx = np.random.choice(candidate_indices)
                        solution[idx] = 1 - solution[idx]   # flip the variable
                        lhs = np.dot(solution, constraint)
                elif constraint_types[i] == 'G' and lhs < rhs[i]:
                    while lhs < rhs[i]:
                        candidate_indices = np.where(
                            ((constraint > 0) & (solution == 0)) | ((constraint < 0) & (solution == 1))
                        )[0]
                        idx = np.random.choice(candidate_indices)
                        solution[idx] = 1 - solution[idx]
                        lhs = np.dot(solution, constraint)
                elif constraint_types[i] == 'E' and lhs != rhs[i]:
                    while lhs != rhs[i]:
                        # Flip based on if the lhs is greater or less than rhs
                        if lhs > rhs[i]:
                            candidate_indices = np.where(
                                ((constraint < 0) & (solution == 0)) | ((constraint > 0) & (solution == 1))
                            )[0]
                            idx = np.random.choice(candidate_indices)
                            solution[idx] = 1 - solution[idx]
                            lhs = np.dot(solution, constraint)
                        elif lhs < rhs[i]:
                            candidate_indices = np.where(
                                ((constraint > 0) & (solution == 0)) | ((constraint < 0) & (solution == 1))
                            )[0]
                            idx = np.random.choice(candidate_indices)
                            solution[idx] = 1 - solution[idx]
                            lhs = np.dot(solution, constraint)
                           
            # Check feasibility
            feasible = True
            for i in np.random.permutation(A.shape[0]):
                constraint = A[i]
                lhs = np.dot(solution, constraint)
                if constraint_types[i] == 'L' and lhs > rhs[i]:
                    feasible = False
                    break
                elif constraint_types[i] == 'G' and lhs < rhs[i]:
                    feasible = False
                    break
                elif constraint_types[i] == 'E' and lhs != rhs[i]:
                    feasible = False
                    break
                constraints_holding += 1

            
            if constraints_holding > max_contraints_holding:
                max_contraints_holding = constraints_holding

            if feasible:
                obj = np.dot(c, solution)
                return True, solution, obj, iter
            
            if constraints_holding_prev_iter <= constraints_holding:
                iter_stuck += 1
                
            if iter_stuck > RANDOM_RESTART_ITER:
                #print("stuck in infeasible solution - start from new random solution")
                solution = np.random.randint(0, 2, len(c))
                iter_stuck = 0
            
            elapsed_time = time.time()-start_time
            constraints_holding_prev_iter = constraints_holding

        return False, solution, -1, iter
    

    def _generate_random_bip_solution_simple(self, problem_instance_name: str, max_time: int) -> Tuple[bool, np.array, float, int]:
        ### Just generate a completely random solution in some time limit ###

        # Unpack the problem data
        c = self.problem_data[problem_instance_name]["c"]
        A = self.problem_data[problem_instance_name]["A"]
        rhs = self.problem_data[problem_instance_name]["rhs"]
        constraint_types = self.problem_data[problem_instance_name]["constraint_types"]

        elapsed_time = 0.0
        start_time = time.time()
        iter = 0
        while elapsed_time < max_time:
            # Random solution
            solution = np.random.randint(0, 2, len(c))
            # Check feasibility
            feasible = self._check_feasibility(solution, A, rhs, constraint_types)

            if feasible:
                # Calculate the objective value
                objective = np.dot(c, solution)
                return feasible, solution, objective
            
            elapsed_time = time.time() - start_time
            iter += 1

        return False, solution, -1, iter
    

    def _solution_to_sol_file(self, problem_instance_name: str, file: str, solution: np.array, obj: float) -> str:
        """
        Writes a solution to a .sol file (we define format as Miplib's format - first line empty, then 
        objective value and then variables values line by line). The objective value line first has "=obj="
        and then the value of the objective seperated by space. The lines with variables have the 
        variable name, blank space and then the value of the variable.
        
        Args:
            problem_instance_name: name of the problem instance
            file: path to the .sol file
            solution: solution array
            obj: objective value
        Returns:
            solution_data: solution data string generated from a .sol file
        """
        # Get solution data on correct format
        variable_names = self.problem_data[problem_instance_name]["var_names"]
        solution_data = ""
        solution_data += "\n"
        solution_data += f"=obj= {obj}\n"
        for i, val in enumerate(solution):
            solution_data += f"{variable_names[i]} {int(val)}\n"
        
        # Write the solution to the .sol file
        try:
            with open(file, "w") as f:
                f.write(solution_data)
        except Exception as e:
            pass   # not so important to raise exception here
            #raise Exception(f"Error writing solution to .sol file: {e}") from e
        finally:
            return solution_data
        

    def solve(self, problem_instance_name: str, best_self_sol_path: str|None, best_obj: float|None, max_solve_time: int) -> Tuple[bool, float|None, str]:
        """
        Solves a binary integer problem that has been added to the solver. The solver generates a random feasible solution 
        and tries to find an improved feasible solution within a time limit. If an improved feasible solution is found,
        it writes the solution to a .sol file and returns that is was found, otherwise it returns that no solution was found.

        Args:
            problem_instance_name: name of the problem instance
            best_self_sol_path: path to the .sol file where the best solution found by the solver will be written
            best_obj: objective value of the best solution on the platform or best solution found by the agent itself, whichever is better
            max_solve_time: maximum time to solve (improve the solution) the problem in seconds
        Returns:
            tuple:
                - found: True if an improved feasible solution is found, False otherwise
                - obj: objective value of the solution
        Raises:
            Exception: if solving fails
        """
        try:
            found = False
            obj = None
            solution_data = ""

            # Check if the problem has registered to the solver
            if problem_instance_name not in self.problem_data:
                raise ValueError(f"Problem instance '{problem_instance_name}' not found in solver.")
            
            # Solve until we find an improved feasible solution or time runs out
            elapsed_time = 0.0
            start_time = time.time()
            max_solve_time_func = max_solve_time
            iterations = 0
            while elapsed_time < max_solve_time:
                # Generate a random feasible solution
                feasible, solution, obj, iters = self._generate_random_bip_solution(problem_instance_name, max_solve_time_func)
                iterations += iters
                if feasible:
                    if best_obj is None or obj < best_obj:
                        found = True
                        # Write the solution to a .sol file
                        solution_data = self._solution_to_sol_file(problem_instance_name, best_self_sol_path, solution, obj)
                        break
                elapsed_time = time.time() - start_time
                max_solve_time_func = max_solve_time - elapsed_time
                    
            return found, obj, solution_data, iterations
        
        except Exception as e:
            # General error handling to propagate to the calling function
            raise Exception(f"Error when calling solve: {str(e)}") from e


    @staticmethod
    def _check_feasibility(x: np.array, A: np.array, rhs: np.array, constraint_types: list) -> bool:
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


    def validate(self, problem_instance_name: str, solution_data: str, best_obj: float|None) -> tuple[bool, float]:
        """
        Validates a solution (feasbile or not) for a binary integer problem (BIP).
        The solution is excpected to be in the format of a .sol file (Miplib format) as described in function "solution_to_sol_file()".    
        
        Args:
            problem_instance_name: name of the problem instance
            solution_data: solution data string generated from a .sol file
            best_obj: objective value of the best solution on the platform or best solution found by the agent itself, whichever is better
        Returns:
            tuple:
                - valid: True if the solution is valid, False otherwise
                - objective: objective value of the solution
        Raises:
            Exception: if problem can not be validated
        """
        # We implement robust error handling for the solution data since that file comes from another agent 
        # so we don't know if it is on the correct format or not
        try:
            # Check if the problem has registered to the solver
            if problem_instance_name not in self.problem_data:
                raise ValueError(f"Problem instance '{problem_instance_name}' not found in solver.")

            # Unpack the problem data
            c = self.problem_data[problem_instance_name]["c"]
            A = self.problem_data[problem_instance_name]["A"]
            rhs = self.problem_data[problem_instance_name]["rhs"]
            constraint_types = self.problem_data[problem_instance_name]["constraint_types"]
            variable_names = self.problem_data[problem_instance_name]["var_names"]

            # Parse solution data
            lines = solution_data.splitlines()
            if len(lines) < 3:
                raise ValueError("Solution file format error: File is too short.")

            # Parse variables into solution array
            solution = np.zeros(len(variable_names))
            for line in lines[2:]:
                parts = line.split()
                if len(parts) != 2:
                    raise ValueError("Solution file format error: Invalid variable assignment line.")

                var, val = parts
                if var not in variable_names:
                    raise ValueError(f"Solution file format error: Variable '{var}' not found in problem definition.")
                
                try:
                    solution[variable_names.index(var)] = int(val)
                except ValueError:
                    raise ValueError(f"Solution file format error: Non-integer value '{val}' for variable '{var}'.")

            # Check feasibility
            feasible = self._check_feasibility(solution, A, rhs, constraint_types)

            # Calculate the objective value
            objective = np.dot(c, solution)

            # Check if the objective value is better than the best objective value on the platform and better than the best objective value found by the agent itself
            if feasible:
                if best_obj is None or objective < best_obj:
                    return True, objective

            return False, objective

        except Exception as e:
            # General error handling to propagate to the calling function
            raise Exception(f"Validation failed: {str(e)}") from e
    
    
    def get_objective_value(self, problem_instance_name: str, solution_data: str) -> float:
        """Calculates the objective value of a solution for a binary integer problem (BIP).
        The solution is assumed to be in the format of a .sol file (Miplib format) as described in function "solution_to_sol_file()"

        Args:
            problem_instance_name: name of the problem instance
            solution_data: solution data string generated from a .sol file
        Returns:
            objective: objective value of the solution
        Raises:
            Exception: if any error occurs during the calculation
        """
        # We assume trust here since this solution file has been validated by the platform - so we don't need to check the solution data format
        # as in function "validate_feasibility_bip_solution()"

        try:
            # Check if the problem has registered to the solver
            if problem_instance_name not in self.problem_data:
                raise ValueError(f"Problem instance '{problem_instance_name}' not found in solver.")

            # Unpack the problem data
            c = self.problem_data[problem_instance_name]["c"]
            variable_names = self.problem_data[problem_instance_name]["var_names"]

            # Parse solution data
            lines = solution_data.splitlines()

            # Parse variables into solution array
            solution = np.zeros(len(variable_names))
            for line in lines[2:]:
                parts = line.split()
                var, val = parts
                solution[variable_names.index(var)] = int(val)
            
            # Calculate the objective value
            objective = np.dot(c, solution)
        
        except Exception as e:
            raise Exception(f"Objective calculation failed: {str(e)}") from e

        return objective

    

        