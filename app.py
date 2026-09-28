import sqlite3
from flask import Flask, jsonify

app = Flask(__name__)


# opens the database when a route needs it
def get_db():
    connection = sqlite3.connect("locker.db")
    connection.row_factory = sqlite3.Row
    return connection


@app.route("/")
def home():
    return "Smart Locker Room server is running"


# shows all lockers in the database
@app.route("/lockers")
def list_lockers():
    connection = get_db()
    rows = connection.execute("SELECT * FROM lockers").fetchall()
    connection.close()

    return jsonify([dict(row) for row in rows])


if __name__ == "__main__":
    app.run(debug=True)