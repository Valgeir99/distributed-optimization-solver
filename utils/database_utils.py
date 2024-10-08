import sqlite3
import os

# Function to create a new database after tearing down the old one
def create_database(db_path):
    # Tear down the existing database if it exists
    teardown_database(db_path)

    # Create new database
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()

    # Read and execute the SQL schema
    with open('../database/schema.sql', 'r') as f:
        schema = f.read()
    cursor.executescript(schema)

    # Optionally insert initial data
    with open('../database/data.sql', 'r') as f:
        data_insert = f.read()
    cursor.executescript(data_insert)

    connection.commit()
    connection.close()
    print(f"New database created and initial data loaded at {db_path}")

# Teardown function to remove the database if it exists
def teardown_database(db_path):
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Database at {db_path} removed.")


def connect_to_database(db_path):
    return sqlite3.connect(db_path)

def close_database_connection(connection):
    connection.close()

def query_db(connection, query, params=()):
    cursor = connection.cursor()
    cursor.execute(query, params)
    result = cursor.fetchall()
    cursor.close()
    return result

# Example usage
if __name__ == "__main__":
    create_database('central_node.db')
    connection = connect_to_database('central_node.db')
    result = query_db(connection, "SELECT * FROM problem_instances")
    print(result)
    close_database_connection(connection)
    teardown_database('central_node.db')


