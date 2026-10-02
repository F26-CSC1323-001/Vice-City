import requests

BASE = "http://127.0.0.1:5000"

print(
    requests.get(
        f"{BASE}/admin/lockers",
        params={"admin_pin": "9999"}
    ).json()
)

print(
    requests.post(
        f"{BASE}/admin/unlock",
        json={
            "admin_pin": "9999",
            "locker_number": 1
        }
    ).json()
)

print(
    requests.post(
        f"{BASE}/door-status",
        json={
            "locker_number": 1,
            "door_status": "closed"
        }
    ).json()
)