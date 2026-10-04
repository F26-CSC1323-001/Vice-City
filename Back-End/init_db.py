import sqlite3

# creates the database file
connection = sqlite3.connect("locker.db")

# reads the table setup from schema.sql
with open("schema.sql") as f:
    connection.executescript(f.read())

# closes the connection when setup is finished
connection.close()

print("Database created successfully.")