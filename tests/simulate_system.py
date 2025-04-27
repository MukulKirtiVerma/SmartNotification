# simulate_system.py
import random
import asyncio
from datetime import datetime, timedelta
import uuid
from sqlalchemy import func
from app.db.database import get_db
from app.db.models import (
    User, Notification, NotificationEngagement,
    UserSession, PageView, UserMetric, AgentLog
)


async def simulate_notification_system(days_to_simulate=30):
    """Simulate the notification system running for a period of time"""
    print(f"Simulating notification system for {days_to_simulate} days...")

    # Simulate each day
    for day in range(1, days_to_simulate + 1):
        print(f"Simulating day {day}...")

        # Step 1: Generate new user activities
        await generate_daily_activities(day)

        # Step 2: Run the behavior analysis
        await analyze_user_behavior(day)

        # Step 3: Generate adapted notifications
        await generate_adapted_notifications(day)

        # Step 4: Simulate user engagement with notifications
        await simulate_notification_engagement(day)

        # Step 5: Update user metrics
        await update_user_metrics(day)

        # Every 5 days, print a progress report
        if day % 5 == 0:
            await run_analysis_report(day)

    print("Simulation complete!")


async def generate_daily_activities(day):
    """Generate daily activities for all users based on their activity level"""
    db = next(get_db())
    users = db.query(User).all()

    # Set simulation date
    simulation_date = datetime.utcnow() - timedelta(days=30 - day)

    for user in users:
        # Determine activity level from username
        activity_level = user.username.split('_')[0]

        # Activity probability based on user level
        if activity_level == "high":
            session_probability = 0.9  # 90% chance of activity
            pages_per_session = (8, 20)
        elif activity_level == "medium":
            session_probability = 0.6  # 60% chance of activity
            pages_per_session = (3, 10)
        else:  # low
            session_probability = 0.3  # 30% chance of activity
            pages_per_session = (1, 5)

        # Decide if user is active today
        if random.random() < session_probability:
            # Create session
            session_start = simulation_date.replace(
                hour=random.randint(8, 22),
                minute=random.randint(0, 59)
            )

            # Session duration between 5 and 120 minutes
            session_duration = random.randint(5, 120)
            ended_at = session_start + timedelta(minutes=session_duration)

            session = UserSession(
                user_id=user.id,
                session_id=str(uuid.uuid4()),
                ip_address=f"192.168.1.{random.randint(1, 255)}",
                user_agent=f"Mozilla/5.0 Test Agent {random.randint(1, 100)}",
                started_at=session_start,
                ended_at=ended_at,
                is_active=False
            )
            db.add(session)
            db.flush()  # To get the session ID

            # Generate page views for this session
            page_count = random.randint(*pages_per_session)
            current_time = session_start

            for _ in range(page_count):
                if current_time > ended_at:
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

    # Log the agent activity
    agent_log = AgentLog(
        agent_type="DashboardTrackerAgent",
        action="track_daily_activities",
        status="success",
        details={"day": day, "activities_generated": True}
    )
    db.add(agent_log)
    db.commit()


async def analyze_user_behavior(day):
    """Simulate behavior analysis by the AI agents"""
    db = next(get_db())
    simulation_date = datetime.utcnow() - timedelta(days=30 - day)

    # Log analysis activity
    for agent_type in ["FrequencyAnalysisAgent", "TypeAnalysisAgent", "ChannelAnalysisAgent"]:
        agent_log = AgentLog(
            agent_type=agent_type,
            action="analyze_user_behavior",
            status="success",
            details={"day": day, "analysis_date": simulation_date.isoformat()}
        )
        db.add(agent_log)

    db.commit()


async def generate_adapted_notifications(day):
    """Generate notifications adapted to user behavior"""
    db = next(get_db())
    users = db.query(User).all()
    simulation_date = datetime.utcnow() - timedelta(days=30 - day)

    notification_types = ["shipment", "packing", "delivery", "payment", "promotion"]
    channels = ["email", "dashboard", "push", "sms"]

    for user in users:
        # Determine activity level from username
        activity_level = user.username.split('_')[0]

        # As days progress, make notifications more adapted to user behavior
        adaptation_factor = min(1.0, day / 15)  # Full adaptation by day 15

        # Base probabilities (without adaptation)
        if activity_level == "high":
            base_notification_probability = 0.7  # 70% chance
        elif activity_level == "medium":
            base_notification_probability = 0.5  # 50% chance
            # continuing generate_adapted_notifications function
        else:  # low
            base_notification_probability = 0.3  # 30% chance

        # Adapt notification probability based on progression
        # As simulation progresses, high users get more, low users get fewer
        if activity_level == "high":
            notification_probability = base_notification_probability + (0.2 * adaptation_factor)
        elif activity_level == "medium":
            notification_probability = base_notification_probability
        else:  # low
            notification_probability = base_notification_probability - (0.1 * adaptation_factor)

        # Ensure probability is within bounds
        notification_probability = max(0.1, min(0.9, notification_probability))

        # Decide whether to send notification
        if random.random() < notification_probability:
            # Adapt channel selection based on user behavior
            # For simplicity, just use random selection - in a real system this would be based on engagement data
            channel = random.choice(channels)

            # Select notification type - in a real system, this would also be adapted
            notification_type = random.choice(notification_types)

            # Create notification
            notification_time = simulation_date.replace(
                hour=random.randint(8, 20),
                minute=random.randint(0, 59)
            )

            notification = Notification(
                user_id=user.id,
                type=notification_type,
                channel=channel,
                title=f"{notification_type.capitalize()} Update",
                content=f"This is an adaptive {notification_type} notification for {activity_level} activity user on day {day}",
                meta_data={"priority": random.choice(["low", "medium", "high"]), "day": day},
                scheduled_at=notification_time - timedelta(minutes=random.randint(1, 30)),
                sent_at=notification_time,
                is_sent=True,
                created_at=notification_time - timedelta(hours=random.randint(1, 4))
            )
            db.add(notification)

    db.commit()

    # Log the agent activity
    agent_log = AgentLog(
        agent_type="NotificationService",
        action="generate_adaptive_notifications",
        status="success",
        details={"day": day, "adaptation_factor": adaptation_factor}
    )
    db.add(agent_log)
    db.commit()


