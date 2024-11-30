--## Database schema for database on central nodes for distributed optimization solver ##--

-- Create problem_instances table
CREATE TABLE problem_instances (
    name TEXT PRIMARY KEY,   -- name of the problem instance is unique (instead of id)
    client_id TEXT NOT NULL,
    description TEXT,
    file_location TEXT NOT NULL,
    reward_accumulated INTEGER DEFAULT 0,
    reward_budget INTEGER NOT NULL,
    active BOOLEAN DEFAULT 1   -- whether the problem instance is active (1) on the platform or not (0)
);

-- Create agent_nodes table
CREATE TABLE agent_nodes (
    id TEXT PRIMARY KEY
);

-- Create all_solutions table
CREATE TABLE all_solutions (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,   -- id of the agent that submitted the solution
    problem_instance_name TEXT NOT NULL,
    submission_time DATETIME NOT NULL,
    validation_end_time DATETIME NOT NULL,
    objective_value INTEGER DEFAULT NULL,
    reward_accumulated INTEGER DEFAULT 0,
    accepted BOOLEAN DEFAULT NULL,   -- whether the solution was accepted as current best one or not (NULL if not yet evaluated)
    sol_file_path TEXT,   -- location of the solution file (path would only exist during solution validation phase)
    FOREIGN KEY (problem_instance_name) REFERENCES problem_instances (name),
    FOREIGN KEY (agent_id) REFERENCES agent_nodes (id)
);

-- Create active_solutions_submissions_validations table - it stores the validation responses of the agents for the active solution submissions
CREATE TABLE active_solutions_submissions_validations (
    solution_submission_id TEXT KEY,
    problem_instance_name TEXT,
    agent_validated_id TEXT NOT NULL,   -- id of the agent that validated the solution
    validation_response BOOLEAN NOT NULL,   -- whether the agent accepted (1) or rejected (0) the solution
    objective_value INTEGER NOT NULL,   -- objective value calulated by the agent
    reward INTEGER NOT NULL,   -- reward that should be given to the agent who validated by the agent
    PRIMARY KEY (solution_submission_id, agent_validated_id),   -- each agent can only validate each solution submission once
    FOREIGN KEY (solution_submission_id) REFERENCES all_solutions (id),
    FOREIGN KEY (problem_instance_name) REFERENCES problem_instances (name),
    FOREIGN KEY (agent_validated_id) REFERENCES agent_nodes (id)
);

-- Create best_solutions table
CREATE TABLE best_solutions (
    problem_instance_name TEXT PRIMARY KEY,
    solution_id TEXT NOT NULL,
    file_location TEXT NOT NULL,
    FOREIGN KEY (problem_instance_name) REFERENCES problem_instances (name),
    FOREIGN KEY (solution_id) REFERENCES all_solutions (id)
);
