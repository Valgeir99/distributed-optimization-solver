-- Insert initial problem instances into problem_instances table
-- Note: The file_location is relative to the root of the project
INSERT INTO problem_instances (name, client_id, description, file_location, reward_budget)
VALUES 
('p0201', 'valgeir', 'Optimization Problem 1', 'data/miplib_problem_instances/p0201.mps', 100),
('supportcase16', 'valgeir', 'Optimization Problem 2', 'data/miplib_problem_instances/supportcase16.mps', 15000),
('cod105', 'valgeir', 'Optimization Problem 3', 'data/miplib_problem_instances/cod105.mps', 15000),
('glass-sc', 'valgeir', 'Optimization Problem 4', 'data/miplib_problem_instances/glass-sc.mps', 15000),
('neos-1516309', 'valgeir', 'Optimization Problem 5', 'data/miplib_problem_instances/neos-1516309.mps', 15000)

--('sorrell3', 'valgeir', 'Optimization Problem 7', 'C:\Users\valge\OneDrive\Documents\DTU\Master thesis\Code\distributed-optimization-solver\data\problem_instances\sorrell3.mps', 15000)

-- Not binary problem TODO investigate
--('qap10', 'valgeir', 'Optimization Problem 6', 'C:\Users\valge\OneDrive\Documents\DTU\Master thesis\Code\distributed-optimization-solver\data\problem_instances\qap10.mps', 15000)