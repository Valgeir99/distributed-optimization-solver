import sqlite3
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import SCHEMA_PATH, DATA_PATH

# Function to create a new database after tearing down the old one
def create_database(db_path):
    try:
        # Tear down the existing database if it exists
        teardown_database(db_path)

        # Create new database
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()

        # Read and execute the SQL schema
        with open(SCHEMA_PATH, 'r') as f:
            schema = f.read()
        cursor.executescript(schema)

        # Optionally insert initial data
        with open(DATA_PATH, 'r') as f:
            data_insert = f.read()
        cursor.executescript(data_insert)

        connection.commit()
        connection.close()
        print(f"New database created and initial data loaded at {db_path}")
    
    except sqlite3.Error as e:
        raise sqlite3.Error(f"SQLite error creating database at {db_path}: {e}")
    
    except FileNotFoundError as e:
        raise FileNotFoundError(f"File not found when creating database at {db_path}: {e}")

# Teardown function to remove the database if it exists
def teardown_database(db_path):
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"Database at {db_path} removed.")
    except OSError as e:
        print(f"Error removing database at {db_path}: {e}")


def connect_to_database(db_path):
    try:
        return sqlite3.connect(db_path)
    except sqlite3.Error as e:
        print(f"Error connecting to database at {db_path}: {e}")
        return None

def close_database_connection(connection):
    try:
        connection.close()
    except sqlite3.Error as e:
        print(f"Error closing database connection: {e}")

def query_db(connection, query, params=()):
    try:
        cursor = connection.cursor()
        cursor.execute(query, params)
        result = cursor.fetchall()
        cursor.close()
        return result
    except sqlite3.Error as e:
        print(f"Error querying database: {e}")
        return None

# Example usage
if __name__ == "__main__":
    create_database('central_node.db')
    connection = connect_to_database('central_node.db')
    result = query_db(connection, "SELECT * FROM problem_instances")
    print(result)
    close_database_connection(connection)
    teardown_database('central_node.db')


