# recommendation_flow_test.py

import requests
import time
import json
from pymongo import MongoClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import random
from config.config import Config
from app.agents.data_collection.dashboard_tracker import DashboardTrackerAgent
from app.agents.data_collection.email_engagement import EmailEngagementAgent
from app.agents.data_collection.mobile_app_events import MobileAppEventsAgent
from app.agents.data_collection.sms_interaction import SMSInteractionAgent
from app.agents.analysis.frequency_analysis import FrequencyAnalysisAgent
from app.agents.analysis.type_analysis import TypeAnalysisAgent
from app.agents.analysis.channel_analysis import ChannelAnalysisAgent
from app.agents.decision_engine.user_profile import UserProfileAgent
from app.agents.decision_engine.recommendation import RecommendationAgent
from app.agents.decision_engine.ab_testing import ABTestingAgent
from app.agents.notification.email_service import EmailServiceAgent
from app.agents.notification.push_notification import PushNotificationAgent
from app.agents.notification.sms_gateway import SMSGatewayAgent
from app.agents.notification.dashboard_alert import DashboardAlertAgent
import logging

API_URL = "http://localhost:8000/api/v1"
MONGODB_URL = Config.MONGODB_URL
POSTGRES_URL = Config.DATABASE_URL


def run_agents():
    agents = [
        # Data Collection Layer
        DashboardTrackerAgent(),
        EmailEngagementAgent(),
        MobileAppEventsAgent(),
        SMSInteractionAgent(),

        # Analysis Layer
        FrequencyAnalysisAgent(),
        TypeAnalysisAgent(),
        ChannelAnalysisAgent(),

        # Decision Engine
        UserProfileAgent(),
        RecommendationAgent(),
        ABTestingAgent(),

        # Notification Management Layer
        EmailServiceAgent(),
        PushNotificationAgent(),
        SMSGatewayAgent(),
        DashboardAlertAgent(),
    ]
    for agent in agents:
        logging.info(agent, "is now processing...")
        agent.process()


