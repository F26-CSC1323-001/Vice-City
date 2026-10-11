import sqlite3
from datetime import datetime, timedelta

from flask import Flask, jsonify, request
from flask import Flask, render_template, jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, static_url_path="")


# prices for each rental option
PRICES = {
    "30min": 2.00,
    "1hour": 3.00,
    "2hours": 5.00,
    "4hours": 8.00,
    "allday": 12.00
}


# how many minutes each option lasts
MINUTES = {
    "30min": 30,
    "1hour": 60,
    "2hours": 120,
    "4hours": 240,
    "allday": 1440
}


# temporary admin pin for the prototype
ADMIN_PIN = "9999"


# opens the database
def get_db():
    connection = sqlite3.connect("locker.db")
    connection.row_factory = sqlite3.Row
    return connection


# finds a locker using its locker number
def get_locker_by_number(connection, locker_number):
    return connection.execute(
        "SELECT * FROM lockers WHERE locker_number = ?",
        (locker_number,)
    ).fetchone()


# shows the front end (index.html inside the "static" folder)
@app.route("/")
def home():
    return render_template("index.html")


# returns the current information for all lockers
@app.route("/lockers")
def list_lockers():
    connection = get_db()

    # also includes end_time when the locker is being rented
    rows = connection.execute(
        """
        SELECT lockers.*, rentals.end_time
        FROM lockers
        LEFT JOIN rentals
        ON rentals.locker_id = lockers.id
        AND rentals.status IN ('active', 'expired')
        """
    ).fetchall()

    connection.close()

    return jsonify([dict(row) for row in rows])


