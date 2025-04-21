import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List

from loguru import logger
from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent
from app.db.database import get_db, get_mongo_collection
from app.db.models import Notification, User
from config.constants import AgentType, Collections, NotificationChannel


class PushNotificationAgent(BaseAgent):
    """
    Agent that handles mobile push notification delivery.
    Receives delivery recommendations and sends personalized push notifications.
    """

    def __init__(self, name: str = "Push Notification Service"):
        super().__init__(AgentType.PUSH_NOTIFICATION, name)
        self.pending_deliveries = []

    async def process(self):
        """
        Process pending push notifications and send them.
        """
        logger.debug(f"PushNotificationAgent {self.agent_id} processing")

        # Check for pending deliveries
        if self.pending_deliveries:
            await self._send_pending_push_notifications()

    async def _send_pending_push_notifications(self):
        """
        Send all pending push notifications.
        """
        if not self.pending_deliveries:
            return

        db = next(get_db())
        delivery_results = []

        for delivery in self.pending_deliveries[:]:
            notification_id = delivery["notification_id"]

            try:
                # Get notification details
                notification = db.query(Notification).filter(Notification.id == notification_id).first()
                if not notification:
                    logger.error(f"Notification {notification_id} not found")
                    self.pending_deliveries.remove(delivery)
                    continue

                # Get user details
                user = db.query(User).filter(User.id == notification.user_id).first()
                if not user:
                    logger.error(f"User {notification.user_id} not found")
                    self.pending_deliveries.remove(delivery)
                    continue

                # Get user's device tokens from a separate table or user metadata
                device_tokens = self._get_user_device_tokens(user.id, db)

                if not device_tokens:
                    logger.warning(f"No device tokens found for user {user.id}")
                    self.pending_deliveries.remove(delivery)
                    continue

                # Send the push notifications to all user devices
                for token in device_tokens:
                    await self._send_push_notification(
                        token,
                        notification.title,
                        notification.content,
                        notification.metadata,
                        notification.id
                    )

                # Update notification status
                notification.is_sent = True
                notification.sent_at = datetime.utcnow()
                db.commit()

                # Record delivery result
                delivery_results.append({
                    "notification_id": notification_id,
                    "user_id": notification.user_id,
                    "status": "delivered",
                    "timestamp": datetime.utcnow(),
                    "device_count": len(device_tokens)
                })

                logger.info(
                    f"Sent push notification {notification_id} to user {notification.user_id} ({len(device_tokens)} devices)")

                # Remove from pending
                self.pending_deliveries.remove(delivery)

            except Exception as e:
                logger.error(f"Error sending push notification {notification_id}: {str(e)}")

                # Record delivery failure
                delivery_results.append({
                    "notification_id": notification_id,
                    "user_id": notification.user_id if notification else None,
                    "status": "failed",
                    "timestamp": datetime.utcnow(),
                    "error": str(e)
                })

                # Keep in pending for retry
                # Remove after too many retries
                delivery["retry_count"] = delivery.get("retry_count", 0) + 1
                if delivery["retry_count"] > 3:
                    self.pending_deliveries.remove(delivery)

        # Send delivery results to Mobile App Events Agent
        if delivery_results:
            await self.send_message(AgentType.MOBILE_APP_EVENTS, {
                "delivery_data": delivery_results
            })

    def _get_user_device_tokens(self, user_id: int, db: Session) -> List[str]:
        """
        Get a user's device tokens for push notifications.

        Args:
            user_id (int): User ID
            db (Session): Database session

        Returns:
            List[str]: List of device tokens
        """
        # In a real implementation, we would query a table of user devices
        # For demonstration, we'll return a fake token
        return [f"device_token_{user_id}_1", f"device_token_{user_id}_2"]

    async def _send_push_notification(self, device_token: str, title: str, message: str, metadata: Dict = None,
                                      notification_id: int = None) -> bool:
        """
        Actually send a push notification. In a real implementation, this would use a push service.

        Args:
            device_token (str): Device token
            title (str): Notification title
            message (str): Notification message
            metadata (Dict, optional): Additional metadata. Defaults to None.
            notification_id (int, optional): Notification ID for tracking. Defaults to None.

        Returns:
            bool: Success flag
        """
        # In a real implementation, this would connect to a push provider like Firebase
        # For demonstration purposes, we'll just log the notification

        # Simulate push notification sending
        logger.debug(f"SIMULATED PUSH: To: {device_token}, Title: {title}")
        logger.debug(f"Message: {message[:100]}...")

        # In a real implementation, we would do something like:
        """
        from firebase_admin import messaging

        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=message
            ),
            token=device_token,
            data={
                'notification_id': str(notification_id),
                'type': metadata.get('type', '')
            }
        )

        response = messaging.send(message)
        """

        # Add artificial delay to simulate actual sending
        await asyncio.sleep(0.1)

        return True

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

            # Only process push recommendations
            if recommendation["recommended_channel"] != NotificationChannel.PUSH:
                return

            logger.info(f"Received push delivery recommendation for notification {recommendation['notification_id']}")

            # Add to pending deliveries
            self.pending_deliveries.append({
                "notification_id": recommendation["notification_id"],
                "user_id": recommendation["user_id"],
                "scheduled_time": recommendation["recommended_time"],
                "retry_count": 0
            })

        # Handle push notification feedback from the mobile app
        elif "push_feedback" in message:
            feedback = message["push_feedback"]

            # Forward to Mobile App Events Agent
            await self.send_message(AgentType.MOBILE_APP_EVENTS, {
                "push_feedback": feedback
            })

            logger.debug(f"Forwarded push feedback for notification {feedback.get('notification_id')}")