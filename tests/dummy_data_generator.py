# dummy_data_generator.py
import random
from datetime import datetime, timedelta
import uuid
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import (
    User, Notification, NotificationEngagement,
    NotificationPreference, UserSession, PageView,
    ABTest, ABTestAssignment, UserMetric, AgentLog
)


def generate_dummy_data():
    """Generate dummy users with different activity patterns"""
    db = next(get_db())

    # Create users with different activity levels
    print("Creating users...")
    high_activity_users = create_users(db, 20, "high")
    medium_activity_users = create_users(db, 20, "medium")
    low_activity_users = create_users(db, 20, "low")

    # Create notification preferences
    print("Creating notification preferences...")
    create_notification_preferences(db, high_activity_users + medium_activity_users + low_activity_users)

    # Generate user sessions and page views
    print("Generating user sessions and page views...")
    generate_user_sessions(db, high_activity_users, session_count_range=(8, 15), pages_per_session=(10, 30))
    generate_user_sessions(db, medium_activity_users, session_count_range=(4, 7), pages_per_session=(5, 15))
    generate_user_sessions(db, low_activity_users, session_count_range=(1, 3), pages_per_session=(1, 5))

    # Generate some initial notifications
    print("Generating initial notifications...")
    notification_types = ["shipment", "packing", "delivery", "payment", "promotion"]
    channels = ["email", "dashboard", "push", "sms"]

    generate_notifications(db, high_activity_users, notification_types, channels, count_range=(5, 10))
    generate_notifications(db, medium_activity_users, notification_types, channels, count_range=(3, 7))
    generate_notifications(db, low_activity_users, notification_types, channels, count_range=(1, 3))

    # Create AB test
    print("Setting up A/B test...")
    setup_ab_test(db, high_activity_users + medium_activity_users + low_activity_users)

    # Create initial metrics
    print("Creating initial user metrics...")
    create_initial_metrics(db, high_activity_users + medium_activity_users + low_activity_users)

    db.commit()
    print("Dummy data generation complete!")


def create_users(db, count, activity_level):
    """Create users with a specific activity level tag in their username"""
    users = []
    for i in range(count):
        user = User(
            email=f"{activity_level}_user_{i}@example.com",
            username=f"{activity_level}_user_{i}",
            password_hash="dummy_hash_for_testing",
            is_active=True
        )
        db.add(user)
        users.append(user)

    db.commit()
    return users


def create_notification_preferences(db, users):
    """Create notification preferences for users"""
    notification_types = ["shipment", "packing", "delivery", "payment", "promotion"]
    channels = ["email", "dashboard", "push", "sms"]

    for user in users:
        # Extract activity level from username
        activity_level = user.username.split('_')[0]

        for notification_type in notification_types:
            for channel in channels:
                # Determine if this channel is enabled based on activity level
                is_enabled = True

                # Set frequency based on activity level
                if activity_level == "high":
                    frequency = "high"
                elif activity_level == "medium":
                    frequency = "normal"
                else:
                    frequency = "low"

                preference = NotificationPreference(
                    user_id=user.id,
                    notification_type=notification_type,
                    channel=channel,
                    is_enabled=is_enabled,
                    frequency=frequency,
                    time_preference={"morning": True, "afternoon": True, "evening": True}
                )
                db.add(preference)

    db.commit()


def generate_user_sessions(db, users, session_count_range, pages_per_session):
    """Generate user sessions and page views based on activity level"""
    now = datetime.utcnow()

    for user in users:
        # Generate sessions for the last 30 days
        session_count = random.randint(*session_count_range)

        for _ in range(session_count):
            # Random date in the last 30 days
            days_ago = random.randint(0, 30)
            session_start = now - timedelta(days=days_ago,
                                            hours=random.randint(0, 23),
                                            minutes=random.randint(0, 59))

            # Some sessions ended, some still active
            is_active = random.random() < 0.2
            ended_at = None if is_active else session_start + timedelta(minutes=random.randint(5, 120))

            session = UserSession(
                user_id=user.id,
                session_id=str(uuid.uuid4()),
                ip_address=f"192.168.1.{random.randint(1, 255)}",
                user_agent=f"Mozilla/5.0 Test Agent {random.randint(1, 100)}",
                started_at=session_start,
                ended_at=ended_at,
                is_active=is_active
            )
            db.add(session)
            db.flush()  # To get the session ID

            # Generate page views for this session
            page_count = random.randint(*pages_per_session)
            current_time = session_start

            for _ in range(page_count):
                if not is_active and current_time > ended_at:
                    break

                # Page view duration between 10 seconds and 5 minutes
                duration = random.randint(10, 300)

                page_view = PageView(
                    session_id=session.id,
                    url=f"/page/{random.choice(['dashboard', 'shipments', 'orders', 'settings', 'profile', 'notifications'])}",
                    view_time=current_time,
                    duration=duration,
                    meta_data={"referrer": random.choice([None, "google", "direct", "email"])}
                )
                db.add(page_view)

                # Move time forward
                current_time += timedelta(seconds=duration + random.randint(0, 60))

    db.commit()


