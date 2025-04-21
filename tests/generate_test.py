# save as system_test.py
import requests
import random
import time
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"


def create_test_user(idx):
    response = requests.post(f"{BASE_URL}/users/", json={
        "email": f"system_test{idx}@example.com",
        "username": f"system_test{idx}",
        "password": "testpassword"
    })
    if response.status_code == 200:
        return response.json()["id"]
    print(f"Failed to create user: {response.text}")
    return None


def create_notifications(user_id, count=5):
    notifications = []
    for i in range(count):
        notification_type = random.choice(["shipment", "delivery", "payment", "order_confirmation"])
        channel = random.choice(["email", "push", "sms", "dashboard"])

        response = requests.post(f"{BASE_URL}/notifications/", json={
            "user_id": user_id,
            "type": notification_type,
            "channel": channel,
            "title": f"Test {notification_type.title()} {i + 1}",
            "content": f"This is test notification #{i + 1} of type {notification_type} via {channel}."
        })

        if response.status_code == 200:
            notifications.append(response.json())

        # Give the system time to process
        time.sleep(1)

    return notifications


def simulate_engagements(notifications, engagement_pattern="high"):
    """
    Simulates user engagement with notifications.
    engagement_pattern can be:
    - "high": often opens and clicks
    - "medium": sometimes opens, occasionally clicks
    - "low": rarely opens, almost never clicks
    """
    for notification in notifications:
        # Determine engagement probabilities based on pattern
        if engagement_pattern == "high":
            open_probability = 0.9
            click_probability = 0.7
        elif engagement_pattern == "medium":
            open_probability = 0.6
            click_probability = 0.3
        else:  # low
            open_probability = 0.3
            click_probability = 0.1

        # Simulate open
        if random.random() < open_probability:
            requests.post(f"{BASE_URL}/engagements/", json={
                "notification_id": notification["id"],
                "action": "open"
            })
            print(f"Opened notification {notification['id']}")

            # Simulate click (only if opened)
            if random.random() < click_probability:
                time.sleep(random.uniform(1, 3))  # Random delay
                requests.post(f"{BASE_URL}/engagements/", json={
                    "notification_id": notification["id"],
                    "action": "click"
                })
                print(f"Clicked notification {notification['id']}")

        # Give the system time to process
        time.sleep(1)


def main():
    # Create users with different engagement patterns
    user_configs = [
        {"pattern": "high", "count": 1},
        {"pattern": "medium", "count": 1},
        {"pattern": "low", "count": 1}
    ]

    for config in user_configs:
        pattern = config["pattern"]
        for i in range(config["count"]):
            print(f"Testing {pattern} engagement pattern (user {i + 1})...")

            # Create user
            user_id = create_test_user(f"{pattern}_{i}")
            if not user_id:
                continue

            # Create notifications
            notifications = create_notifications(user_id, count=5)

            # Wait for processing
            print("Waiting for notification processing...")
            time.sleep(5)

            # Simulate engagements
            simulate_engagements(notifications, pattern)

            print(f"Completed testing for {pattern} engagement pattern (user {i + 1})")
            print("-" * 50)

    print("System test complete!")


if __name__ == "__main__":
    main()