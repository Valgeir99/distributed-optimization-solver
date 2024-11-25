from typing import TypedDict, Dict

import numpy as np
import pulp as pl
from typing import Tuple
import time
#from scipy.sparse import csr_matrix


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
    Solver for binary integer problems. It offers ...
    (And more like parser, ...) TODO
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

        # TODO: maybe we want to add class variables for like if we have solved this before and stuff like that


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

    
    def _generate_random_bip_solution(self, problem_instance_name) -> Tuple[bool, np.array, float]:
        """
        Generates a random feasible solution for a binary integer problem in some time limit.

        """
        # Unpack the problem data
        c = self.problem_data[problem_instance_name]["c"]
        A = self.problem_data[problem_instance_name]["A"]
        rhs = self.problem_data[problem_instance_name]["rhs"]
        constraint_types = self.problem_data[problem_instance_name]["constraint_types"]

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
    

    # TODO: maybe not have this private and we will call this from the agent depending on what the result form the solver will be
    def _solution_to_sol_file(self, problem_instance_name:str, file: str, solution: np.array, obj: float):
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
        Raises:
            Exception: if there is an error writing the solution to the .sol file
        """
        variable_names = self.problem_data[problem_instance_name]["var_names"]
        try:
            with open(file, "w") as f:
                f.write("\n")
                f.write(f"=obj= {obj}\n")
                for i, val in enumerate(solution):
                    f.write(f"{variable_names[i]} {int(val)}\n")
        except Exception as e:
            raise Exception(f"Error writing solution to .sol file: {e}") from e


    # TODO: Now we are just generating a single solution not necessarily the best solution and we are not checking if the solution is better than the best solution
    def solve(self, problem_instance_name: str, best_self_sol_path: str, best_platform_sol_path: str):
        """
        Solves a binary integer problem.
        It writes the solution to a .sol file. ... TODO ?
        
        Args:
            problem_instance_name: name of the problem instance
            best_self_sol_path: path to the .sol file where the best solution found by the solver will be written
            best_platform_sol_path: path to the .sol file where the best solution on the platform is stored
        Returns:
            tuple:
                - found: True if a feasible solution is found, False otherwise
                - solution_data: solution data string generated from a .sol file
                - obj: objective value of the solution
        Raises:
            Exception: if solving fails
        """
        # TODO: need to rethink this whole function!!

        try:
            # Check if the problem has registered to the solver
            if problem_instance_name not in self.problem_data:
                raise ValueError(f"Problem instance '{problem_instance_name}' not found in solver.")
                        
            # Generate a random feasible solution
            print("Solving problem:", problem_instance_name)
            # TODO: if we use subprocess then we might want to have a wrapper function that calls this function and only
            # returns the solution if it is imporving the best solution
            # TODO: we probably want to have some loop here so we can run this multiple times and then return the best solution?
            # But we need to think about that in regards to the subprocess thing since we don't want to start a new process 
            # every time...
            found, solution, obj = self._generate_random_bip_solution(problem_instance_name)
            # TODO: depending on solver we will use we might want to return different stuff if solver find a better solution or not (maybe only have exception if solver fails but 
            # not if it doesn't find a better solution?)

            solution_data = ""
            # TODO: we should only write the solution to a file if it is better than the best solution on the platform! (but now we are doing it every time)
            if found:
                # Write the solution to a .sol file
                self._solution_to_sol_file(problem_instance_name, best_self_sol_path, solution, obj)    #TODO: maybe we should not write to file here but in agent code instead?
                print("Solution written to", best_self_sol_path)

                with open(best_self_sol_path, "r") as f:   # TODO: just a temp solution to get the solution data
                    solution_data = f.read()
            else:
                print("No feasible solution found")

            return found, solution_data, obj
        
        except Exception as e:
            # General error handling to propagate to the calling function
            raise Exception(f"Error when calling solve: {str(e)}") from e


        # TODO: check if the problem is actually improving the best solution? - depends how we want to use this function (just remember that 
        # we don't have access to the agent node data from here since I want the solver to be generic so it could be e.g. C solver or commercial 
        # like gurobi). So 
        # Also note that it is not a good idea to run this function as a subprocess if we call it muliple times, we would rather 
        # just call it single time and then not return anything but just save the solution to a file and then read that file 
        # from the agent node I guess...?


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


    def validate(self, problem_instance_name: str, solution_data: str) -> Tuple[bool, float]:
        """
        Validates a solution (feasbile or not) for a binary integer problem (BIP).
        The solution is excpected to be in the format of a .sol file (Miplib format) as described in function "solution_to_sol_file()".    
        
        Args:
            problem_instance_name: name of the problem instance
            solution_data: solution data string generated from a .sol file
        Returns:
            tuple:
                - feasible: True if a feasible solution is found, False otherwise
                - obj: objective value of the solution
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

            return feasible, objective   # TODO: maybe we don't want to return the objective value? Also maybe we want to compare best solution on platform with this solution? So we 
            # would input that objecticve value also...

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

    

        