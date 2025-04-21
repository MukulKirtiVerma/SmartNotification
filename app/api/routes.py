from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User, Notification, NotificationEngagement, NotificationPreference, ABTest
from app.api.schemas import (
    User as UserSchema,
    UserCreate,
    Notification as NotificationSchema,
    NotificationCreate,
    NotificationPreference as NotificationPreferenceSchema,
    NotificationPreferenceCreate,
    Engagement,
    EngagementCreate,
    ABTest as ABTestSchema,
    ABTestCreate,
    DashboardAlert,
    DashboardAlertCreate,
    SystemStatus
)
from app.agents.agent_registry import AgentRegistry
from app.agents.base_agent import BaseAgent
from config.constants import NotificationChannel, NotificationType, AgentType

router = APIRouter()


# User routes
@router.post("/users/", response_model=UserSchema)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create a new user."""
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # In a real app, you would hash the password here
    password_hash = user.password  # DEMO ONLY - don't do this in production!

    db_user = User(
        email=user.email,
        username=user.username,
        password_hash=password_hash
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.get("/users/", response_model=List[UserSchema])
def get_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get a list of users."""
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.get("/users/{user_id}", response_model=UserSchema)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get a specific user by ID."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# Notification routes
@router.post("/notifications/", response_model=NotificationSchema)
async def create_notification(notification: NotificationCreate, background_tasks: BackgroundTasks,
                              db: Session = Depends(get_db)):
    """Create a new notification."""
    # Validate user exists
    user = db.query(User).filter(User.id == notification.user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate notification type and channel
    if notification.type not in NotificationType.ALL:
        raise HTTPException(status_code=400, detail=f"Invalid notification type: {notification.type}")

    if notification.channel not in NotificationChannel.ALL:
        raise HTTPException(status_code=400, detail=f"Invalid notification channel: {notification.channel}")

    # Create notification object
    db_notification = Notification(
        user_id=notification.user_id,
        type=notification.type,
        channel=notification.channel,
        title=notification.title,
        content=notification.content,
        meta_data=notification.meta_data,
        scheduled_at=notification.scheduled_at or datetime.utcnow()
    )
    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)

    # Send to Recommendation System as a background task
    background_tasks.add_task(
        send_notification_to_recommendation_system,
        db_notification.id
    )

    return db_notification


@router.get("/notifications/", response_model=List[NotificationSchema])
def get_notifications(
        user_id: Optional[int] = None,
        channel: Optional[str] = None,
        type: Optional[str] = None,
        is_sent: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db)
):
    """Get a list of notifications with optional filters."""
    query = db.query(Notification)

    if user_id is not None:
        query = query.filter(Notification.user_id == user_id)

    if channel is not None:
        if channel not in NotificationChannel.ALL:
            raise HTTPException(status_code=400, detail=f"Invalid channel: {channel}")
        query = query.filter(Notification.channel == channel)

    if type is not None:
        if type not in NotificationType.ALL:
            raise HTTPException(status_code=400, detail=f"Invalid type: {type}")
        query = query.filter(Notification.type == type)

    if is_sent is not None:
        query = query.filter(Notification.is_sent == is_sent)

    notifications = query.offset(skip).limit(limit).all()
    return notifications


@router.get("/notifications/{notification_id}", response_model=NotificationSchema)
def get_notification(notification_id: int, db: Session = Depends(get_db)):
    """Get a specific notification by ID."""
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


# Engagement routes
@router.post("/engagements/", response_model=Engagement)
async def create_engagement(engagement: EngagementCreate, background_tasks: BackgroundTasks,
                            db: Session = Depends(get_db)):
    """Record a notification engagement."""
    # Validate notification exists
    notification = db.query(Notification).filter(Notification.id == engagement.notification_id).first()
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")

    # Create engagement record
    db_engagement = NotificationEngagement(
        notification_id=engagement.notification_id,
        action=engagement.action,
        meta_data=engagement.meta_data,
        timestamp=datetime.utcnow()
    )
    db.add(db_engagement)
    db.commit()
    db.refresh(db_engagement)

    # Process engagement as a background task
    background_tasks.add_task(
        process_engagement,
        db_engagement.id,
        notification.channel
    )

    return db_engagement


