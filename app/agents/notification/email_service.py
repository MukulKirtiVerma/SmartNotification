import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from loguru import logger
from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent
from app.db.database import get_db, get_mongo_collection
from app.db.models import Notification, User
from config.constants import AgentType, Collections, NotificationChannel


class EmailServiceAgent(BaseAgent):
    """
    Agent that handles email notification delivery.
    Receives delivery recommendations and sends personalized emails.
    """

    def __init__(self, name: str = "Email Service"):
        super().__init__(AgentType.EMAIL_SERVICE, name)
        self.pending_deliveries = []

    async def process(self):
        """
        Process pending email notifications and send them.
        """
        logger.debug(f"EmailServiceAgent {self.agent_id} processing")

        # Check for pending deliveries
        if self.pending_deliveries:
            await self._send_pending_emails()

    async def _send_pending_emails(self):
        """
        Send all pending email notifications.
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
                if not user or not user.email:
                    logger.error(f"User {notification.user_id} not found or has no email")
                    self.pending_deliveries.remove(delivery)
                    continue

                # Send the email
                email_id = await self._send_email(
                    user.email,
                    notification.title,
                    notification.content,
                    notification.metadata
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
                    "email_id": email_id
                })

                logger.info(f"Sent email notification {notification_id} to user {notification.user_id}")

                # Remove from pending
                self.pending_deliveries.remove(delivery)

            except Exception as e:
                logger.error(f"Error sending email notification {notification_id}: {str(e)}")

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

        # Send delivery results to Email Engagement Agent
        if delivery_results:
            await self.send_message(AgentType.EMAIL_ENGAGEMENT, {
                "delivery_data": delivery_results
            })

    async def _send_email(self, recipient: str, subject: str, content: str, metadata: Dict = None) -> str:
        """
        Actually send an email. In a real implementation, this would use an email service.

        Args:
            recipient (str): Recipient email address
            subject (str): Email subject
            content (str): Email content
            metadata (Dict, optional): Additional metadata. Defaults to None.

        Returns:
            str: Unique email ID for tracking
        """
        # In a real implementation, this would connect to an email provider
        # For demonstration purposes, we'll just log the email and generate a fake ID

        # Simulate email sending
        logger.debug(f"SIMULATED EMAIL: To: {recipient}, Subject: {subject}")
        logger.debug(f"Content: {content[:100]}...")

        # Generate a fake email ID for tracking
        email_id = f"email_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hash(recipient) % 10000}"

        # In a real implementation, we would do something like:
        """
        message = MIMEMultipart('alternative')
        message['Subject'] = subject
        message['From'] = 'notifications@example.com'
        message['To'] = recipient

        # Add tracking pixels/links if needed
        html_content = content

        text_part = MIMEText(content.strip_tags(), 'plain')
        html_part = MIMEText(html_content, 'html')

        message.attach(text_part)
        message.attach(html_part)

        with smtplib.SMTP('smtp.example.com', 587) as server:
            server.starttls()
            server.login('username', 'password')
            server.send_message(message)
        """

        # Add artificial delay to simulate actual sending
        await asyncio.sleep(0.1)

        return email_id

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

            # Only process email recommendations
            if recommendation["recommended_channel"] != NotificationChannel.EMAIL:
                return

            logger.info(f"Received email delivery recommendation for notification {recommendation['notification_id']}")

            # Add to pending deliveries
            self.pending_deliveries.append({
                "notification_id": recommendation["notification_id"],
                "user_id": recommendation["user_id"],
                "scheduled_time": recommendation["recommended_time"],
                "retry_count": 0
            })

            # Handle tracking pixel/link clicks
        elif "email_tracking_event" in message:
            event = message["email_tracking_event"]

            # Forward to Email Engagement Agent
            await self.send_message(AgentType.EMAIL_ENGAGEMENT, {
                "tracking_event": event
            })

            logger.debug(f"Forwarded email tracking event for notification {event.get('notification_id')}")