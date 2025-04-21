import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List

from loguru import logger
from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent
from app.db.database import get_db, get_mongo_collection
from app.db.models import Notification, User
from config.constants import AgentType, Collections, NotificationChannel


class DashboardAlertAgent(BaseAgent):
    """
    Agent that handles dashboard notification delivery.
    Manages in-app notifications shown on the user dashboard.
    """

    def __init__(self, name: str = "Dashboard Alert System"):
        super().__init__(AgentType.DASHBOARD_ALERT, name)
        self.pending_alerts = []
        self.active_alerts = get_mongo_collection("active_dashboard_alerts")

    async def process(self):
        """
        Process pending dashboard notifications and make them active.
        """
        logger.debug(f"DashboardAlertAgent {self.agent_id} processing")

        # Process pending alerts
        await self._process_pending_alerts()

        # Remove expired alerts
        await self._clean_expired_alerts()

    async def _process_pending_alerts(self):
        """
        Process pending dashboard alerts and make them active.
        """
        if not self.pending_alerts:
            return

        db = next(get_db())
        processed_alerts = []

        for alert in self.pending_alerts[:]:
            notification_id = alert["notification_id"]

            try:
                # Get notification details
                notification = db.query(Notification).filter(Notification.id == notification_id).first()
                if not notification:
                    logger.error(f"Notification {notification_id} not found")
                    self.pending_alerts.remove(alert)
                    continue

                # Create an active dashboard alert
                alert_doc = {
                    "notification_id": notification_id,
                    "user_id": notification.user_id,
                    "title": notification.title,
                    "content": notification.content,
                    "type": notification.type,
                    "created_at": datetime.utcnow(),
                    "expires_at": datetime.utcnow() + timedelta(days=7),  # Default expiration
                    "is_read": False,
                    "metadata": notification.metadata or {}
                }

                # Insert into active alerts collection
                self.active_alerts.insert_one(alert_doc)

                # Update notification status
                notification.is_sent = True
                notification.sent_at = datetime.utcnow()
                db.commit()

                # Record processing result
                processed_alerts.append({
                    "notification_id": notification_id,
                    "user_id": notification.user_id,
                    "status": "active",
                    "timestamp": datetime.utcnow()
                })

                logger.info(
                    f"Activated dashboard alert for notification {notification_id}, user {notification.user_id}")

                # Remove from pending
                self.pending_alerts.remove(alert)

            except Exception as e:
                logger.error(f"Error processing dashboard alert {notification_id}: {str(e)}")

                # Keep in pending for retry
                # Remove after too many retries
                alert["retry_count"] = alert.get("retry_count", 0) + 1
                if alert["retry_count"] > 3:
                    self.pending_alerts.remove(alert)

        # Send processing results to Dashboard Tracker Agent
        if processed_alerts:
            await self.send_message(AgentType.DASHBOARD_TRACKER, {
                "alert_data": processed_alerts
            })

    async def _clean_expired_alerts(self):
        """
        Remove expired dashboard alerts.
        """
        # Find and remove expired alerts
        result = self.active_alerts.delete_many({
            "expires_at": {"$lt": datetime.utcnow()}
        })

        if result.deleted_count > 0:
            logger.info(f"Removed {result.deleted_count} expired dashboard alerts")

    async def handle_message(self, message: Dict[str, Any], sender: Dict[str, Any]):
        """
        Handle messages from other agents.

        Args:
            message (Dict[str, Any]): The message content
            sender (Dict[str, Any]): Information about the sender
        """
        # Handle delivery recommendations
        if "delivery_recommendation" in message and sender.get("agent_type") == AgentType.RECOMMENDATION:
            recommendation = message["delivery_recommendation"]

            # Only process dashboard recommendations
            if recommendation["recommended_channel"] != NotificationChannel.DASHBOARD:
                return

            logger.info(f"Received dashboard alert recommendation for notification {recommendation['notification_id']}")

            # Add to pending alerts
            self.pending_alerts.append({
                "notification_id": recommendation["notification_id"],
                "user_id": recommendation["user_id"],
                "scheduled_time": recommendation["recommended_time"],
                "retry_count": 0
            })

        # Handle alert interactions
        elif "alert_interaction" in message:
            interaction = message["alert_interaction"]
            notification_id = interaction.get("notification_id")
            user_id = interaction.get("user_id")
            action = interaction.get("action")

            if not notification_id or not user_id or not action:
                logger.warning("Incomplete alert interaction data")
                return

            # Update alert status based on action
            if action == "read":
                self.active_alerts.update_one(
                    {"notification_id": notification_id, "user_id": user_id},
                    {"$set": {"is_read": True, "read_at": datetime.utcnow()}}
                )
            elif action == "dismiss":
                self.active_alerts.delete_one(
                    {"notification_id": notification_id, "user_id": user_id}
                )
            elif action == "click":
                self.active_alerts.update_one(
                    {"notification_id": notification_id, "user_id": user_id},
                    {"$set": {"is_clicked": True, "clicked_at": datetime.utcnow()}}
                )

            # Send interaction data to Dashboard Tracker Agent
            view_data = [{
                "user_id": user_id,
                "notification_id": notification_id,
                "action": action,
                "timestamp": datetime.utcnow()
            }]

            await self.send_message(AgentType.DASHBOARD_TRACKER, {
                "view_data": view_data
            })

            logger.debug(
                f"Processed dashboard alert interaction: user {user_id}, notification {notification_id}, action {action}")