async def simulate_notification_engagement(day):
    """Simulate users engaging with notifications"""
    db = next(get_db())
    simulation_date = datetime.utcnow() - timedelta(days=30 - day)

    # Get notifications sent on this simulation day without engagement records
    notifications = db.query(Notification).outerjoin(
        NotificationEngagement,
        Notification.id == NotificationEngagement.notification_id
    ).filter(
        NotificationEngagement.id == None,
        Notification.is_sent == True,
        func.date(Notification.sent_at) == func.date(simulation_date)
    ).all()

    for notification in notifications:
        # Get user activity level
        user = db.query(User).filter(User.id == notification.user_id).first()
        activity_level = user.username.split('_')[0]

        # Determine engagement probability based on user activity level and adaptation
        # As days progress, engagement rates should improve for all users, but especially for low activity users
        adaptation_factor = min(1.0, day / 15)  # Full adaptation by day 15

        if activity_level == "high":
            base_engagement_probability = 0.6  # 60% chance
            adapted_probability = base_engagement_probability + (0.1 * adaptation_factor)
        elif activity_level == "medium":
            base_engagement_probability = 0.5  # 50% chance
            adapted_probability = base_engagement_probability + (0.15 * adaptation_factor)
        else:  # low
            base_engagement_probability = 0.4  # 40% chance
            adapted_probability = base_engagement_probability + (0.2 * adaptation_factor)

        # Ensure probability is within bounds
        engagement_probability = max(0.4, min(0.9, adapted_probability))

        # Decide if user engages with notification
        if random.random() < engagement_probability:
            # Determine action based on some probability
            action_probability = random.random()

            if action_probability < 0.6:  # 60% open
                action = "open"
            elif action_probability < 0.8:  # 20% click
                action = "click"
            else:  # 20% dismiss
                action = "dismiss"

            # Create engagement record
            engagement_time = notification.sent_at + timedelta(minutes=random.randint(1, 120))

            engagement = NotificationEngagement(
                notification_id=notification.id,
                action=action,
                timestamp=engagement_time,
                meta_data={"device": random.choice(["mobile", "desktop", "tablet"])}
            )
            db.add(engagement)

    db.commit()


async def update_user_metrics(day):
    """Update user metrics based on activities and engagements"""
    db = next(get_db())
    simulation_date = datetime.utcnow() - timedelta(days=30 - day)
    day_start = simulation_date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)

    # Process each user
    users = db.query(User).all()

    for user in users:
        # Calculate engagement rate for today
        notifications_count = db.query(func.count(Notification.id)).filter(
            Notification.user_id == user.id,
            Notification.sent_at >= day_start,
            Notification.sent_at < day_end,
            Notification.is_sent == True
        ).scalar() or 0

        engagements_count = db.query(func.count(NotificationEngagement.id)).join(
            Notification,
            NotificationEngagement.notification_id == Notification.id
        ).filter(
            Notification.user_id == user.id,
            NotificationEngagement.timestamp >= day_start,
            NotificationEngagement.timestamp < day_end
        ).scalar() or 0

        engagement_rate = engagements_count / notifications_count if notifications_count > 0 else 0

        # Calculate session frequency for today
        sessions_count = db.query(func.count(UserSession.id)).filter(
            UserSession.user_id == user.id,
            UserSession.started_at >= day_start,
            UserSession.started_at < day_end
        ).scalar() or 0

        session_frequency = sessions_count / 1.0  # sessions per day

        # Store metrics
        db.add(UserMetric(
            user_id=user.id,
            metric_type="engagement_rate",
            value=engagement_rate,
            period_start=day_start,
            period_end=day_end
        ))

        db.add(UserMetric(
            user_id=user.id,
            metric_type="session_frequency",
            value=session_frequency,
            period_start=day_start,
            period_end=day_end
        ))

    db.commit()

    # Log the agent activity
    agent_log = AgentLog(
        agent_type="MetricsAgent",
        action="update_user_metrics",
        status="success",
        details={"day": day, "metrics_updated": True}
    )
    db.add(agent_log)
    db.commit()


async def run_analysis_report(day):
    """Run analysis report at specific intervals"""
    from adaptation_validator import validate_adaptation

    print(f"\n===== DAY {day} ANALYSIS REPORT =====")
    await validate_adaptation()
    print("=====================================\n")


if __name__ == "__main__":
    asyncio.run(simulate_notification_system(days_to_simulate=30))