import os
import sys
import random
from datetime import datetime, timedelta
import sqlalchemy.exc

# Add the project root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import sessionmaker
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, BulkWriteError

from app.db.database import engine, mongo_db
from app.db.models import User, Notification, NotificationEngagement, NotificationPreference, ABTest
from config.constants import NotificationType, NotificationChannel, EngagementAction, TimeOfDay, Collections


def create_dummy_users(session, count=10):
    """
    Create dummy users, handling duplicates.

    Args:
        session: Database session
        count (int, optional): Number of users to create. Defaults to 10.

    Returns:
        list: Created users
    """
    print(f"Creating {count} dummy users...")

    users = []
    for i in range(1, count + 1):
        email = f"user{i}@example.com"
        username = f"user{i}"

        # Check if user already exists
        existing_user = session.query(User).filter(
            (User.email == email) | (User.username == username)
        ).first()

        if existing_user:
            print(f"User with email {email} or username {username} already exists, skipping...")
            users.append(existing_user)
            continue

        user = User(
            email=email,
            username=username,
            password_hash=f"password{i}",  # In production, hash passwords properly
            is_active=True,
            created_at=datetime.utcnow() - timedelta(days=random.randint(1, 30))
        )

        try:
            session.add(user)
            session.flush()  # Try to insert but don't commit yet
            users.append(user)
        except sqlalchemy.exc.IntegrityError:
            session.rollback()
            print(f"Failed to create user {email}, may already exist")
            # Try to fetch the existing user
            existing_user = session.query(User).filter(
                (User.email == email) | (User.username == username)
            ).first()
            if existing_user:
                users.append(existing_user)

    session.commit()
    print(f"Created or retrieved {len(users)} users")
    return users


def create_notification_preferences(session, users):
    """
    Create notification preferences for users, handling duplicates.

    Args:
        session: Database session
        users (list): User objects
    """
    print("Creating notification preferences...")

    preferences = []
    for user in users:
        # Create preferences for different combinations of types and channels
        for notification_type in random.sample(NotificationType.ALL, random.randint(3, len(NotificationType.ALL))):
            for channel in random.sample(NotificationChannel.ALL, random.randint(1, len(NotificationChannel.ALL))):
                # Check if preference already exists
                existing_pref = session.query(NotificationPreference).filter(
                    NotificationPreference.user_id == user.id,
                    NotificationPreference.notification_type == notification_type,
                    NotificationPreference.channel == channel
                ).first()

                if existing_pref:
                    print(
                        f"Preference for user {user.id}, type {notification_type}, channel {channel} already exists, skipping...")
                    preferences.append(existing_pref)
                    continue

                preference = NotificationPreference(
                    user_id=user.id,
                    notification_type=notification_type,
                    channel=channel,
                    is_enabled=random.choice([True, True, True, False]),  # 75% enabled
                    frequency=random.choice(["low", "normal", "high"]),
                    time_preference={
                        period: round(random.random(), 2)
                        for period in random.sample(TimeOfDay.ALL, random.randint(1, len(TimeOfDay.ALL)))
                    }
                )

                try:
                    session.add(preference)
                    session.flush()  # Try to insert but don't commit yet
                    preferences.append(preference)
                except sqlalchemy.exc.IntegrityError:
                    session.rollback()
                    print(f"Failed to create preference, may already exist")

    session.commit()
    print(f"Created or retrieved {len(preferences)} notification preferences")


def create_notifications(session, users, count_per_user=5):
    """
    Create dummy notifications for users.

    Args:
        session: Database session
        users (list): User objects
        count_per_user (int, optional): Notifications per user. Defaults to 5.

    Returns:
        list: Created notifications
    """
    print(f"Creating notifications ({count_per_user} per user)...")

    notifications = []
    for user in users:
        for _ in range(count_per_user):
            notification_type = random.choice(NotificationType.ALL)
            channel = random.choice(NotificationChannel.ALL)

            notification = Notification(
                user_id=user.id,
                type=notification_type,
                channel=channel,
                title=f"{notification_type.capitalize()} Notification",
                content=f"This is a {notification_type} notification via {channel}.",
                meta_data={  # Changed from meta_data to meta_data to avoid reserved name
                    "priority": random.choice(["low", "medium", "high"]),
                    "category": random.choice(["transactional", "marketing", "system"]),
                },
                is_sent=random.choice([True, True, False]),  # 67% sent
                created_at=datetime.utcnow() - timedelta(days=random.randint(0, 14))
            )

            # Set sent time for sent notifications
            if notification.is_sent:
                notification.sent_at = notification.created_at + timedelta(minutes=random.randint(1, 60))

            try:
                session.add(notification)
                session.flush()  # Try to insert but don't commit yet
                notifications.append(notification)
            except sqlalchemy.exc.IntegrityError:
                session.rollback()
                print(f"Failed to create notification, may already exist")

    session.commit()
    print(f"Created {len(notifications)} notifications")
    return notifications


