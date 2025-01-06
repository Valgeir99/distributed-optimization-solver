import os

# Get the project root directory
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Database configuration
SCHEMA_PATH = os.path.join(PROJECT_ROOT, 'database', 'schema.sql')
DATA_PATH = os.path.join(PROJECT_ROOT, 'database', 'data.sql')

# Experiment directory - has subdirectories for each experiment and keeps temporary node data for each experiment and more
EXPERIMENT_DIR = os.path.join(PROJECT_ROOT, 'experiments')
EXPERIMENT_DATA_DIR = os.path.join(PROJECT_ROOT, 'experiments', 'experiments_data')

# Central node configuration
CENTRAL_NODE_HOST = "127.0.0.1"
CENTRAL_NODE_PORT = 8080

# Network parameters directory
NETWORK_PARAMS_DIR = os.path.join(PROJECT_ROOT, 'network', 'network.params')
