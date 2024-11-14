--## Database schema for database on central nodes for distributed optimization solver ##--

-- TODO: update schema to be the same as in drawio diagram


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
-- CREATE TABLE agent_nodes (
--     id TEXT PRIMARY KEY
--     --host TEXT NOT NULL,
--     --port INTEGER NOT NULL
-- );

-- Create central_nodes table
-- CREATE TABLE central_nodes (
--     id TEXT PRIMARY KEY,
--     host TEXT NOT NULL,
--     port INTEGER NOT NULL
-- );

-- Create solution_submissions table (TODO: not sure if I will use all of these columns since we might instead want to use in memory data structures since we only have 
-- one central node and we can just keep track of the data in memory since it is way faster than constantly querying the database)
-- CREATE TABLE solution_submissions (
--     id INTEGER PRIMARY KEY AUTOINCREMENT,
--     problem_instance_name TEXT,
--     agent_node_id TEXT,
--     submission_time DATETIME NOT NULL,
--     objective_value INTEGER NOT NULL,
--     reward INTEGER NOT NULL,
--     solution_status TEXT NOT NULL,   -- status of the solution (e.g., "submitted", "accepted", "rejected")
--     number_of_validations INTEGER DEFAULT 0,
--     number_of_rejections INTEGER DEFAULT 0,
--     number_of_acceptances INTEGER DEFAULT 0,
--     FOREIGN KEY (problem_instance_name) REFERENCES problem_instances (name),
--     FOREIGN KEY (agent_node_id) REFERENCES agent_nodes (id)
-- );

-- Create all_solutions table
CREATE TABLE all_solutions (
    id TEXT PRIMARY KEY,
    problem_instance_name TEXT NOT NULL,
    submission_time DATETIME NOT NULL,
    validation_end_time DATETIME NOT NULL,
    objective_value INTEGER DEFAULT NULL,
    reward_accumulated INTEGER DEFAULT 0,
    accepted BOOLEAN DEFAULT NULL,   -- whether the solution was accepted as current best one or not (NULL if not yet evaluated)
    FOREIGN KEY (problem_instance_name) REFERENCES problem_instances (name)
);

-- Create best_solutions table
CREATE TABLE best_solutions (
    problem_instance_name TEXT PRIMARY KEY,
    solution_id INTEGER,
    file_location TEXT NOT NULL,
    --objective_value INTEGER NOT NULL, -- redundant since it's in all_solutions
    --submission_time DATETIME NOT NULL,
    FOREIGN KEY (problem_instance_name) REFERENCES problem_instances (name),
    FOREIGN KEY (solution_id) REFERENCES all_solutions (id)
);

-- Create connections table
-- CREATE TABLE connections (
--     agent_node_id TEXT,
--     central_node_id TEXT,
--     --problem_instance_id TEXT,
--     PRIMARY KEY (agent_node_id, central_node_id), -- agent_node_id, central_node_id, and problem_instance_id together form a unique key
--     FOREIGN KEY (agent_node_id) REFERENCES agent_nodes (id) ON DELETE CASCADE, -- ON DELETE CASCADE to delete all connections to a node when it is deleted
--     FOREIGN KEY (central_node_id) REFERENCES central_nodes (id) ON DELETE CASCADE
--     --FOREIGN KEY (problem_instance_id) REFERENCES problem_instances (id) ON DELETE CASCADE
-- );

-- TODO: possibly add rewards table for tracking rewards
-- "If you foresee complex reward distribution mechanisms, consider a separate table to track agent earnings 
-- over time (e.g., reward_transactions with agent_id, problem_instance_id, reward_amount, and timestamp)."