def generate_notifications(db, users, notification_types, channels, count_range):
    """Generate notifications for users"""
    now = datetime.utcnow()

    for user in users:
        # Extract activity level from username
        activity_level = user.username.split('_')[0]

        # Generate notifications
        notification_count = random.randint(*count_range)

        for _ in range(notification_count):
            # Random date in the last 15 days
            days_ago = random.randint(0, 15)
            notification_time = now - timedelta(days=days_ago,
                                                hours=random.randint(0, 23),
                                                minutes=random.randint(0, 59))

            notification_type = random.choice(notification_types)
            channel = random.choice(channels)

            notification = Notification(
                user_id=user.id,
                type=notification_type,
                channel=channel,
                title=f"{notification_type.capitalize()} Update",
                content=f"This is a test {notification_type} notification for {activity_level} activity user",
                meta_data={"priority": random.choice(["low", "medium", "high"])},
                scheduled_at=notification_time - timedelta(minutes=random.randint(1, 30)),
                sent_at=notification_time,
                is_sent=True,
                created_at=notification_time - timedelta(hours=random.randint(1, 24))
            )
            db.add(notification)
            db.flush()  # To get the notification ID

            # Determine engagement probability based on activity level
            if activity_level == "high":
                engagement_probability = 0.6
            elif activity_level == "medium":
                engagement_probability = 0.7
            else:  # low
                engagement_probability = 0.8

            # Decide if user engages with notification
            if random.random() < engagement_probability:
                action = random.choice(["open", "click", "dismiss"])

                engagement = NotificationEngagement(
                    notification_id=notification.id,
                    action=action,
                    timestamp=notification_time + timedelta(minutes=random.randint(1, 60)),
                    meta_data={"device": random.choice(["mobile", "desktop", "tablet"])}
                )
                db.add(engagement)

    db.commit()


def setup_ab_test(db, users):
    """Set up an A/B test for notification frequency"""
    ab_test = ABTest(
        name="notification_frequency_test",
        description="Testing different notification frequencies",
        start_date=datetime.utcnow() - timedelta(days=30),
        end_date=None,  # Still active
        is_active=True,
        metrics={"open_rate": True, "click_rate": True, "dismiss_rate": True},
        variants={"control": "normal frequency", "variant_a": "higher frequency", "variant_b": "lower frequency"}
    )
    db.add(ab_test)
    db.flush()

    # Assign users to variants
    variants = ["control", "variant_a", "variant_b"]

    for user in users:
        assignment = ABTestAssignment(
            ab_test_id=ab_test.id,
            user_id=user.id,
            variant=random.choice(variants)
        )
        db.add(assignment)

    db.commit()


def create_initial_metrics(db, users):
    """Create initial user metrics"""
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)

    for user in users:
        # Extract activity level from username
        activity_level = user.username.split('_')[0]

        # Set metrics based on activity level
        if activity_level == "high":
            engagement_rate = random.uniform(0.5, 0.7)
            session_frequency = random.uniform(0.7, 0.9)
        elif activity_level == "medium":
            engagement_rate = random.uniform(0.3, 0.5)
            session_frequency = random.uniform(0.4, 0.6)
        else:  # low
            engagement_rate = random.uniform(0.1, 0.3)
            session_frequency = random.uniform(0.1, 0.3)

        # Create engagement rate metric
        db.add(UserMetric(
            user_id=user.id,
            metric_type="engagement_rate",
            value=engagement_rate,
            period_start=thirty_days_ago,
            period_end=now
        ))

        # Create session frequency metric
        db.add(UserMetric(
            user_id=user.id,
            metric_type="session_frequency",
            value=session_frequency,
            period_start=thirty_days_ago,
            period_end=now
        ))

    db.commit()


if __name__ == "__main__":
    generate_dummy_data()