def test_recommendation_flow():
    """Test the complete recommendation flow from data collection to notification delivery"""
    logging.info("\n===== TESTING SMART NOTIFICATION SYSTEM RECOMMENDATION FLOW =====\n")

    # Step 1: Create test users with different behavior patterns
    high_user_id = create_test_user("high_test", "high engagement pattern")
    medium_user_id = create_test_user("medium_test", "medium engagement pattern")
    low_user_id = create_test_user("low_test", "low engagement pattern")

    if not all([high_user_id, medium_user_id, low_user_id]):
        logging.info("❌ Failed to create test users")
        return

    # Step 2: Generate user behavior data for each user
    logging.info("\n----- Generating User Behavior Data -----")

    # High engagement user - many sessions, high click rates
    for _ in range(8):  # Create 8 sessions for high user
        simulate_user_session(high_user_id, page_count=10, click_probability=0.8)

    # Medium engagement user - moderate sessions, moderate click rates
    for _ in range(4):  # Create 4 sessions for medium user
        simulate_user_session(medium_user_id, page_count=5, click_probability=0.5)

    # Low engagement user - few sessions, low click rates
    for _ in range(1):  # Create 1 session for low user
        simulate_user_session(low_user_id, page_count=2, click_probability=0.2)

    # Step 3: Wait for data collection agents to process the data
    logging.info("\nWaiting for data collection agents to process user behavior data...")
    time.sleep(10)
    run_agents()

    # Step 4: Check if analysis agents have processed the data
    logging.info("\n----- Checking Analysis Agent Processing -----")
    """
    {'email_service', 'sms_gateway', 'frequency_analysis', 'user_profile', 'channel_analysis', 'push_notification',
     'email_engagement', 'dashboard_alert', 'recommendation', 'dashboard_tracker', 'sms_interaction', 'ab_testing',
     'type_analysis', 'mobile_app_events'}"""
    check_agent_logs(["frequency_analysis", "type_analysis", "channel_analysis"])

    # Step 5: Check if user profiles have been created/updated
    logging.info("\n----- Checking User Profiles -----")
    profiles = check_user_profiles([high_user_id, medium_user_id, low_user_id])

    if not profiles:
        logging.info("❌ User profiles not found. Waiting longer for profile generation...")
        time.sleep(120)
        profiles = check_user_profiles([high_user_id, medium_user_id, low_user_id])
        if not profiles:
            logging.info("❌ User profiles still not found after waiting. System may not be working correctly.")
            return

    # Step 6: Generate test notifications for each user
    logging.info("\n----- Creating Test Notifications -----")
    notification_ids = {}

    for user_id, label in [(high_user_id, "high"), (medium_user_id, "medium"), (low_user_id, "low")]:
        notification_id = create_test_notification(user_id, f"Test for {label} user")
        if notification_id:
            notification_ids[user_id] = notification_id

    # Step 7: Wait for recommendation system to process notifications
    logging.info("\nWaiting for recommendation system to process notifications...")
    run_agents()

    # Step 8: Check notification delivery decisions
    logging.info("\n----- Checking Notification Delivery Decisions -----")
    check_notification_delivery(notification_ids)

    # Step 9: Simulate engagement with notifications
    logging.info("\n----- Simulating User Engagement -----")
    for user_id, notification_id in notification_ids.items():
        # Determine engagement probability based on user type
        if user_id == high_user_id:
            simulate_notification_engagement(notification_id, open_prob=0.9, click_prob=0.7)
        elif user_id == medium_user_id:
            simulate_notification_engagement(notification_id, open_prob=0.6, click_prob=0.4)
        else:  # low user
            simulate_notification_engagement(notification_id, open_prob=0.3, click_prob=0.1)

    # Step 10: Wait for engagement data to be processed
    logging.info("\nWaiting for engagement data to be processed...")
    run_agents()

    # Step 11: Check if user profiles are updated with new engagement data
    logging.info("\n----- Checking Profile Updates After Engagement -----")
    updated_profiles = check_user_profiles([high_user_id, medium_user_id, low_user_id])

    # Step 12: Generate second round of notifications to see adaptation
    logging.info("\n----- Creating Second Round of Notifications -----")
    round2_notification_ids = {}

    for user_id, label in [(high_user_id, "high"), (medium_user_id, "medium"), (low_user_id, "low")]:
        notification_id = create_test_notification(user_id, f"Round 2 test for {label} user")
        if notification_id:
            round2_notification_ids[user_id] = notification_id

    # Step 13: Wait for recommendation system to process second round
    logging.info("\nWaiting for recommendation system to process second round...")
    run_agents()

    # Step 14: Check second round delivery decisions for adaptation
    logging.info("\n----- Checking Second Round Adaptation -----")
    check_notification_delivery(round2_notification_ids)

    # Step 15: Compare first and second round recommendations
    logging.info("\n----- Comparing Recommendations Between Rounds -----")
    compare_recommendations(notification_ids, round2_notification_ids)

    logging.info("\n===== RECOMMENDATION FLOW TEST COMPLETE =====\n")


def create_test_user(username_prefix, description):
    """Create a test user and return the user ID"""
    try:
        # Generate random suffix to avoid conflicts
        suffix = random.randint(1000, 9999)
        username = f"{username_prefix}_{suffix}"
        email = f"{username}@example.com"

        response = requests.post(f"{API_URL}/users/", json={
            "email": email,
            "username": username,
            "password": "testpassword"
        })

        if response.status_code == 200:
            user_id = response.json()["id"]
            logging.info(f"✅ Created test user: {username} (ID: {user_id}) - {description}")
            return user_id
        else:
            logging.info(f"❌ Failed to create user {username}: {response.text}")
            return None
    except Exception as e:
        logging.info(f"❌ Error creating test user: {str(e)}")
        return None