# creates a new locker rental
@app.route("/rent", methods=["POST"])
def rent():
    data = request.get_json()

    name = data.get("name")
    phone = data.get("phone")
    pin = data.get("pin")
    duration = data.get("duration")
    card_uid = data.get("card_uid")


    # checks that nothing was left blank
    if not name or not phone or not pin or not duration or not card_uid:
        return jsonify({"error": "Missing information"}), 400


    # pin has to be between 4 and 6 numbers
    if not (pin.isdigit() and 4 <= len(pin) <= 6):
        return jsonify({"error": "PIN must be 4 to 6 digits"}), 400


    # makes sure the rental option exists
    if duration not in PRICES:
        return jsonify({"error": "Invalid duration"}), 400


    price = PRICES[duration]
    connection = get_db()


    # checks if the card exists
    card = connection.execute(
        "SELECT * FROM demo_cards WHERE card_uid = ?",
        (card_uid,)
    ).fetchone()


    if card is None:
        connection.close()
        return jsonify({"error": "Card not recognized"}), 404


    # checks the card balance
    if card["balance"] < price:
        connection.close()
        return jsonify({"error": "Not enough balance"}), 402


    # uses the locker the customer picked (if one was sent), otherwise the first free one
    locker_number = data.get("locker_number")

    if locker_number is not None:
        locker = connection.execute(
            "SELECT * FROM lockers WHERE status = 'available' AND locker_number = ?",
            (locker_number,)
        ).fetchone()
    else:
        locker = connection.execute(
            "SELECT * FROM lockers WHERE status = 'available' LIMIT 1"
        ).fetchone()


    if locker is None:
        connection.close()

        if locker_number is not None:
            return jsonify({"error": "That locker is no longer available"}), 409

        return jsonify({"error": "No lockers available"}), 409


    # checks whether this phone number is already in the system
    user = connection.execute(
        "SELECT * FROM users WHERE phone = ?",
        (phone,)
    ).fetchone()


    # stores the pin as a hash instead of plain text
    pin_hash = generate_password_hash(pin)


    if user is None:

        # creates a new user
        cursor = connection.execute(
            "INSERT INTO users (name, phone, pin_hash) VALUES (?, ?, ?)",
            (name, phone, pin_hash)
        )

        user_id = cursor.lastrowid

    else:
        user_id = user["id"]


        # prevents someone from having two active rentals
        active = connection.execute(
            "SELECT id FROM rentals WHERE user_id = ? AND status = 'active'",
            (user_id,)
        ).fetchone()


        if active:
            connection.close()

            return jsonify({
                "error": "This phone number already has an active rental"
            }), 409


        # updates their name and pin if they have rented before
        connection.execute(
            "UPDATE users SET name = ?, pin_hash = ? WHERE id = ?",
            (name, pin_hash, user_id)
        )


    # works out the start and end time
    start = datetime.now()
    end = start + timedelta(minutes=MINUTES[duration])


    # charges the demo card
    connection.execute(
        "UPDATE demo_cards SET balance = balance - ? WHERE card_uid = ?",
        (price, card_uid)
    )


    # saves the rental
    connection.execute(
        """
        INSERT INTO rentals
        (user_id, locker_id, start_time, end_time, amount_paid)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            user_id,
            locker["id"],
            start.isoformat(),
            end.isoformat(),
            price
        )
    )


    # marks the locker as being used and unlocked
    connection.execute(
        """
        UPDATE lockers
        SET status = 'occupied', lock_status = 'unlocked'
        WHERE id = ?
        """,
        (locker["id"],)
    )


    connection.commit()
    connection.close()


    return jsonify({
        "locker_number": locker["locker_number"],
        "end_time": end.isoformat(),
        "amount_paid": price,
        "new_balance": card["balance"] - price
    })


# lets a user get back into their locker
@app.route("/open-locker", methods=["POST"])
def open_locker():
    data = request.get_json()

    phone = data.get("phone")
    pin = data.get("pin")


    if not phone or not pin:
        return jsonify({"error": "Missing information"}), 400


    connection = get_db()


    # finds the user using their phone number
    user = connection.execute(
        "SELECT * FROM users WHERE phone = ?",
        (phone,)
    ).fetchone()


    # checks that the phone and pin match
    if user is None or not check_password_hash(user["pin_hash"], pin):
        connection.close()

        return jsonify({
            "error": "Phone number or PIN is incorrect"
        }), 401


    # gets their active rental and locker
    rental = connection.execute(
        """
        SELECT rentals.*, lockers.locker_number,
        lockers.id AS locker_id
        FROM rentals
        JOIN lockers ON rentals.locker_id = lockers.id
        WHERE rentals.user_id = ?
        AND rentals.status = 'active'
        """,
        (user["id"],)
    ).fetchone()


    if rental is None:
        connection.close()

        return jsonify({
            "error": "No active rental found"
        }), 404


    end_time = datetime.fromisoformat(rental["end_time"])
    now = datetime.now()


    # stops access if the rental already expired
    if now >= end_time:

        connection.execute(
            "UPDATE rentals SET status = 'expired' WHERE id = ?",
            (rental["id"],)
        )

        connection.commit()
        connection.close()

        return jsonify({
            "error": "Rental expired",
            "expired_at": rental["end_time"]
        }), 410


    # works out how much time is left
    minutes_left = int(
        (end_time - now).total_seconds() // 60
    )


    # unlocks the locker in the database for now
    connection.execute(
        "UPDATE lockers SET lock_status = 'unlocked' WHERE id = ?",
        (rental["locker_id"],)
    )


    connection.commit()
    connection.close()


    return jsonify({
        "locker_number": rental["locker_number"],
        "minutes_remaining": minutes_left,
        "end_time": rental["end_time"]
    })


# adds more time to an active rental
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


    # checks the user and pin
    user = connection.execute(
        "SELECT * FROM users WHERE phone = ?",
        (phone,)
    ).fetchone()


    if user is None or not check_password_hash(user["pin_hash"], pin):
        connection.close()
        return jsonify({"error": "Phone number or PIN is incorrect"}), 401


    # finds the user's current rental
    rental = connection.execute(
        "SELECT * FROM rentals WHERE user_id = ? AND status = 'active'",
        (user["id"],)
    ).fetchone()


    if rental is None:
        connection.close()
        return jsonify({"error": "No active rental found"}), 404


    end_time = datetime.fromisoformat(rental["end_time"])


    # expired rentals cannot be extended
    if datetime.now() >= end_time:

        connection.execute(
            "UPDATE rentals SET status = 'expired' WHERE id = ?",
            (rental["id"],)
        )

        connection.commit()
        connection.close()

        return jsonify({
            "error": "Rental already expired, cannot extend"
        }), 410


    price = PRICES[duration]


    # checks the card again before charging it
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


    # adds the new time onto the current end time
    new_end = end_time + timedelta(
        minutes=MINUTES[duration]
    )


    # charges the card
    connection.execute(
        "UPDATE demo_cards SET balance = balance - ? WHERE card_uid = ?",
        (price, card_uid)
    )


    # updates the rental time and total amount paid
    connection.execute(
        """
        UPDATE rentals
        SET end_time = ?, amount_paid = amount_paid + ?
        WHERE id = ?
        """,
        (new_end.isoformat(), price, rental["id"])
    )


    connection.commit()
    connection.close()


    return jsonify({
        "new_end_time": new_end.isoformat(),
        "amount_charged": price,
        "new_balance": card["balance"] - price
    })


# ends a rental early
@app.route("/end-rental", methods=["POST"])
def end_rental():
    data = request.get_json()

    phone = data.get("phone")
    pin = data.get("pin")


    if not phone or not pin:
        return jsonify({"error": "Missing information"}), 400


    connection = get_db()


    # checks the user and pin
    user = connection.execute(
        "SELECT * FROM users WHERE phone = ?",
        (phone,)
    ).fetchone()


    if user is None or not check_password_hash(user["pin_hash"], pin):
        connection.close()
        return jsonify({"error": "Phone number or PIN is incorrect"}), 401


    # finds the active rental
    rental = connection.execute(
        "SELECT * FROM rentals WHERE user_id = ? AND status = 'active'",
        (user["id"],)
    ).fetchone()


    if rental is None:
        connection.close()
        return jsonify({"error": "No active rental found"}), 404


    # marks the rental as ended
    connection.execute(
        "UPDATE rentals SET status = 'ended' WHERE id = ?",
        (rental["id"],)
    )


    # frees the locker for the next person
    connection.execute(
        """
        UPDATE lockers
        SET status = 'available', lock_status = 'locked'
        WHERE id = ?
        """,
        (rental["locker_id"],)
    )


    connection.commit()
    connection.close()


    return jsonify({
        "message": "Rental ended. Locker is now locked and available."
    })


# updates whether a locker door is open or closed
@app.route("/door-status", methods=["POST"])
def door_status():
    data = request.get_json()

    locker_number = data.get("locker_number")
    door_status_value = data.get("door_status")


    # only open or closed are allowed
    if locker_number is None or door_status_value not in ("open", "closed"):
        return jsonify({"error": "Invalid request"}), 400


    connection = get_db()

    locker = get_locker_by_number(
        connection,
        locker_number
    )


    if locker is None:
        connection.close()
        return jsonify({"error": "Locker not found"}), 404


    # updates the door status
    connection.execute(
        "UPDATE lockers SET door_status = ? WHERE id = ?",
        (door_status_value, locker["id"])
    )


    # if the door closes while unlocked, lock it again
    if door_status_value == "closed" and locker["lock_status"] == "unlocked":

        connection.execute(
            "UPDATE lockers SET lock_status = 'locked' WHERE id = ?",
            (locker["id"],)
        )


    connection.commit()
    connection.close()


    return jsonify({
        "message": f"Locker {locker_number} door is now {door_status_value}"
    })


# gives instructions if someone forgets their pin
@app.route("/forgot-pin", methods=["POST"])
def forgot_pin():
    data = request.get_json()

    phone = data.get("phone")


    if not phone:
        return jsonify({"error": "Missing phone number"}), 400


    return jsonify({
        "message": "Please contact the administrator for help resetting your PIN."
    })


# lets the admin see every locker
@app.route("/admin/lockers")
def admin_lockers():
    admin_pin = request.args.get("admin_pin")


    if admin_pin != ADMIN_PIN:
        return jsonify({"error": "Invalid admin PIN"}), 401


    connection = get_db()


    # also shows rental and user info if the locker is being used
    rows = connection.execute(
        """
        SELECT lockers.*,
        rentals.id AS rental_id,
        rentals.end_time,
        users.name,
        users.phone
        FROM lockers
        LEFT JOIN rentals
        ON rentals.locker_id = lockers.id
        AND rentals.status IN ('active', 'expired')
        LEFT JOIN users
        ON users.id = rentals.user_id
        """
    ).fetchall()


    connection.close()

    return jsonify([dict(row) for row in rows])


# lets the admin unlock any locker
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

    locker = get_locker_by_number(
        connection,
        locker_number
    )


    if locker is None:
        connection.close()
        return jsonify({"error": "Locker not found"}), 404


    # unlocks the selected locker
    connection.execute(
        "UPDATE lockers SET lock_status = 'unlocked' WHERE id = ?",
        (locker["id"],)
    )


    connection.commit()
    connection.close()


    return jsonify({
        "message": f"Locker {locker_number} unlocked by admin"
    })


# lets the admin force-end a rental
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

    locker = get_locker_by_number(
        connection,
        locker_number
    )


    if locker is None:
        connection.close()
        return jsonify({"error": "Locker not found"}), 404


    # checks if the locker currently has a rental
    rental = connection.execute(
        """
        SELECT * FROM rentals
        WHERE locker_id = ?
        AND status IN ('active', 'expired')
        """,
        (locker["id"],)
    ).fetchone()


    if rental is None:
        connection.close()

        return jsonify({
            "error": "No active rental on this locker"
        }), 404


    # ends the rental
    connection.execute(
        "UPDATE rentals SET status = 'ended' WHERE id = ?",
        (rental["id"],)
    )


    # resets the locker
    connection.execute(
        """
        UPDATE lockers
        SET status = 'available', lock_status = 'locked'
        WHERE id = ?
        """,
        (locker["id"],)
    )


    connection.commit()
    connection.close()


    return jsonify({
        "message": f"Rental on locker {locker_number} ended by admin"
    })


# lets the admin take a locker out of service
@app.route("/admin/disable", methods=["POST"])
def admin_disable():
    data = request.get_json()

    admin_pin = data.get("admin_pin")
    locker_number = data.get("locker_number")


    if admin_pin != ADMIN_PIN:
        return jsonify({"error": "Invalid admin PIN"}), 401


    if locker_number is None:
        return jsonify({"error": "Missing locker_number"}), 400


    connection = get_db()

    locker = get_locker_by_number(
        connection,
        locker_number
    )


    if locker is None:
        connection.close()
        return jsonify({"error": "Locker not found"}), 404


    # a locker that is being rented cannot be disabled
    if locker["status"] == "occupied":
        connection.close()
        return jsonify({"error": "Locker is being rented"}), 409


    # disabled lockers are locked and nobody can rent them
    connection.execute(
        "UPDATE lockers SET status = 'disabled', lock_status = 'locked' WHERE id = ?",
        (locker["id"],)
    )


    connection.commit()
    connection.close()


    return jsonify({
        "message": f"Locker {locker_number} disabled by admin"
    })


# lets the admin put a disabled locker back in service
@app.route("/admin/enable", methods=["POST"])
def admin_enable():
    data = request.get_json()

    admin_pin = data.get("admin_pin")
    locker_number = data.get("locker_number")


    if admin_pin != ADMIN_PIN:
        return jsonify({"error": "Invalid admin PIN"}), 401


    if locker_number is None:
        return jsonify({"error": "Missing locker_number"}), 400


    connection = get_db()

    locker = get_locker_by_number(
        connection,
        locker_number
    )


    if locker is None:
        connection.close()
        return jsonify({"error": "Locker not found"}), 404


    if locker["status"] != "disabled":
        connection.close()
        return jsonify({"error": "Locker is not disabled"}), 409


    connection.execute(
        "UPDATE lockers SET status = 'available' WHERE id = ?",
        (locker["id"],)
    )


    connection.commit()
    connection.close()


    return jsonify({
        "message": f"Locker {locker_number} enabled by admin"
    })


# starts the server
if __name__ == "__main__":
    app.run(debug=True)