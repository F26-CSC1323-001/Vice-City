import requests

# adds one more hour to the current rental
response = requests.post(
    "http://127.0.0.1:5000/extend-rental",
    json={
        "phone": "3185551234",
        "pin": "1234",
        "duration": "1hour",
        "card_uid": "CARD001"
    }
)

print(response.status_code)
print(response.json())