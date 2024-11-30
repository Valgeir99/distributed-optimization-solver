import os
from datetime import datetime
from dotenv import load_dotenv

# Get the project root directory
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Database configuration
SCHEMA_PATH = os.path.join(PROJECT_ROOT, 'database', 'schema.sql')
DATA_PATH = os.path.join(PROJECT_ROOT, 'database', 'data.sql')

# Temporary data configuration - delete the data before running the program
AGENT_DATA_DIR = os.path.join(PROJECT_ROOT, 'network', 'agent_data_tmp')
CENTRAL_DATA_DIR = os.path.join(PROJECT_ROOT, 'network', 'central_data_tmp')
DB_PATH = os.path.join(CENTRAL_DATA_DIR, 'central_node.db')
BEST_SOLUTIONS_DIR = os.path.join(CENTRAL_DATA_DIR, 'best_solutions')
ACTIVE_SOLUTIONS_DIR = os.path.join(CENTRAL_DATA_DIR, 'active_solutions')

# Experiment directory - has subdirectories for each experiment
EXPERIMENT_DIR = os.path.join(PROJECT_ROOT, 'experiments')
EXPERIMENT_DATA_DIR = os.path.join(PROJECT_ROOT, 'experiments', 'experiments_data')