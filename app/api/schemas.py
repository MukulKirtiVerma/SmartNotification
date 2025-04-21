from datetime import datetime
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, Field, EmailStr


# User schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        orm_mode = True


# Notification schemas
class NotificationBase(BaseModel):
    user_id: int
    type: str
    channel: str
    title: str
    content: str
    meta_data: Optional[Dict[str, Any]] = None


class NotificationCreate(NotificationBase):
    scheduled_at: Optional[datetime] = None


class Notification(NotificationBase):
    id: int
    is_sent: bool
    sent_at: Optional[datetime]
    created_at: datetime

    class Config:
        orm_mode = True


# Notification preference schemas
class NotificationPreferenceBase(BaseModel):
    user_id: int
    notification_type: str
    channel: str
    is_enabled: bool = True
    frequency: str = "normal"
    time_preference: Optional[Dict[str, Any]] = None


class NotificationPreferenceCreate(NotificationPreferenceBase):
    pass


class NotificationPreference(NotificationPreferenceBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True


# Engagement schemas
class EngagementCreate(BaseModel):
    notification_id: int
    action: str
    meta_data: Optional[Dict[str, Any]] = None


class Engagement(EngagementCreate):
    id: int
    timestamp: datetime

    class Config:
        orm_mode = True


# A/B Test schemas
class ABTestBase(BaseModel):
    name: str
    description: Optional[str] = None
    variants: Dict[str, Any]
    metrics: Optional[List[str]] = None


class ABTestCreate(ABTestBase):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class ABTest(ABTestBase):
    id: int
    is_active: bool
    start_date: datetime
    end_date: Optional[datetime]
    created_at: datetime

    class Config:
        orm_mode = True


# Dashboard Alert schemas
class DashboardAlertBase(BaseModel):
    notification_id: int
    user_id: int
    action: str  # read, dismiss, click


class DashboardAlertCreate(DashboardAlertBase):
    pass


class DashboardAlert(BaseModel):
    id: str
    notification_id: int
    user_id: int
    title: str
    content: str
    type: str
    created_at: datetime
    expires_at: datetime
    is_read: bool

    class Config:
        orm_mode = True


# System status schemas
class AgentStatus(BaseModel):
    agent_id: str
    agent_type: str
    agent_name: str
    status: str
    last_run_time: Optional[datetime] = None

class SystemStatus(BaseModel):
    agents: List[AgentStatus]
    registered_agents: int
    active_agent_types: List[str]
    messages_delivered: int
    system_start_time: datetime