def create_engagements(session, notifications):
    """
    Create dummy engagements for notifications.

    Args:
        session: Database session
        notifications (list): Notification objects
    """
    print("Creating notification engagements...")

    engagements = []
    for notification in notifications:
        # Only create engagements for sent notifications
        if notification.is_sent and notification.sent_at:
            # Randomly decide if this notification was engaged with
            if random.random() < 0.7:  # 70% engagement rate
                # Different engagement patterns based on channel
                if notification.channel == NotificationChannel.EMAIL:
                    # Email might have open and click
                    engagement = NotificationEngagement(
                        notification_id=notification.id,
                        action=EngagementAction.OPEN,
                        timestamp=notification.sent_at + timedelta(minutes=random.randint(5, 120))
                    )
                    try:
                        session.add(engagement)
                        session.flush()
                        engagements.append(engagement)
                    except sqlalchemy.exc.IntegrityError:
                        session.rollback()
                        print(f"Failed to create engagement, may already exist")
                        continue

                    # 50% chance of click after open
                    if random.random() < 0.5:
                        engagement = NotificationEngagement(
                            notification_id=notification.id,
                            action=EngagementAction.CLICK,
                            timestamp=engagement.timestamp + timedelta(seconds=random.randint(3, 30))
                        )
                        try:
                            session.add(engagement)
                            session.flush()
                            engagements.append(engagement)
                        except sqlalchemy.exc.IntegrityError:
                            session.rollback()
                            print(f"Failed to create click engagement, may already exist")

                elif notification.channel == NotificationChannel.PUSH:
                    # Push might have open, click, or dismiss
                    action = random.choice([EngagementAction.OPEN, EngagementAction.CLICK, EngagementAction.DISMISS])
                    engagement = NotificationEngagement(
                        notification_id=notification.id,
                        action=action,
                        timestamp=notification.sent_at + timedelta(minutes=random.randint(1, 60))
                    )
                    try:
                        session.add(engagement)
                        session.flush()
                        engagements.append(engagement)
                    except sqlalchemy.exc.IntegrityError:
                        session.rollback()
                        print(f"Failed to create push engagement, may already exist")

                elif notification.channel == NotificationChannel.SMS:
                    # SMS might have a "response" action
                    if random.random() < 0.3:  # 30% response rate
                        engagement = NotificationEngagement(
                            notification_id=notification.id,
                            action="response",
                            timestamp=notification.sent_at + timedelta(minutes=random.randint(5, 240)),
                            meta_data={"content": random.choice(["OK", "Thanks", "Got it", "Please unsubscribe"])}
                        )
                        try:
                            session.add(engagement)
                            session.flush()
                            engagements.append(engagement)
                        except sqlalchemy.exc.IntegrityError:
                            session.rollback()
                            print(f"Failed to create SMS engagement, may already exist")

                elif notification.channel == NotificationChannel.DASHBOARD:
                    # Dashboard might have view, click
                    action = random.choice([EngagementAction.OPEN, EngagementAction.CLICK])
                    engagement = NotificationEngagement(
                        notification_id=notification.id,
                        action=action,
                        timestamp=notification.sent_at + timedelta(hours=random.randint(1, 24)),
                        meta_data={"duration": random.randint(5, 60)}
                    )
                    try:
                        session.add(engagement)
                        session.flush()
                        engagements.append(engagement)
                    except sqlalchemy.exc.IntegrityError:
                        session.rollback()
                        print(f"Failed to create dashboard engagement, may already exist")

    session.commit()
    print(f"Created {len(engagements)} notification engagements")


