import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List

from loguru import logger
from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent
from app.db.database import get_db, get_mongo_collection
from app.db.models import Notification, User
from config.constants import AgentType, Collections, NotificationChannel


class SMSGatewayAgent(BaseAgent):
    """
    Agent that handles SMS notification delivery.
    Receives delivery recommendations and sends personalized SMS messages.
    """

    def __init__(self, name: str = "SMS Gateway"):
        super().__init__(AgentType.SMS_GATEWAY, name)
        self.pending_deliveries = []

    async def process(self):
        """
        Process pending SMS notifications and send them.
        """
        logger.debug(f"SMSGatewayAgent {self.agent_id} processing")

        # Check for pending deliveries
        if self.pending_deliveries:
            await self._send_pending_sms()

    async def _send_pending_sms(self):
        """
        Send all pending SMS notifications.
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

                # Get user's phone number
                phone_number = self._get_user_phone_number(user.id, db)

                if not phone_number:
                    logger.warning(f"No phone number found for user {user.id}")
                    self.pending_deliveries.remove(delivery)
                    continue

                # Send the SMS
                sms_id = await self._send_sms(
                    phone_number,
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
                    "sms_id": sms_id,
                    "provider": "twilio"  # Or whatever provider is being used
                })

                logger.info(f"Sent SMS notification {notification_id} to user {notification.user_id}")

                # Remove from pending
                self.pending_deliveries.remove(delivery)

            except Exception as e:
                logger.error(f"Error sending SMS notification {notification_id}: {str(e)}")

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

        # Send delivery results to SMS Interaction Agent
        if delivery_results:
            await self.send_message(AgentType.SMS_INTERACTION, {
                "delivery_data": delivery_results
            })

    def _get_user_phone_number(self, user_id: int, db: Session) -> str:
        """
        Get a user's phone number for SMS.

        Args:
            user_id (int): User ID
            db (Session): Database session

        Returns:
            str: Phone number
        """
        # In a real implementation, we would query the user's profile
        # For demonstration, we'll return a fake phone number
        return f"+1555{user_id:08d}"

    async def _send_sms(self, phone_number: str, message: str, metadata: Dict = None,
                        notification_id: int = None) -> str:
        """
        Actually send an SMS. In a real implementation, this would use an SMS service.

        Args:
            phone_number (str): Recipient phone number
            message (str): SMS message
            metadata (Dict, optional): Additional metadata. Defaults to None.
            notification_id (int, optional): Notification ID for tracking. Defaults to None.

        Returns:
            str: Unique SMS ID for tracking
        """
        # In a real implementation, this would connect to an SMS provider like Twilio
        # For demonstration purposes, we'll just log the SMS

        # Simulate SMS sending
        logger.debug(f"SIMULATED SMS: To: {phone_number}")
        logger.debug(f"Message: {message[:100]}...")

        # In a real implementation, we would do something like:
        """
        from twilio.rest import Client

        client = Client(account_sid, auth_token)

        message = client.messages.create(
            body=message,
            from_='+15551234567',
            to=phone_number,
            status_callback='https://example.com/sms/callback'
        )

        return message.sid
        """

        # Generate a fake SMS ID for tracking
        sms_id = f"sms_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hash(phone_number) % 10000}"

        # Add artificial delay to simulate actual sending
        await asyncio.sleep(0.1)

        return sms_id

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

            # Only process SMS recommendations
            if recommendation["recommended_channel"] != NotificationChannel.SMS:
                return

            logger.info(f"Received SMS delivery recommendation for notification {recommendation['notification_id']}")

            # Add to pending deliveries
            self.pending_deliveries.append({
                "notification_id": recommendation["notification_id"],
                "user_id": recommendation["user_id"],
                "scheduled_time": recommendation["recommended_time"],
                "retry_count": 0
            })

        # Handle SMS responses
        elif "sms_response" in message:
            response = message["sms_response"]

            # Forward to SMS Interaction Agent
            await self.send_message(AgentType.SMS_INTERACTION, {
                "response_data": [response]
            })

            logger.debug(f"Forwarded SMS response from user {response.get('user_id')}")