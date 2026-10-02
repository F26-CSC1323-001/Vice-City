import sqlite3
from datetime import datetime, timedelta

from flask import Flask, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

PRICES = {"30min": 2.00, "1hour": 3.00, "2hours": 5.00, "4hours": 8.00, "allday": 12.00}
MINUTES = {"30min": 30, "1hour": 60, "2hours": 120, "4hours": 240, "allday": 1440}

ADMIN_PIN = "9999"  # placeholder for the prototype — swap for something real later


def get_db():
    connection = sqlite3.connect("locker.db")
    connection.row_factory = sqlite3.Row
    return connection


def get_locker_by_number(connection, locker_number):
    return connection.execute(
        "SELECT * FROM lockers WHERE locker_number = ?", (locker_number,)
    ).fetchone()


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
        "SELECT * FROM demo_cards WHERE card_uid = ?", (card_uid,)
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
        "SELECT * FROM users WHERE phone = ?", (phone,)
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
            return jsonify({"error": "This phone number already has an active rental"}), 409
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
        "INSERT INTO rentals (user_id, locker_id, start_time, end_time, amount_paid) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, locker["id"], start.isoformat(), end.isoformat(), price),
    )
    connection.execute(
        "UPDATE lockers SET status = 'occupied', lock_status = 'unlocked' WHERE id = ?",
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


@app.route("/open-locker", methods=["POST"])
def open_locker():
    data = request.get_json()
    phone = data.get("phone")
    pin = data.get("pin")

    if not phone or not pin:
        return jsonify({"error": "Missing information"}), 400

    connection = get_db()

    user = connection.execute(
        "SELECT * FROM users WHERE phone = ?", (phone,)
    ).fetchone()
    if user is None or not check_password_hash(user["pin_hash"], pin):
        connection.close()
        return jsonify({"error": "Phone number or PIN is incorrect"}), 401

    rental = connection.execute(
        "SELECT rentals.*, lockers.locker_number, lockers.id AS locker_id "
        "FROM rentals JOIN lockers ON rentals.locker_id = lockers.id "
        "WHERE rentals.user_id = ? AND rentals.status = 'active'",
        (user["id"],),
    ).fetchone()

    if rental is None:
        connection.close()
        return jsonify({"error": "No active rental found"}), 404

    end_time = datetime.fromisoformat(rental["end_time"])
    now = datetime.now()

    if now >= end_time:
        connection.execute(
            "UPDATE rentals SET status = 'expired' WHERE id = ?", (rental["id"],)
        )
        connection.commit()
        connection.close()
        return jsonify({"error": "Rental expired", "expired_at": rental["end_time"]}), 410

    minutes_left = int((end_time - now).total_seconds() // 60)
    connection.execute(
        "UPDATE lockers SET lock_status = 'unlocked' WHERE id = ?",
        (rental["locker_id"],),
    )
    connection.commit()
    connection.close()

    return jsonify({
        "locker_number": rental["locker_number"],
        "minutes_remaining": minutes_left,
        "end_time": rental["end_time"],
    })


@app.route("/extend-rental", methods=["POST"])
def extend_rental():
    data = request.get_json()
    phone = data.get("phone")
    pin = data.get("pin")
    duration = data.get("duration")
    card_uid = data.get("card_uid")

    if not phone or not pin or not duration or not card_uid:
        return jsonify({"error": "Missing information"}), 400
    if duration not in PRICES:
        return jsonify({"error": "Invalid duration"}), 400

    connection = get_db()
    user = connection.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
    if user is None or not check_password_hash(user["pin_hash"], pin):
        connection.close()
        return jsonify({"error": "Phone number or PIN is incorrect"}), 401

    rental = connection.execute(
        "SELECT * FROM rentals WHERE user_id = ? AND status = 'active'", (user["id"],)
    ).fetchone()
    if rental is None:
        connection.close()
        return jsonify({"error": "No active rental found"}), 404

    end_time = datetime.fromisoformat(rental["end_time"])
    if datetime.now() >= end_time:
        connection.execute("UPDATE rentals SET status = 'expired' WHERE id = ?", (rental["id"],))
        connection.commit()
        connection.close()
        return jsonify({"error": "Rental already expired, cannot extend"}), 410

    price = PRICES[duration]
    card = connection.execute("SELECT * FROM demo_cards WHERE card_uid = ?", (card_uid,)).fetchone()
    if card is None:
        connection.close()
        return jsonify({"error": "Card not recognized"}), 404
    if card["balance"] < price:
        connection.close()
        return jsonify({"error": "Not enough balance"}), 402

    new_end = end_time + timedelta(minutes=MINUTES[duration])
    connection.execute(
        "UPDATE demo_cards SET balance = balance - ? WHERE card_uid = ?", (price, card_uid)
    )
    connection.execute(
        "UPDATE rentals SET end_time = ?, amount_paid = amount_paid + ? WHERE id = ?",
        (new_end.isoformat(), price, rental["id"]),
    )
    connection.commit()
    connection.close()

    return jsonify({
        "new_end_time": new_end.isoformat(),
        "amount_charged": price,
        "new_balance": card["balance"] - price,
    })


@app.route("/end-rental", methods=["POST"])
def end_rental():
    data = request.get_json()
    phone = data.get("phone")
    pin = data.get("pin")

    if not phone or not pin:
        return jsonify({"error": "Missing information"}), 400

    connection = get_db()
    user = connection.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
    if user is None or not check_password_hash(user["pin_hash"], pin):
        connection.close()
        return jsonify({"error": "Phone number or PIN is incorrect"}), 401

    rental = connection.execute(
        "SELECT * FROM rentals WHERE user_id = ? AND status = 'active'", (user["id"],)
    ).fetchone()
    if rental is None:
        connection.close()
        return jsonify({"error": "No active rental found"}), 404

    connection.execute("UPDATE rentals SET status = 'ended' WHERE id = ?", (rental["id"],))
    connection.execute(
        "UPDATE lockers SET status = 'available', lock_status = 'locked' WHERE id = ?",
        (rental["locker_id"],),
    )
    connection.commit()
    connection.close()

    return jsonify({"message": "Rental ended. Locker is now locked and available."})


@app.route("/door-status", methods=["POST"])
def door_status():
    data = request.get_json()
    locker_number = data.get("locker_number")
    door_status_value = data.get("door_status")

    if locker_number is None or door_status_value not in ("open", "closed"):
        return jsonify({"error": "Invalid request"}), 400

    connection = get_db()
    locker = get_locker_by_number(connection, locker_number)
    if locker is None:
        connection.close()
        return jsonify({"error": "Locker not found"}), 404

    connection.execute(
        "UPDATE lockers SET door_status = ? WHERE id = ?", (door_status_value, locker["id"])
    )

    if door_status_value == "closed" and locker["lock_status"] == "unlocked":
        connection.execute(
            "UPDATE lockers SET lock_status = 'locked' WHERE id = ?", (locker["id"],)
        )

    connection.commit()
    connection.close()
    return jsonify({"message": f"Locker {locker_number} door is now {door_status_value}"})


@app.route("/forgot-pin", methods=["POST"])
def forgot_pin():
    data = request.get_json()
    phone = data.get("phone")
    if not phone:
        return jsonify({"error": "Missing phone number"}), 400
    return jsonify({"message": "Please contact the administrator for help resetting your PIN."})


@app.route("/admin/lockers")
def admin_lockers():
    admin_pin = request.args.get("admin_pin")
    if admin_pin != ADMIN_PIN:
        return jsonify({"error": "Invalid admin PIN"}), 401

    connection = get_db()
    rows = connection.execute(
        "SELECT lockers.*, rentals.id AS rental_id, rentals.end_time, "
        "users.name, users.phone "
        "FROM lockers "
        "LEFT JOIN rentals ON rentals.locker_id = lockers.id AND rentals.status = 'active' "
        "LEFT JOIN users ON users.id = rentals.user_id"
    ).fetchall()
    connection.close()
    return jsonify([dict(row) for row in rows])


@app.route("/admin/unlock", methods=["POST"])
def admin_unlock():
    data = request.get_json()
    admin_pin = data.get("admin_pin")
    locker_number = data.get("locker_number")

    if admin_pin != ADMIN_PIN:
        return jsonify({"error": "Invalid admin PIN"}), 401
    if locker_number is None:
        return jsonify({"error": "Missing locker_number"}), 400

    connection = get_db()
    locker = get_locker_by_number(connection, locker_number)
    if locker is None:
        connection.close()
        return jsonify({"error": "Locker not found"}), 404

    connection.execute(
        "UPDATE lockers SET lock_status = 'unlocked' WHERE id = ?", (locker["id"],)
    )
    connection.commit()
    connection.close()
    return jsonify({"message": f"Locker {locker_number} unlocked by admin"})


@app.route("/admin/end-rental", methods=["POST"])
def admin_end_rental():
    data = request.get_json()
    admin_pin = data.get("admin_pin")
    locker_number = data.get("locker_number")

    if admin_pin != ADMIN_PIN:
        return jsonify({"error": "Invalid admin PIN"}), 401
    if locker_number is None:
        return jsonify({"error": "Missing locker_number"}), 400

    connection = get_db()
    locker = get_locker_by_number(connection, locker_number)
    if locker is None:
        connection.close()
        return jsonify({"error": "Locker not found"}), 404

    rental = connection.execute(
        "SELECT * FROM rentals WHERE locker_id = ? AND status = 'active'", (locker["id"],)
    ).fetchone()
    if rental is None:
        connection.close()
        return jsonify({"error": "No active rental on this locker"}), 404

    connection.execute("UPDATE rentals SET status = 'ended' WHERE id = ?", (rental["id"],))
    connection.execute(
        "UPDATE lockers SET status = 'available', lock_status = 'locked' WHERE id = ?",
        (locker["id"],),
    )
    connection.commit()
    connection.close()
    return jsonify({"message": f"Rental on locker {locker_number} ended by admin"})


if __name__ == "__main__":
    app.run(debug=True)