def create_ab_tests(session):
    """
    Create dummy A/B tests, handling duplicates.

    Args:
        session: Database session
    """
    print("Creating A/B tests...")

    tests = []
    test_configs = [
        {
            "name": "Email Subject Line Test",
            "description": "Testing different subject line formats for shipment notifications",
            "start_date": datetime.utcnow() - timedelta(days=14),
            "end_date": datetime.utcnow() + timedelta(days=7),
            "is_active": True,
            "metrics": ["open_rate", "click_rate"],
            "variants": {
                "control": {
                    "description": "Standard subject",
                    "subject_template": "Your order has shipped"
                },
                "variant_a": {
                    "description": "Order number in subject",
                    "subject_template": "Order #{{order_id}} has shipped"
                },
                "variant_b": {
                    "description": "Estimated delivery in subject",
                    "subject_template": "Your order has shipped - Delivery on {{delivery_date}}"
                }
            }
        },
        {
            "name": "Notification Timing Test",
            "description": "Testing different times of day for sending notifications",
            "start_date": datetime.utcnow() - timedelta(days=7),
            "end_date": datetime.utcnow() + timedelta(days=14),
            "is_active": True,
            "metrics": ["open_rate", "engagement_score"],
            "variants": {
                "control": {
                    "description": "Send at standard time (9 AM)",
                    "delivery_hour": 9
                },
                "variant_a": {
                    "description": "Send at lunch time (12 PM)",
                    "delivery_hour": 12
                },
                "variant_b": {
                    "description": "Send in evening (7 PM)",
                    "delivery_hour": 19
                }
            }
        },
        {
            "name": "Channel Preference Test",
            "description": "Testing user response to different notification channels",
            "start_date": datetime.utcnow() - timedelta(days=3),
            "end_date": datetime.utcnow() + timedelta(days=18),
            "is_active": True,
            "metrics": ["engagement_score"],
            "variants": {
                "control": {
                    "description": "Use user's primary preferred channel",
                    "strategy": "primary_preference"
                },
                "variant_a": {
                    "description": "Use alternate channels occasionally",
                    "strategy": "mixed_channels"
                },
                "variant_b": {
                    "description": "Use channel appropriate for notification type",
                    "strategy": "type_based_channel"
                }
            }
        }
    ]

    for config in test_configs:
        # Check if test with this name already exists
        existing_test = session.query(ABTest).filter(ABTest.name == config["name"]).first()
        if existing_test:
            print(f"A/B test '{config['name']}' already exists, skipping...")
            tests.append(existing_test)
            continue

        test = ABTest(**config)
        try:
            session.add(test)
            session.flush()
            tests.append(test)
        except sqlalchemy.exc.IntegrityError:
            session.rollback()
            print(f"Failed to create A/B test '{config['name']}', may already exist")

    session.commit()
    print(f"Created or retrieved {len(tests)} A/B tests")


def create_user_events(users):
    """
    Create dummy user events in MongoDB, handling duplicates.

    Args:
        users (list): User objects
    """
    print("Creating user events in MongoDB...")

    events_collection = mongo_db[Collections.USER_EVENTS]

    # Ensure we have an index on event identification fields to avoid duplicates
    try:
        events_collection.create_index([("user_id", 1), ("event_type", 1), ("timestamp", 1)], unique=True)
    except Exception as e:
        print(f"Note: Could not create unique index: {e}")

    total_inserted = 0

    for user in users:
        events = []

        # Dashboard views
        num_dashboard_views = random.randint(3, 20)
        for _ in range(num_dashboard_views):
            timestamp = datetime.utcnow() - timedelta(days=random.randint(0, 30))
            events.append({
                "user_id": user.id,
                "event_type": "dashboard_view",
                "channel": NotificationChannel.DASHBOARD,
                "timestamp": timestamp,
                "details": {
                    "url": f"/dashboard/{random.choice(['home', 'orders', 'shipments', 'payments', 'settings'])}",
                    "duration": random.randint(30, 600),  # seconds
                    "section": random.choice(["main", "shipments", "orders", "payments", "delivery"])
                },
                "context": {
                    "session_id": f"session_{user.id}_{random.randint(1000, 9999)}",
                    "ip": f"192.168.1.{random.randint(1, 255)}",
                    "user_agent": random.choice([
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
                        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15"
                    ])
                }
            })

        # Email engagements
        num_email_events = random.randint(2, 15)
        for _ in range(num_email_events):
            timestamp = datetime.utcnow() - timedelta(days=random.randint(0, 30))
            events.append({
                "user_id": user.id,
                "event_type": "email_engagement",
                "channel": NotificationChannel.EMAIL,
                "timestamp": timestamp,
                "details": {
                    "notification_id": random.randint(1, 500),  # Fictional ID
                    "notification_type": random.choice(NotificationType.ALL),
                    "action": random.choice([EngagementAction.OPEN, EngagementAction.CLICK])
                }
            })

        # Push engagements
        num_push_events = random.randint(1, 10)
        for _ in range(num_push_events):
            timestamp = datetime.utcnow() - timedelta(days=random.randint(0, 30))
            events.append({
                "user_id": user.id,
                "event_type": "push_engagement",
                "channel": NotificationChannel.PUSH,
                "timestamp": timestamp,
                "details": {
                    "notification_id": random.randint(1, 500),  # Fictional ID
                    "notification_type": random.choice(NotificationType.ALL),
                    "action": random.choice([EngagementAction.OPEN, EngagementAction.CLICK, EngagementAction.DISMISS])
                }
            })

        # Insert events in smaller batches to handle potential duplicates
        if events:
            for i in range(0, len(events), 50):  # Process in batches of 50
                batch = events[i:i + 50]
                try:
                    result = events_collection.insert_many(batch, ordered=False)
                    total_inserted += len(result.inserted_ids)
                except BulkWriteError as e:
                    # Some documents might be inserted even with errors
                    if 'nInserted' in e.details:
                        total_inserted += e.details['nInserted']
                    print(f"Some events already existed in batch {i // 50 + 1}")
                except Exception as e:
                    print(f"Error inserting events batch {i // 50 + 1}: {str(e)}")

    print(f"Inserted {total_inserted} user events into MongoDB")


