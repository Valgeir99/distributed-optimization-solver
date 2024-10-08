-- Insert initial problem instances into problem_instances table
INSERT INTO problem_instances (id, client_id, description, instance_file_location, reward_accumulated, reward_budget)
VALUES 
('instance_1', 'client_1', 'Optimization Problem 1', '/path/to/problem1.mps', 0, 100),
('instance_2', 'client_2', 'Optimization Problem 2', '/path/to/problem2.mps', 0, 150),
('instance_3', 'client_3', 'Optimization Problem 3', '/path/to/problem3.mps', 0, 200);
