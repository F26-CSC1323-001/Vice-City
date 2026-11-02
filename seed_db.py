import sqlite3

# opens the database
connection = sqlite3.connect("locker.db")

# adds four lockers
connection.execute("INSERT INTO lockers (locker_number) VALUES (1)")
connection.execute("INSERT INTO lockers (locker_number) VALUES (2)")
connection.execute("INSERT INTO lockers (locker_number) VALUES (3)")
connection.execute("INSERT INTO lockers (locker_number) VALUES (4)")

# saves the changes
connection.commit()
connection.close()

print("Lockers added.")