def create_user_profiles(users):
    """
    Create dummy user profiles in MongoDB, handling duplicates.

    Args:
        users (list): User objects
    """
    print("Creating user profiles in MongoDB...")

    profiles_collection = mongo_db[Collections.USER_PROFILES]

    # Ensure we have an index on user_id to avoid duplicates
    try:
        profiles_collection.create_index("user_id", unique=True)
    except Exception as e:
        print(f"Note: Could not create unique index: {e}")

    success_count = 0

    for user in users:
        # Generate random profile data
        profile = {
            "user_id": user.id,
            "last_updated": datetime.utcnow() - timedelta(hours=random.randint(1, 72)),

            # Channel preferences
            "channel_preferences": {
                "channel_scores": {
                    NotificationChannel.EMAIL: round(random.random(), 2),
                    NotificationChannel.PUSH: round(random.random(), 2),
                    NotificationChannel.SMS: round(random.random(), 2),
                    NotificationChannel.DASHBOARD: round(random.random(), 2)
                }
            },

            # Content preferences
            "content_preferences": {
                "type_scores": {
                    notification_type: round(random.random(), 2)
                    for notification_type in NotificationType.ALL
                }
            },

            # Frequency preferences
            "frequency_preferences": {
                "level": random.choice(["very_low", "low", "medium", "high", "very_high"]),
                "score": round(random.random(), 2),
                "max_daily_notifications": random.randint(1, 10),
                "last_updated": datetime.utcnow() - timedelta(days=random.randint(1, 7))
            },

            # Time preferences
            "time_preferences": {
                "distribution": {
                    period: round(random.random(), 2)
                    for period in TimeOfDay.ALL
                }
            }
        }

        # Calculate ranked channels
        channel_scores = profile["channel_preferences"]["channel_scores"]
        profile["channel_preferences"]["ranked_channels"] = sorted(
            channel_scores.keys(),
            key=lambda c: channel_scores[c],
            reverse=True
        )

        # Calculate preferred types
        type_scores = profile["content_preferences"]["type_scores"]
        profile["content_preferences"]["preferred_types"] = sorted(
            type_scores.keys(),
            key=lambda t: type_scores[t],
            reverse=True
        )

        # Calculate peak period
        time_distribution = profile["time_preferences"]["distribution"]
        profile["time_preferences"]["peak_period"] = max(
            time_distribution.keys(),
            key=lambda p: time_distribution[p]
        )

        # Calculate segments
        segments = [
            f"frequency_{profile['frequency_preferences']['level']}",
            f"prefers_{profile['channel_preferences']['ranked_channels'][0]}",
            f"prefers_{profile['content_preferences']['preferred_types'][0]}",
            f"active_{profile['time_preferences']['peak_period']}"
        ]
        profile["segments"] = segments

        # Try to insert or update profile
        try:
            result = profiles_collection.update_one(
                {"user_id": user.id},
                {"$set": profile},
                upsert=True
            )
            if result.upserted_id or result.modified_count > 0:
                success_count += 1
        except Exception as e:
            print(f"Error upserting profile for user {user.id}: {str(e)}")

    print(f"Created or updated {success_count} user profiles in MongoDB")


def main():
    """
    Main function to generate dummy data.
    """
    print("Starting dummy data generation...")

    # Create a session
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Create users
        users = create_dummy_users(session, count=20)

        # Create notification preferences
        create_notification_preferences(session, users)

        # Create notifications
        notifications = create_notifications(session, users, count_per_user=10)

        # Create engagements
        create_engagements(session, notifications)

        # Create A/B tests
        create_ab_tests(session)

        # Create MongoDB data
        create_user_events(users)
        create_user_profiles(users)

        print("Dummy data generation complete!")

    except Exception as e:
        print(f"Error generating dummy data: {str(e)}")
        session.rollback()
        raise

    finally:
        session.close()


if __name__ == "__main__":
    main()