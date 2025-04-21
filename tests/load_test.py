import requests
import threading
import time
import random

BASE_URL = "http://localhost:8000/api/v1"


def create_notification(user_id):
    notification_type = random.choice(["shipment", "delivery", "payment"])
    channel = random.choice(["email", "push", "sms", "dashboard"])

    start_time = time.time()
    response = requests.post(f"{BASE_URL}/notifications/", json={
        "user_id": user_id,
        "type": notification_type,
        "channel": channel,
        "title": f"Load Test Notification",
        "content": "This is a load test notification."
    })
    elapsed = time.time() - start_time

    return {
        "status_code": response.status_code,
        "response_time": elapsed,
        "success": response.status_code == 200
    }


def worker(user_id, results):
    result = create_notification(user_id)
    results.append(result)


def run_load_test(concurrent_users=50):
    threads = []
    results = []

    for i in range(concurrent_users):
        # Assuming we have users with IDs 1-20 from dummy data
        user_id = (i % 20) + 1
        t = threading.Thread(target=worker, args=(user_id, results))
        threads.append(t)

    start_time = time.time()

    # Start all threads
    for t in threads:
        t.start()

    # Wait for all threads to complete
    for t in threads:
        t.join()

    elapsed = time.time() - start_time

    # Calculate statistics
    success_count = sum(1 for r in results if r["success"])
    avg_response_time = sum(r["response_time"] for r in results) / len(results)

    print(f"Load test results for {concurrent_users} concurrent users:")
    print(f"Total time: {elapsed:.2f} seconds")
    print(f"Success rate: {success_count}/{len(results)} ({success_count / len(results) * 100:.1f}%)")
    print(f"Average response time: {avg_response_time * 1000:.2f} ms")


if __name__ == "__main__":
    print("Starting load test...")
    run_load_test(50)  # Test with 50 concurrent users