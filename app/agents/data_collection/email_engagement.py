import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List

from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.agents.base_agent import BaseAgent
from app.db.database import get_db, get_mongo_collection
from app.db.models import User, Notification, NotificationEngagement
from config.constants import AgentType, Collections, NotificationChannel, EngagementAction


class EmailEngagementAgent(BaseAgent):
    """
    Agent that tracks user engagement with email notifications.
    Collects data on opens, clicks, and other interactions with email notifications.
    """

    def __init__(self, name: str = "Email Engagement Tracker"):
        super().__init__(AgentType.EMAIL_ENGAGEMENT, name)
        self.user_events_collection = get_mongo_collection(Collections.USER_EVENTS)

    async def process(self):
        """
        Process email engagement data and collect metrics.
        """
        logger.debug(f"EmailEngagementAgent {self.agent_id} processing")

        # Get recent email engagements from database
        try:
            db = next(get_db())
            await self._process_recent_engagements(db)
            await self._calculate_email_metrics(db)

            # Send processed data to analysis agents
            await self._send_data_to_analysis_agents()

        except Exception as e:
            logger.error(f"Error processing email engagement: {str(e)}")
            raise

    async def _process_recent_engagements(self, db: Session):
        """
        Process recent email engagements to collect user interaction data.

        Args:
            db (Session): Database session
        """
        # Define the cutoff time (e.g., last hour)
        cutoff_time = datetime.utcnow() - timedelta(hours=1)

        # Query recent email notification engagements
        recent_engagements = db.query(NotificationEngagement).join(Notification).filter(
            NotificationEngagement.timestamp >= cutoff_time,
            Notification.channel == NotificationChannel.EMAIL
        ).all()

        # Process each engagement
        for engagement in recent_engagements:
            notification = engagement.notification

            # Create an event document
            event = {
                "user_id": notification.user_id,
                "event_type": "email_engagement",
                "channel": NotificationChannel.EMAIL,
                "timestamp": engagement.timestamp,
                "details": {
                    "notification_id": notification.id,
                    "notification_type": notification.type,
                    "action": engagement.action,
                    "engagement_id": engagement.id
                },
                "meta_data": engagement.meta_data or {}
            }

            # Store the event in MongoDB
            try:
                self.user_events_collection.insert_one(event)
            except Exception as e:
                print(e)

            logger.debug(f"Processed email engagement for user {notification.user_id}, action: {engagement.action}")

    async def _calculate_email_metrics(self, db: Session):
        """
        Calculate email engagement metrics for users.

        Args:
            db (Session): Database session
        """
        # Define the cutoff time (e.g., last week)
        cutoff_time = datetime.utcnow() - timedelta(days=7)

        # Query users who have received email notifications
        active_users = db.query(User.id).join(Notification).filter(
            Notification.channel == NotificationChannel.EMAIL,
            Notification.sent_at >= cutoff_time
        ).distinct().all()

        active_user_ids = [user.id for user in active_users]

        for user_id in active_user_ids:
            # Get all sent notifications for this user
            sent_notifications = db.query(Notification).filter(
                Notification.user_id == user_id,
                Notification.channel == NotificationChannel.EMAIL,
                Notification.sent_at >= cutoff_time,
                Notification.is_sent == True
            ).all()

            # Count total sent
            total_sent = len(sent_notifications)

            if total_sent == 0:
                continue

            # Get notification IDs
            notification_ids = [n.id for n in sent_notifications]

            # Count engagements by type
            opens = db.query(func.count(NotificationEngagement.id)).filter(
                NotificationEngagement.notification_id.in_(notification_ids),
                NotificationEngagement.action == EngagementAction.OPEN
            ).scalar() or 0

            clicks = db.query(func.count(NotificationEngagement.id)).filter(
                NotificationEngagement.notification_id.in_(notification_ids),
                NotificationEngagement.action == EngagementAction.CLICK
            ).scalar() or 0

            # Calculate metrics
            open_rate = opens / total_sent if total_sent > 0 else 0
            click_rate = clicks / total_sent if total_sent > 0 else 0
            click_to_open_rate = clicks / opens if opens > 0 else 0

            # Create a metrics document
            metrics = {
                "user_id": user_id,
                "metric_type": "email_engagement",
                "period_start": cutoff_time,
                "period_end": datetime.utcnow(),
                "metrics": {
                    "total_sent": total_sent,
                    "total_opens": opens,
                    "total_clicks": clicks,
                    "open_rate": open_rate,
                    "click_rate": click_rate,
                    "click_to_open_rate": click_to_open_rate
                }
            }

            # Store the metrics in MongoDB
            get_mongo_collection("user_metrics").insert_one(metrics)

            logger.debug(
                f"Calculated email metrics for user {user_id}: {open_rate:.1%} open rate, {click_rate:.1%} click rate")

    async def _send_data_to_analysis_agents(self):
        """
        Send collected data to analysis agents.
        """
        # Get recent email metrics
        metrics = list(get_mongo_collection("user_metrics").find(
            {"metric_type": "email_engagement"},
            sort=[("period_end", -1)],
            limit=100
        ))

        # Send to Frequency Analysis Agent
        frequency_data = {
            "email_engagement": [
                {
                    "user_id": metric["user_id"],
                    "timestamp": metric["period_end"],
                    "open_rate": metric["metrics"]["open_rate"],
                    "click_rate": metric["metrics"]["click_rate"]
                }
                for metric in metrics
            ],
            "channel": NotificationChannel.EMAIL
        }
        await self.send_message(AgentType.FREQUENCY_ANALYSIS, frequency_data)

        # Send to Channel Analysis Agent
        channel_data = {
            "channel_engagement": [
                {
                    "user_id": metric["user_id"],
                    "timestamp": metric["period_end"],
                    "channel": NotificationChannel.EMAIL,
                    "engagement_level": self._calculate_engagement_level(metric["metrics"])
                }
                for metric in metrics
            ]
        }
        await self.send_message(AgentType.CHANNEL_ANALYSIS, channel_data)

        # Get notification type engagement data
        type_metrics = await self._get_notification_type_metrics()

        # Send to Type Analysis Agent
        type_data = {
            "notification_type_engagement": type_metrics
        }
        await self.send_message(AgentType.TYPE_ANALYSIS, type_data)

        logger.info(f"Sent email metrics for {len(metrics)} users to analysis agents")

    async def _get_notification_type_metrics(self) -> List[Dict[str, Any]]:
        """
        Get engagement metrics broken down by notification type.

        Returns:
            List[Dict[str, Any]]: List of notification type metrics by user
        """
        # Get all email engagement events from the past week
        cutoff_time = datetime.utcnow() - timedelta(days=7)

        pipeline = [
            {
                "$match": {
                    "event_type": "email_engagement",
                    "timestamp": {"$gte": cutoff_time}
                }
            },
            {
                "$group": {
                    "_id": {
                        "user_id": "$user_id",
                        "notification_type": "$details.notification_type",
                        "action": "$details.action"
                    },
                    "count": {"$sum": 1}
                }
            },
            {
                "$group": {
                    "_id": {
                        "user_id": "$_id.user_id",
                        "notification_type": "$_id.notification_type"
                    },
                    "actions": {
                        "$push": {
                            "action": "$_id.action",
                            "count": "$count"
                        }
                    }
                }
            },
            {
                "$group": {
                    "_id": "$_id.user_id",
                    "types": {
                        "$push": {
                            "type": "$_id.notification_type",
                            "actions": "$actions"
                        }
                    }
                }
            }
        ]

        # Execute the aggregation pipeline
        results = list(self.user_events_collection.aggregate(pipeline))

        # Format the results for the Type Analysis Agent
        formatted_results = []
        for user_result in results:
            user_id = user_result["_id"]

            for type_data in user_result["types"]:
                notification_type = type_data["type"]
                actions = {action["action"]: action["count"] for action in type_data["actions"]}

                # Calculate engagement metrics for this notification type
                total_actions = sum(actions.values())
                engagement_score = (actions.get(EngagementAction.CLICK, 0) * 1.0 +
                                    actions.get(EngagementAction.OPEN,
                                                0) * 0.5) / total_actions if total_actions > 0 else 0

                formatted_results.append({
                    "user_id": user_id,
                    "notification_type": notification_type,
                    "channel": NotificationChannel.EMAIL,
                    "engagement_score": engagement_score,
                    "actions": actions
                })

        return formatted_results

    def _calculate_engagement_level(self, metrics: Dict[str, Any]) -> float:
        """
        Calculate an engagement level score from email metrics.

        Args:
            metrics (Dict[str, Any]): The metrics to calculate from

        Returns:
            float: Engagement level score (0-1)
        """
        # Weighted score based on open and click rates
        open_score = metrics["open_rate"] * 0.4
        click_score = metrics["click_rate"] * 0.6

        return open_score + click_score

    async def handle_message(self, message: Dict[str, Any], sender: Dict[str, Any]):
        """
        Handle messages from other agents.

        Args:
            message (Dict[str, Any]): The message content
            sender (Dict[str, Any]): Information about the sender
        """
        # Feedback from Email Service
        if "delivery_data" in message and sender.get("agent_type") == AgentType.EMAIL_SERVICE:
            delivery_data = message["delivery_data"]

            # Store delivery confirmation data
            for delivery in delivery_data:
                event = {
                    "user_id": delivery["user_id"],
                    "event_type": "email_delivery",
                    "channel": NotificationChannel.EMAIL,
                    "timestamp": delivery["timestamp"],
                    "details": {
                        "notification_id": delivery["notification_id"],
                        "status": delivery["status"],
                        "email_id": delivery.get("email_id")
                    }
                }
                self.user_events_collection.insert_one(event)

            logger.info(f"Processed {len(delivery_data)} email delivery events")