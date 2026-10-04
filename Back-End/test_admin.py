import requests

BASE = "http://127.0.0.1:5000"


# shows all lockers from the admin side
print(
    requests.get(
        f"{BASE}/admin/lockers",
        params={"admin_pin": "9999"}
    ).json()
)


# admin unlocks locker 1
print(
    requests.post(
        f"{BASE}/admin/unlock",
        json={
            "admin_pin": "9999",
            "locker_number": 1
        }
    ).json()
)


# pretends the door sensor says the door closed
print(
    requests.post(
        f"{BASE}/door-status",
        json={
            "locker_number": 1,
            "door_status": "closed"
        }
    ).json()
)