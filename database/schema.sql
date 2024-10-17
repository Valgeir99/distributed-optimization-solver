--## Database schema for database on central nodes for distributed optimization solver ##--

-- Create problem_instances table
CREATE TABLE problem_instances (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    description TEXT,
    instance_file_location TEXT NOT NULL,
    reward_accumulated INTEGER DEFAULT 0,
    reward_budget INTEGER NOT NULL
);

-- Create agent_nodes table
CREATE TABLE agent_nodes (
    id TEXT PRIMARY KEY
    --host TEXT NOT NULL,
    --port INTEGER NOT NULL
);

-- Create central_nodes table
CREATE TABLE central_nodes (
    id TEXT PRIMARY KEY,
    host TEXT NOT NULL,
    port INTEGER NOT NULL
);

-- Create all_solutions table
CREATE TABLE all_solutions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    problem_instance_id TEXT,
    agent_node_id TEXT,
    submission_time DATETIME NOT NULL,
    objective_value INTEGER NOT NULL,
    reward INTEGER NOT NULL,
    FOREIGN KEY (problem_instance_id) REFERENCES problem_instances (id),
    FOREIGN KEY (agent_node_id) REFERENCES agent_nodes (id)
);

-- Create best_solutions table
CREATE TABLE best_solutions (
    problem_instance_id TEXT PRIMARY KEY,
    solution_id INTEGER,
    solution_file_location TEXT NOT NULL,
    --objective_value INTEGER NOT NULL, -- redundant since it's in all_solutions
    --submission_time DATETIME NOT NULL,
    FOREIGN KEY (problem_instance_id) REFERENCES problem_instances (id),
    FOREIGN KEY (solution_id) REFERENCES all_solutions (id)
);

-- Create connections table
CREATE TABLE connections (
    agent_node_id TEXT,
    central_node_id TEXT,
    problem_instance_id TEXT,
    PRIMARY KEY (agent_node_id, central_node_id, problem_instance_id), -- agent_node_id, central_node_id, and problem_instance_id together form a unique key
    FOREIGN KEY (agent_node_id) REFERENCES agent_nodes (id) ON DELETE CASCADE, -- ON DELETE CASCADE to delete all connections to a node when it is deleted
    FOREIGN KEY (central_node_id) REFERENCES central_nodes (id) ON DELETE CASCADE,
    FOREIGN KEY (problem_instance_id) REFERENCES problem_instances (id) ON DELETE CASCADE
);

-- TODO: possibly add rewards table for tracking rewards
-- "If you foresee complex reward distribution mechanisms, consider a separate table to track agent earnings 
-- over time (e.g., reward_transactions with agent_id, problem_instance_id, reward_amount, and timestamp)."
