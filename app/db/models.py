# app/db/models.py
# Add the code for this file here
from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime, Float, Text, Enum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

from app.db.database import Base
from config.constants import NotificationType, NotificationChannel, EngagementLevel

class User(Base):
    """User model for storing user information."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    notifications = relationship("Notification", back_populates="user")
    notification_preferences = relationship("NotificationPreference", back_populates="user")
    user_sessions = relationship("UserSession", back_populates="user")


class Notification(Base):
    """Notification model for storing notification information."""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(String, index=True)
    channel = Column(String, index=True)
    title = Column(String)
    content = Column(Text)
    meta_data = Column(JSON, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    is_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="notifications")
    engagements = relationship("NotificationEngagement", back_populates="notification")


class NotificationEngagement(Base):
    """Model for tracking user engagements with notifications."""
    __tablename__ = "notification_engagements"

    id = Column(Integer, primary_key=True, index=True)
    notification_id = Column(Integer, ForeignKey("notifications.id"))
    action = Column(String, index=True)  # open, click, dismiss, etc.
    timestamp = Column(DateTime, default=datetime.utcnow)
    meta_data = Column(JSON, nullable=True)

    # Relationships
    notification = relationship("Notification", back_populates="engagements")


class NotificationPreference(Base):
    """Model for storing user notification preferences."""
    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    notification_type = Column(String, index=True)
    channel = Column(String, index=True)
    is_enabled = Column(Boolean, default=True)
    frequency = Column(String, default="normal")  # low, normal, high
    time_preference = Column(JSON, nullable=True)  # preferred times of day
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="notification_preferences")


class UserSession(Base):
    """Model for tracking user sessions."""
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    session_id = Column(String, unique=True, index=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    # Relationships
    user = relationship("User", back_populates="user_sessions")
    page_views = relationship("PageView", back_populates="session")


class PageView(Base):
    """Model for tracking user page views."""
    __tablename__ = "page_views"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("user_sessions.id"))
    url = Column(String)
    view_time = Column(DateTime, default=datetime.utcnow)
    duration = Column(Integer, nullable=True)  # in seconds
    meta_data = Column(JSON, nullable=True)

    # Relationships
    session = relationship("UserSession", back_populates="page_views")


class ABTest(Base):
    """Model for tracking A/B tests."""
    __tablename__ = "ab_tests"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(Text, nullable=True)
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    metrics = Column(JSON, nullable=True)  # what metrics to track
    variants = Column(JSON)  # different variants being tested
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    assignments = relationship("ABTestAssignment", back_populates="ab_test")


class ABTestAssignment(Base):
    """Model for tracking which users are assigned to which A/B test variants."""
    __tablename__ = "ab_test_assignments"

    id = Column(Integer, primary_key=True, index=True)
    ab_test_id = Column(Integer, ForeignKey("ab_tests.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    variant = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    ab_test = relationship("ABTest", back_populates="assignments")


class UserMetric(Base):
    """Model for storing aggregated user metrics."""
    __tablename__ = "user_metrics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    metric_type = Column(String, index=True)  # engagement_rate, session_frequency, etc.
    value = Column(Float)
    period_start = Column(DateTime)
    period_end = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentLog(Base):
    """Model for logging agent activities."""
    __tablename__ = "agent_logs"

    id = Column(Integer, primary_key=True, index=True)
    agent_type = Column(String, index=True)
    action = Column(String, index=True)
    status = Column(String)  # success, failure, etc.
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)