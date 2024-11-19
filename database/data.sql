-- Insert initial problem instances into problem_instances table
INSERT INTO problem_instances (name, client_id, description, file_location, reward_budget)
VALUES 
('p0201', 'valgeir', 'Optimization Problem 1', 'C:\Users\valge\OneDrive\Documents\DTU\Master thesis\Code\distributed-optimization-solver\data\problem_instances\p0201.mps', 10000),
('supportcase16', 'valgeir', 'Optimization Problem 2', 'C:\Users\valge\OneDrive\Documents\DTU\Master thesis\Code\distributed-optimization-solver\data\problem_instances\supportcase16.mps', 15000),
('cod105', 'valgeir', 'Optimization Problem 3', 'C:\Users\valge\OneDrive\Documents\DTU\Master thesis\Code\distributed-optimization-solver\data\problem_instances\cod105.mps', 15000),
('glass-sc', 'valgeir', 'Optimization Problem 4', 'C:\Users\valge\OneDrive\Documents\DTU\Master thesis\Code\distributed-optimization-solver\data\problem_instances\glass-sc.mps', 15000),
('neos-1516309', 'valgeir', 'Optimization Problem 5', 'C:\Users\valge\OneDrive\Documents\DTU\Master thesis\Code\distributed-optimization-solver\data\problem_instances\neos-1516309.mps', 15000)

--('sorrell3', 'valgeir', 'Optimization Problem 7', 'C:\Users\valge\OneDrive\Documents\DTU\Master thesis\Code\distributed-optimization-solver\data\problem_instances\sorrell3.mps', 15000)

-- Not binary problem TODO investigate
--('qap10', 'valgeir', 'Optimization Problem 6', 'C:\Users\valge\OneDrive\Documents\DTU\Master thesis\Code\distributed-optimization-solver\data\problem_instances\qap10.mps', 15000)