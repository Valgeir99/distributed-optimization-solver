import os
from datetime import datetime
from dotenv import load_dotenv

# Get the project root directory
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Define the paths based on the project root
DB_PATH = os.path.join(PROJECT_ROOT, 'database', 'central_node.db')
SCHEMA_PATH = os.path.join(PROJECT_ROOT, 'database', 'schema.sql')
DATA_PATH = os.path.join(PROJECT_ROOT, 'database', 'data.sql')
BEST_SOLUTIONS_DIR = os.path.join(PROJECT_ROOT, 'data', 'best_solutions')
AGENT_DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'agent_data')

# New log file each time the program is run
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE_PATH = os.path.join(PROJECT_ROOT, 'data', 'logs', f'log_{timestamp}.log')
open(LOG_FILE_PATH, 'w').close()