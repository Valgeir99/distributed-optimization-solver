import sqlite3
import threading
from fastapi import FastAPI
import uvicorn
from dotenv import load_dotenv
import os
import time

from utils.database_utils import create_database, teardown_database
from config import DB_PATH

load_dotenv()
CENTRAL_NODE_HOST = os.getenv("CENTRAL_NODE_HOST")
CENTRAL_NODE_PORT = int(os.getenv("CENTRAL_NODE_PORT"))



# TODO: maybe later add in another thread/background task that will check if reward 
# for problem instance is finshed

class CentralNode:
    """A central node that has a web server to comminicate with agent nodes and stores data in a local database."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        """Singleton pattern to ensure only one instance of the central node is created."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        else:
            raise Exception("CentralNode instance already exists!")
        return cls._instance
        

    # TODO: I just put the web_server as an argument to the constructor because I thought it would be better
    # so that people realize that the central node needs a web server to work...
    def __init__(self, web_server: FastAPI):
        """Initialize the central node with a web server and connect to the database."""

        self.host = CENTRAL_NODE_HOST
        self.port = CENTRAL_NODE_PORT

        # Database
        self.db_path = DB_PATH
        create_database(self.db_path)
        self.db_connection = self.__connect_to_database()
        #self.edit_data_in_db("INSERT INTO central_nodes (id, host, port) VALUES (?, ?, ?)", (self.id, self.host, self.port))

        # Web server
        self.web_server = web_server
              
        self.lock = threading.Lock()
             


    def __connect_to_database(self):
        """Create a connection to the database."""
        try:
            connection = sqlite3.connect(self.db_path, check_same_thread=False)   # check_same_thread=False is needed for multithreading
            print(f"Connected to database at {self.db_path}")
            return connection
        except sqlite3.Error as e:
            # Raise exception to stop the program (we can't continue without the database)
            raise sqlite3.Error(f"Error while connecting to database at {self.db_path}: {e}")


    def __disconnect_from_database(self):
        """Close the connection to the database."""
        try:
            self.db_connection.close()
            print(f"Disconnected from database at {self.db_path}")
        except sqlite3.Error as e:
            print(f"Error while disconnecting from database at {self.db_path}: {e}")


    def query_db(self, query: str, params: tuple=()) -> list[dict] | None:
        """Query the database and return the result.
        Returns: 
            list: The result of the query or None if an error occurred."""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute(query, params)
            result = cursor.fetchall()
            # Return a list of dictionaries with the column names as keys
            columns = [description[0] for description in cursor.description]
            result_dict = [dict(zip(columns, row)) for row in result]
            cursor.close()
            return result_dict
        except sqlite3.Error as e:
            print(f"Error while querying database at {self.db_path}: {e}")
            return None
        # TODO: remember we need to check if the result is None when we call this function!!



    def edit_data_in_db(self, query: str, params: tuple=()):
        """Insert/Delete data in the database."""
        with self.lock:
            try:
                cursor = self.db_connection.cursor()
                cursor.execute(query, params)
                self.db_connection.commit()
                cursor.close()
            except sqlite3.Error as e:
                self.db_connection.rollback()
                raise sqlite3.Error(f"Error while editing data in database at {self.db_path}: {e}")



