import requests
import random
import time

BASE_URL = "http://localhost:8000/api/v1"

# Create 3 test users
user_ids = []
for i in range(3):
    response = requests.post(f"{BASE_URL}/users/", json={
        "email": f"systemtest{i}@example.com",
        "username": f"systemtest{i}",
        "password": "password123"
    })
    if response.status_code == 200:
        user_ids.append(response.json()["id"])

# Create 5 notifications per user across different channels
for user_id in user_ids:
    for _ in range(5):
        notification_type = random.choice(["shipment", "delivery", "payment"])
        channel = random.choice(["email", "push", "sms", "dashboard"])

        response = requests.post(f"{BASE_URL}/notifications/", json={
            "user_id": user_id,
            "type": notification_type,
            "channel": channel,
            "title": f"Test {notification_type} notification",
            "content": "This is a test notification content"
        })

        # Wait a bit to space out notifications
        time.sleep(0.5)

print("Test data generation complete")