def simulate_user_session(user_id, page_count, click_probability):
    """Simulate a user browsing session with page views and clicks"""
    # This is a simplified simulation - in reality, you'd record actual sessions in your database

    # Create a user session via API or direct database entry
    engine = create_engine(POSTGRES_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Create user session
        session_start = datetime.utcnow() - timedelta(minutes=random.randint(5, 120))
        session_id = str(random.randint(10000, 99999))

        # Insert session directly to database
        session.execute(text(
            """
            INSERT INTO user_sessions (user_id, session_id, ip_address, user_agent, started_at, is_active)
            VALUES (:user_id, :session_id, :ip_address, :user_agent, :started_at, :is_active)
            RETURNING id
            """
        ), {
            "user_id": user_id,
            "session_id": session_id,
            "ip_address": f"192.168.1.{random.randint(1, 255)}",
            "user_agent": "Mozilla/5.0 Test Agent",
            "started_at": session_start,
            "is_active": False
        })

        db_session_id = session.execute(text(
            "SELECT id FROM user_sessions WHERE session_id = :session_id"
        ), {"session_id": session_id}).scalar()

        # Create page views
        for i in range(page_count):
            page_path = random.choice([
                "/dashboard",
                "/notifications",
                "/settings",
                "/profile",
                "/orders",
                "/shipments"
            ])

            # Insert page view
            session.execute(text(
                """
                INSERT INTO page_views (session_id, url, view_time, duration)
                VALUES (:session_id, :url, :view_time, :duration)
                """
            ), {
                "session_id": db_session_id,
                "url": page_path,
                "view_time": session_start + timedelta(minutes=i * 2),
                "duration": random.randint(10, 300)
            })

            # Simulate clicks based on probability
            if random.random() < click_probability:
                # Record click event (or some other engagement)
                pass

        session.commit()
        logging.info(f"✅ Simulated session for user {user_id} with {page_count} page views")

    except Exception as e:
        session.rollback()
        logging.info(f"❌ Error simulating session: {str(e)}")
    finally:
        session.close()


def check_agent_logs(agent_types):
    """Check if agents have been processing data"""
    try:
        client = MongoClient(MONGODB_URL)
        db = client.get_database()

        for agent_type in agent_types:
            recent_logs = list(db.agent_logs.find(
                {"agent_type": agent_type}
            ).sort("timestamp", -1).limit(1))

            if recent_logs:
                log = recent_logs[0]
                time_diff = datetime.utcnow() - log["timestamp"]
                minutes_ago = time_diff.total_seconds() / 60

                if minutes_ago < 10:
                    logging.info(f"✅ {agent_type} active - last action: {log['action']} ({minutes_ago:.1f} minutes ago)")
                else:
                    logging.info(f"⚠️ {agent_type} last active {minutes_ago:.1f} minutes ago")
            else:
                logging.info(f"❌ No logs found for {agent_type}")
    except Exception as e:
        logging.info(f"❌ Error checking agent logs: {str(e)}")


def check_user_profiles(user_ids):
    """Check if user profiles exist and return them"""
    try:
        client = MongoClient(MONGODB_URL)
        db = client.get_database()

        profiles = {}
        for user_id in user_ids:
            profile = db.user_profiles.find_one({"user_id": user_id})

            if profile:
                profile_age = datetime.utcnow() - profile.get("last_updated", datetime.min)
                minutes_ago = profile_age.total_seconds() / 60

                # Check profile components
                has_frequency = "frequency_preferences" in profile and profile["frequency_preferences"]
                has_channel = "channel_preferences" in profile and profile["channel_preferences"]
                has_content = "content_preferences" in profile and profile["content_preferences"]
                has_time = "time_preferences" in profile and profile["time_preferences"]

                components = [has_frequency, has_channel, has_content, has_time]
                completeness = sum(components) / len(components) * 100

                logging.info(
                    f"✅ User {user_id} profile found - {completeness:.0f}% complete, updated {minutes_ago:.1f} minutes ago")

                # Show some preferences if available
                if has_channel and "ranked_channels" in profile["channel_preferences"]:
                    ranked = profile["channel_preferences"]["ranked_channels"]
                    if ranked:
                        logging.info(f"  • Preferred channels: {', '.join(ranked[:2])}")

                profiles[user_id] = profile
            else:
                logging.info(f"❌ No profile found for user {user_id}")

        return profiles if profiles else None
    except Exception as e:
        logging.info(f"❌ Error checking user profiles: {str(e)}")
        return None


def create_test_notification(user_id, title_prefix):
    """Create a test notification and return its ID"""
    try:
        notification_type = random.choice(["shipment", "delivery", "payment", "order_confirmation"])
        channel = "default"  # Let the system decide the channel

        notification_data = {
            "user_id": user_id,
            "type": notification_type,
            "channel": channel,
            "title": f"{title_prefix} - {notification_type}",
            "content": f"This is a test notification to check recommendation flow."
        }

        response = requests.post(f"{API_URL}/notifications/", json=notification_data)

        if response.status_code == 200:
            notification_id = response.json()["id"]
            logging.info(f"✅ Created notification {notification_id} for user {user_id}")
            return notification_id
        else:
            logging.info(f"❌ Failed to create notification: {response.text}")
            return None
    except Exception as e:
        logging.info(f"❌ Error creating notification: {str(e)}")
        return None


def check_notification_delivery(notification_ids):
    """Check delivery status and decisions for notifications"""
    try:
        engine = create_engine(POSTGRES_URL)
        Session = sessionmaker(bind=engine)
        session = Session()

        for user_id, notification_id in notification_ids.items():
            # Check notification status
            result = session.execute(text(
                """
                SELECT n.is_sent, n.channel, n.sent_at, u.username
                FROM notifications n 
                JOIN users u ON n.user_id = u.id
                WHERE n.id = :notification_id
                """
            ), {"notification_id": notification_id}).fetchone()

            if result:
                is_sent, channel, sent_at, username = result

                if is_sent:
                    delivery_time = sent_at.strftime("%H:%M:%S") if sent_at else "N/A"
                    logging.info(f"✅ Notification {notification_id} for {username} (ID: {user_id}):")
                    logging.info(f"  • Delivery decision: SEND via {channel}")
                    logging.info(f"  • Delivery time: {delivery_time}")
                else:
                    logging.info(f"⚠️ Notification {notification_id} for user {user_id} not sent yet")
            else:
                logging.info(f"❌ Notification {notification_id} not found")

        session.close()
    except Exception as e:
        logging.info(f"❌ Error checking notification delivery: {str(e)}")


def simulate_notification_engagement(notification_id, open_prob, click_prob):
    """Simulate user engagement with a notification"""
    try:
        # Decide whether to open based on probability
        if random.random() < open_prob:
            # Record open engagement
            requests.post(f"{API_URL}/engagements/", json={
                "notification_id": notification_id,
                "action": "open"
            })
            logging.info(f"✅ Simulated 'open' action for notification {notification_id}")

            # Decide whether to click based on probability
            if random.random() < click_prob:
                time.sleep(2)  # Small delay between open and click

                # Record click engagement
                requests.post(f"{API_URL}/engagements/", json={
                    "notification_id": notification_id,
                    "action": "click"
                })
                logging.info(f"✅ Simulated 'click' action for notification {notification_id}")
        else:
            logging.info(f"ℹ️ No engagement simulated for notification {notification_id}")
    except Exception as e:
        logging.info(f"❌ Error simulating engagement: {str(e)}")


def compare_recommendations(round1_notifications, round2_notifications):
    """Compare recommendations between rounds to see adaptation"""
    try:
        engine = create_engine(POSTGRES_URL)
        Session = sessionmaker(bind=engine)
        session = Session()

        logging.info("\nComparing notification decisions between rounds:")

        for user_id in round1_notifications.keys():
            if user_id not in round2_notifications:
                continue

            # Get details for both rounds
            round1_details = session.execute(text(
                """
                SELECT n.channel, n.sent_at, u.username
                FROM notifications n 
                JOIN users u ON n.user_id = u.id
                WHERE n.id = :notification_id
                """
            ), {"notification_id": round1_notifications[user_id]}).fetchone()

            round2_details = session.execute(text(
                """
                SELECT n.channel, n.sent_at, u.username
                FROM notifications n 
                JOIN users u ON n.user_id = u.id
                WHERE n.id = :notification_id
                """
            ), {"notification_id": round2_notifications[user_id]}).fetchone()

            if round1_details and round2_details:
                r1_channel, r1_time, username = round1_details
                r2_channel, r2_time, _ = round2_details

                # Extract user type from username
                user_type = "unknown"
                if "high" in username.lower():
                    user_type = "HIGH activity"
                elif "medium" in username.lower():
                    user_type = "MEDIUM activity"
                elif "low" in username.lower():
                    user_type = "LOW activity"

                logging.info(f"\n{user_type} user ({username}, ID: {user_id}):")
                logging.info(f"  • Round 1: Channel = {r1_channel}")
                logging.info(f"  • Round 2: Channel = {r2_channel}")

                if r1_channel != r2_channel:
                    logging.info(f"  ✅ ADAPTATION DETECTED: Channel changed from {r1_channel} to {r2_channel}")
                else:
                    logging.info(f"  ℹ️ Same channel used in both rounds")

                # Check time difference if both times exist
                if r1_time and r2_time:
                    # Calculate time of day difference
                    r1_hour = r1_time.hour
                    r2_hour = r2_time.hour

                    if abs(r1_hour - r2_hour) >= 2:
                        logging.info(f"  ✅ ADAPTATION DETECTED: Timing  changed from {r1_hour}:00 to {r2_hour}:00")

        session.close()
    except Exception as e:
        logging.info(f"❌ Error comparing recommendations: {str(e)}")


if __name__ == "__main__":
    test_recommendation_flow()