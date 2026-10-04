import sqlite3

# opens the database
connection = sqlite3.connect("locker.db")

# adds two lockers
connection.execute("INSERT INTO lockers (locker_number) VALUES (1)")
connection.execute("INSERT INTO lockers (locker_number) VALUES (2)")

# adds one demo payment card.
connection.execute(
    "INSERT INTO demo_cards (card_uid, balance) VALUES ('CARD001', 25.00)"
)

# saves the changes
connection.commit()
connection.close()

print("Lockers and demo card added.")