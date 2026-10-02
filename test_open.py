import requests

response = requests.post("http://127.0.0.1:5000/open-locker", json={
    "phone": "3185551234",
    "pin": "1234",
})

print(response.status_code)
print(response.json())