# Notification preferences routes
@router.post("/preferences/", response_model=NotificationPreferenceSchema)
def create_preference(preference: NotificationPreferenceCreate, db: Session = Depends(get_db)):
    """Create or update a notification preference."""
    # Validate user exists
    user = db.query(User).filter(User.id == preference.user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if preference already exists
    db_preference = db.query(NotificationPreference).filter(
        NotificationPreference.user_id == preference.user_id,
        NotificationPreference.notification_type == preference.notification_type,
        NotificationPreference.channel == preference.channel
    ).first()

    if db_preference:
        # Update existing preference
        db_preference.is_enabled = preference.is_enabled
        db_preference.frequency = preference.frequency
        db_preference.time_preference = preference.time_preference
        db_preference.updated_at = datetime.utcnow()
    else:
        # Create new preference
        db_preference = NotificationPreference(
            user_id=preference.user_id,
            notification_type=preference.notification_type,
            channel=preference.channel,
            is_enabled=preference.is_enabled,
            frequency=preference.frequency,
            time_preference=preference.time_preference
        )
        db.add(db_preference)

    db.commit()
    db.refresh(db_preference)
    return db_preference


@router.get("/preferences/", response_model=List[NotificationPreferenceSchema])
def get_preferences(user_id: int, db: Session = Depends(get_db)):
    """Get notification preferences for a user."""
    preferences = db.query(NotificationPreference).filter(
        NotificationPreference.user_id == user_id
    ).all()
    return preferences


# A/B Test routes
@router.post("/ab-tests/", response_model=ABTestSchema)
def create_ab_test(ab_test: ABTestCreate, db: Session = Depends(get_db)):
    """Create a new A/B test."""
    # Validate variants
    if "control" not in ab_test.variants:
        raise HTTPException(status_code=400, detail="A/B test must include a 'control' variant")

    # Create A/B test
    db_ab_test = ABTest(
        name=ab_test.name,
        description=ab_test.description,
        variants=ab_test.variants,
        metrics=ab_test.metrics,
        start_date=ab_test.start_date or datetime.utcnow(),
        end_date=ab_test.end_date,
        is_active=True
    )
    db.add(db_ab_test)
    db.commit()
    db.refresh(db_ab_test)
    return db_ab_test


@router.get("/ab-tests/", response_model=List[ABTestSchema])
def get_ab_tests(is_active: Optional[bool] = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get a list of A/B tests."""
    query = db.query(ABTest)

    if is_active is not None:
        query = query.filter(ABTest.is_active == is_active)

    ab_tests = query.offset(skip).limit(limit).all()
    return ab_tests


@router.get("/ab-tests/{ab_test_id}", response_model=ABTestSchema)
def get_ab_test(ab_test_id: int, db: Session = Depends(get_db)):
    """Get a specific A/B test by ID."""
    ab_test = db.query(ABTest).filter(ABTest.id == ab_test_id).first()
    if ab_test is None:
        raise HTTPException(status_code=404, detail="A/B test not found")
    return ab_test


# Dashboard alert routes
@router.post("/dashboard-alerts/interaction/")
async def dashboard_alert_interaction(interaction: DashboardAlertCreate, background_tasks: BackgroundTasks):
    """Record a dashboard alert interaction."""
    # This endpoint just forwards the interaction to the Dashboard Alert Agent

    # Send interaction to Dashboard Alert Agent as a background task
    background_tasks.add_task(
        send_dashboard_interaction,
        interaction.notification_id,
        interaction.user_id,
        interaction.action
    )

    return {"status": "success"}


@router.get("/dashboard-alerts/", response_model=List[DashboardAlert])
def get_dashboard_alerts(user_id: int):
    """Get active dashboard alerts for a user."""
    from app.db.database import get_mongo_collection

    # Query MongoDB for active alerts
    alerts = list(get_mongo_collection("active_dashboard_alerts").find(
        {"user_id": user_id}
    ))

    return [
        DashboardAlert(
            id=str(alert["_id"]),
            notification_id=alert["notification_id"],
            user_id=alert["user_id"],
            title=alert["title"],
            content=alert["content"],
            type=alert["type"],
            created_at=alert["created_at"],
            expires_at=alert["expires_at"],
            is_read=alert["is_read"]
        )
        for alert in alerts
    ]


# System status route
@router.get("/system/status", response_model=SystemStatus)
def get_system_status():
    """Get the current status of the notification system."""
    # Get agent registry stats
    registry_stats = AgentRegistry.get_stats()

    # Get all registered agents
    agents = AgentRegistry.get_agents()

    # Format agent statuses
    agent_statuses = [
        {
            "agent_id": agent.agent_id,
            "agent_type": agent.agent_type,
            "agent_name": agent.agent_name,
            "status": "running" if agent.running else "stopped",
            "last_run_time": agent.last_run_time
        }
        for agent in agents
    ]

    # Return system status
    return {
        "agents": agent_statuses,
        "registered_agents": registry_stats["registered_agents"],
        "active_agent_types": registry_stats["active_agent_types"],
        "messages_delivered": registry_stats["messages_delivered"],
        "system_start_time": datetime.utcnow()  # This would be stored somewhere in a real app
    }


# Background task functions
async def send_notification_to_recommendation_system(notification_id: int):
    """Send a notification to the Recommendation System."""
    from app.db.database import get_db

    # Get notification details
    db = next(get_db())
    notification = db.query(Notification).filter(Notification.id == notification_id).first()

    if not notification:
        return

    # Find a Recommendation agent to send it to
    recommendation_agents = AgentRegistry.get_agents(AgentType.RECOMMENDATION)

    if not recommendation_agents:
        return

    # Send to the first available agent
    await recommendation_agents[0].send_message(AgentType.RECOMMENDATION, {
        "new_notification": {
            "id": notification.id,
            "user_id": notification.user_id,
            "type": notification.type,
            "content": notification.content,
            "scheduled_at": notification.scheduled_at
        }
    })


async def process_engagement(engagement_id: int, channel: str):
    """Process a notification engagement."""
    from app.db.database import get_db

    # Get engagement details
    db = next(get_db())
    engagement = db.query(NotificationEngagement).filter(NotificationEngagement.id == engagement_id).first()

    if not engagement:
        return

    # Get notification details
    notification = db.query(Notification).filter(Notification.id == engagement.notification_id).first()

    if not notification:
        return

    # Determine target agent based on channel
    if channel == NotificationChannel.EMAIL:
        target_agent_type = AgentType.EMAIL_ENGAGEMENT
    elif channel == NotificationChannel.PUSH:
        target_agent_type = AgentType.MOBILE_APP_EVENTS
    elif channel == NotificationChannel.SMS:
        target_agent_type = AgentType.SMS_INTERACTION
    elif channel == NotificationChannel.DASHBOARD:
        target_agent_type = AgentType.DASHBOARD_TRACKER
    else:
        return

    # Find an agent to send it to
    target_agents = AgentRegistry.get_agents(target_agent_type)

    if not target_agents:
        return

    # Send to the first available agent
    await target_agents[0].send_message(target_agent_type, {
        "engagement_event": {
            "notification_id": notification.id,
            "user_id": notification.user_id,
            "action": engagement.action,
            "timestamp": engagement.timestamp,
            "channel": channel,
            "meta_data": engagement.meta_data
        }
    })

    # Also send to A/B Testing agent for analysis
    ab_testing_agents = AgentRegistry.get_agents(AgentType.AB_TESTING)

    if ab_testing_agents:
        await ab_testing_agents[0].send_message(AgentType.AB_TESTING, {
            "engagement_event": {
                "notification_id": notification.id,
                "user_id": notification.user_id,
                "action": engagement.action,
                "timestamp": engagement.timestamp,
                "channel": channel
            }
        })


async def send_dashboard_interaction(notification_id: int, user_id: int, action: str):
    """Send a dashboard interaction to the Dashboard Alert Agent."""
    # Find a Dashboard Alert agent
    dashboard_agents = AgentRegistry.get_agents(AgentType.DASHBOARD_ALERT)

    if not dashboard_agents:
        return

    # Send to the first available agent
    await dashboard_agents[0].send_message(AgentType.DASHBOARD_ALERT, {
        "alert_interaction": {
            "notification_id": notification_id,
            "user_id": user_id,
            "action": action,
            "timestamp": datetime.utcnow()
        }
    })