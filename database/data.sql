-- Insert initial problem instances into problem_instances table
-- Note: The file_location is relative to the root of the project
INSERT INTO problem_instances (name, description, file_location, reward_budget)
VALUES 
('p0201', 'Optimization Problem 1', 'data/miplib_problem_instances/p0201.mps', 100000000),
('supportcase16', 'Optimization Problem 2', 'data/miplib_problem_instances/supportcase16.mps', 100000000),
('cod105', 'Optimization Problem 3', 'data/miplib_problem_instances/cod105.mps', 100000000),
('glass-sc', 'Optimization Problem 4', 'data/miplib_problem_instances/glass-sc.mps', 100000000),
('neos-1516309', 'Optimization Problem 5', 'data/miplib_problem_instances/neos-1516309.mps', 100000000),
('iis-hc-cov', 'Optimization Problem 6', 'data/miplib_problem_instances/iis-hc-cov.mps', 100000000),
('reblock354', 'Optimization Problem 7', 'data/miplib_problem_instances/reblock354.mps', 100000000),
('tanglegram6', 'Optimization Problem 8', 'data/miplib_problem_instances/tanglegram6.mps', 100000000)
;