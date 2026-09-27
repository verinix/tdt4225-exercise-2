import os
import mysql.connector as mysql
from dotenv import load_dotenv

load_dotenv()

class DbConnector:
    def __init__(self):
        self.db_connection = mysql.connect(
            host="127.0.0.1",
            port=3306,
            database="tdt4225",
            user="tdt4225",
            password=os.environ["MYSQL_PASSWORD"]
        )
        
        self.cursor = self.db_connection.cursor()

    def close_connection(self):
        self.cursor.close()
        self.db_connection.close()
