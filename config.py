import os
from dotenv import load_dotenv

# Get the project root directory
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Define the paths based on the project root
DB_PATH = os.path.join(PROJECT_ROOT, 'database', 'central_node.db')
SCHEMA_PATH = os.path.join(PROJECT_ROOT, 'database', 'schema.sql')
DATA_PATH = os.path.join(PROJECT_ROOT, 'database', 'data.sql')
BEST_SOLUTIONS_DIR = os.path.join(PROJECT_ROOT, 'data', 'best_solutions')