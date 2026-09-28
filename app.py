import sqlite3
from datetime import datetime, timedelta

from flask import Flask, jsonify, request
from werkzeug.security import generate_password_hash

app = Flask(__name__)

PRICES = {
    "30min": 2.00,
    "1hour": 3.00,
    "2hours": 5.00,
    "4hours": 8.00,
    "allday": 12.00
}

MINUTES = {
    "30min": 30,
    "1hour": 60,
    "2hours": 120,
    "4hours": 240,
    "allday": 1440
}


def get_db():
    connection = sqlite3.connect("locker.db")
    connection.row_factory = sqlite3.Row
    return connection


@app.route("/")
def home():
    return "Smart Locker Room server is running"


@app.route("/lockers")
def list_lockers():
    connection = get_db()
    rows = connection.execute("SELECT * FROM lockers").fetchall()
    connection.close()
    return jsonify([dict(row) for row in rows])


@app.route("/rent", methods=["POST"])
def rent():
    data = request.get_json()

    name = data.get("name")
    phone = data.get("phone")
    pin = data.get("pin")
    duration = data.get("duration")
    card_uid = data.get("card_uid")

    if not name or not phone or not pin or not duration or not card_uid:
        return jsonify({"error": "Missing information"}), 400

    if not (pin.isdigit() and 4 <= len(pin) <= 6):
        return jsonify({"error": "PIN must be 4 to 6 digits"}), 400

    if duration not in PRICES:
        return jsonify({"error": "Invalid duration"}), 400

    price = PRICES[duration]
    connection = get_db()

    card = connection.execute(
        "SELECT * FROM demo_cards WHERE card_uid = ?",
        (card_uid,)
    ).fetchone()

    if card is None:
        connection.close()
        return jsonify({"error": "Card not recognized"}), 404

    if card["balance"] < price:
        connection.close()
        return jsonify({"error": "Not enough balance"}), 402

    locker = connection.execute(
        "SELECT * FROM lockers WHERE status = 'available' LIMIT 1"
    ).fetchone()

    if locker is None:
        connection.close()
        return jsonify({"error": "No lockers available"}), 409

    user = connection.execute(
        "SELECT * FROM users WHERE phone = ?",
        (phone,)
    ).fetchone()

    pin_hash = generate_password_hash(pin)

    if user is None:
        cursor = connection.execute(
            "INSERT INTO users (name, phone, pin_hash) VALUES (?, ?, ?)",
            (name, phone, pin_hash),
        )
        user_id = cursor.lastrowid

    else:
        user_id = user["id"]

        active = connection.execute(
            "SELECT id FROM rentals WHERE user_id = ? AND status = 'active'",
            (user_id,),
        ).fetchone()

        if active:
            connection.close()
            return jsonify(
                {"error": "This phone number already has an active rental"}
            ), 409

        connection.execute(
            "UPDATE users SET name = ?, pin_hash = ? WHERE id = ?",
            (name, pin_hash, user_id),
        )

    start = datetime.now()
    end = start + timedelta(minutes=MINUTES[duration])

    connection.execute(
        "UPDATE demo_cards SET balance = balance - ? WHERE card_uid = ?",
        (price, card_uid),
    )

    connection.execute(
        "INSERT INTO rentals "
        "(user_id, locker_id, start_time, end_time, amount_paid) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            user_id,
            locker["id"],
            start.isoformat(),
            end.isoformat(),
            price,
        ),
    )

    connection.execute(
        "UPDATE lockers "
        "SET status = 'occupied', lock_status = 'unlocked' "
        "WHERE id = ?",
        (locker["id"],),
    )

    connection.commit()
    connection.close()

    return jsonify({
        "locker_number": locker["locker_number"],
        "end_time": end.isoformat(),
        "amount_paid": price,
        "new_balance": card["balance"] - price,
    })


if __name__ == "__main__":
    app.run(debug=True)