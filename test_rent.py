import requests

# sends a fake rental request
response = requests.post(
    "http://127.0.0.1:5000/rent",
    json={
        "name": "Test User",
        "phone": "3185551234",
        "pin": "1234",
        "duration": "2hours",
        "card_uid": "CARD001"
    }
)

# shows what the server sends back
print(response.status_code)
print(response.json())