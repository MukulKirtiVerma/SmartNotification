"""
Constants used throughout the application.
"""


# Notification types
class NotificationType:
    SHIPMENT = "shipment"
    PACKING = "packing"
    DELIVERY = "delivery"
    PAYMENT = "payment"
    ORDER_CONFIRMATION = "order_confirmation"
    RETURN = "return"
    PROMOTION = "promotion"
    PRICE_DROP = "price_drop"
    RESTOCK = "restock"

    # List of all notification types
    ALL = [
        SHIPMENT, PACKING, DELIVERY, PAYMENT, ORDER_CONFIRMATION,
        RETURN, PROMOTION, PRICE_DROP, RESTOCK
    ]


# Notification channels
class NotificationChannel:
    EMAIL = "email"
    PUSH = "push"
    SMS = "sms"
    DASHBOARD = "dashboard"

    # List of all notification channels
    ALL = [EMAIL, PUSH, SMS, DASHBOARD]


# User engagement levels
class EngagementLevel:
    VERY_LOW = "very_low"  # Almost never engages
    LOW = "low"  # Rarely engages
    MEDIUM = "medium"  # Sometimes engages
    HIGH = "high"  # Often engages
    VERY_HIGH = "very_high"  # Almost always engages

    # List of all engagement levels
    ALL = [VERY_LOW, LOW, MEDIUM, HIGH, VERY_HIGH]


# Engagement actions
class EngagementAction:
    OPEN = "open"  # Opened notification
    CLICK = "click"  # Clicked on notification
    DISMISS = "dismiss"  # Dismissed notification
    MUTE = "mute"  # Muted specific notification type
    UNSUBSCRIBE = "unsubscribe"  # Unsubscribed from all notifications

    # List of all engagement actions
    ALL = [OPEN, CLICK, DISMISS, MUTE, UNSUBSCRIBE]


# Time of day ranges for notification delivery
class TimeOfDay:
    EARLY_MORNING = "early_morning"  # 5:00 - 8:00
    MORNING = "morning"  # 8:00 - 12:00
    AFTERNOON = "afternoon"  # 12:00 - 17:00
    EVENING = "evening"  # 17:00 - 20:00
    NIGHT = "night"  # 20:00 - 23:00
    LATE_NIGHT = "late_night"  # 23:00 - 5:00

    # List of all time ranges
    ALL = [EARLY_MORNING, MORNING, AFTERNOON, EVENING, NIGHT, LATE_NIGHT]

    # Time range boundaries in hours (24-hour format)
    BOUNDARIES = {
        EARLY_MORNING: (5, 8),
        MORNING: (8, 12),
        AFTERNOON: (12, 17),
        EVENING: (17, 20),
        NIGHT: (20, 23),
        LATE_NIGHT: (23, 5)
    }


# Database collection names for MongoDB
class Collections:
    USER_EVENTS = "user_events"
    NOTIFICATION_HISTORY = "notification_history"
    USER_PROFILES = "user_profiles"
    AGENT_LOGS = "agent_logs"
    AB_TEST_RESULTS = "ab_test_results"


# Agent types
class AgentType:
    # Data Collection Layer
    DASHBOARD_TRACKER = "dashboard_tracker"
    EMAIL_ENGAGEMENT = "email_engagement"
    MOBILE_APP_EVENTS = "mobile_app_events"
    SMS_INTERACTION = "sms_interaction"

    # Analysis Layer
    FREQUENCY_ANALYSIS = "frequency_analysis"
    TYPE_ANALYSIS = "type_analysis"
    CHANNEL_ANALYSIS = "channel_analysis"

    # Decision Engine
    USER_PROFILE = "user_profile"
    RECOMMENDATION = "recommendation"
    AB_TESTING = "ab_testing"

    # Notification Management
    EMAIL_SERVICE = "email_service"
    PUSH_NOTIFICATION = "push_notification"
    SMS_GATEWAY = "sms_gateway"
    DASHBOARD_ALERT = "dashboard_alert"

    # Group by layer
    DATA_COLLECTION = [DASHBOARD_TRACKER, EMAIL_ENGAGEMENT, MOBILE_APP_EVENTS, SMS_INTERACTION]
    ANALYSIS = [FREQUENCY_ANALYSIS, TYPE_ANALYSIS, CHANNEL_ANALYSIS]
    DECISION_ENGINE = [USER_PROFILE, RECOMMENDATION, AB_TESTING]
    NOTIFICATION_MANAGEMENT = [EMAIL_SERVICE, PUSH_NOTIFICATION, SMS_GATEWAY, DASHBOARD_ALERT]

    # All agent types
    ALL = DATA_COLLECTION + ANALYSIS + DECISION_ENGINE + NOTIFICATION_MANAGEMENT