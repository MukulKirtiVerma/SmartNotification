import os
import sys
import asyncio
from datetime import datetime

# Add the project root directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import Base, engine, get_mongo_collection
from app.db.models import User, NotificationPreference
from config.constants import NotificationType, NotificationChannel, Collections
from config.config import current_config


def setup_sql_database():
    """
    Set up the SQL database schema.
    """
    print("Setting up SQL database...")

    # Create all tables
    Base.meta_data.create_all(bind=engine)

    print("SQL database setup complete")


def setup_mongo_collections():
    """
    Set up the MongoDB collections.
    """
    print("Setting up MongoDB collections...")

    # Create required collections
    for collection_name in [
        Collections.USER_EVENTS,
        Collections.NOTIFICATION_HISTORY,
        Collections.USER_PROFILES,
        Collections.AGENT_LOGS,
        Collections.AB_TEST_RESULTS,
        "active_dashboard_alerts",
        "pending_notifications",
        "engagement_metrics",
        "user_metrics",
        "ab_test_deliveries",
        "ab_test_engagements"
    ]:
        try:
            get_mongo_collection(collection_name)
            print(f"Created collection: {collection_name}")
        except Exception as e:
            print(f"Error creating collection {collection_name}: {str(e)}")

    print("MongoDB setup complete")


def create_admin_user():
    """
    Create an admin user if it doesn't exist.
    """
    from sqlalchemy.orm import sessionmaker
    from app.utils.helpers import hash_password

    Session = sessionmaker(bind=engine)
    session = Session()

    # Check if admin user exists
    admin = session.query(User).filter(User.email == "admin@example.com").first()

    if not admin:
        print("Creating admin user...")

        # Create admin user
        admin = User(
            email="admin@example.com",
            username="admin",
            password_hash=hash_password("adminpassword"),  # In production, use a secure password
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        session.add(admin)
        session.commit()

        print("Admin user created")
    else:
        print("Admin user already exists")

    # Close session
    session.close()


def create_indexes():
    """
    Create required indexes on collections.
    """
    print("Creating MongoDB indexes...")

    try:
        # User events collection
        get_mongo_collection(Collections.USER_EVENTS).create_index("user_id")
        get_mongo_collection(Collections.USER_EVENTS).create_index("event_type")
        get_mongo_collection(Collections.USER_EVENTS).create_index("timestamp")

        # User profiles collection
        get_mongo_collection(Collections.USER_PROFILES).create_index("user_id", unique=True)

        # Notification history collection
        get_mongo_collection(Collections.NOTIFICATION_HISTORY).create_index("notification_id")
        get_mongo_collection(Collections.NOTIFICATION_HISTORY).create_index("user_id")

        # Agent logs collection
        get_mongo_collection(Collections.AGENT_LOGS).create_index("agent_id")
        get_mongo_collection(Collections.AGENT_LOGS).create_index("timestamp")

        # A/B test results collection
        get_mongo_collection(Collections.AB_TEST_RESULTS).create_index([("test_id", 1), ("variant", 1), ("metric", 1)],
                                                                       unique=True)

        # Active dashboard alerts
        get_mongo_collection("active_dashboard_alerts").create_index("user_id")
        get_mongo_collection("active_dashboard_alerts").create_index("notification_id")

        # User metrics
        get_mongo_collection("user_metrics").create_index([("user_id", 1), ("metric_type", 1)])

        print("MongoDB indexes created")
    except Exception as e:
        print(f"Error creating indexes: {str(e)}")


def main():
    """
    Main function to set up the databases.
    """
    print("Starting database setup...")

    # Setup SQL database
    setup_sql_database()

    # Setup MongoDB collections
    setup_mongo_collections()

    # Create indexes
    create_indexes()

    # Create admin user
    create_admin_user()

    print("Database setup complete!")


if __name__ == "__main__":
    main()