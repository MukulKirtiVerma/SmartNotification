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


class MobileAppEventsAgent(BaseAgent):
    """
    Agent that tracks user interactions with mobile push notifications.
    Collects data on opens, reactions, and in-app behavior related to notifications.
    """

    def __init__(self, name: str = "Mobile App Events Tracker"):
        super().__init__(AgentType.MOBILE_APP_EVENTS, name)
        self.user_events_collection = get_mongo_collection(Collections.USER_EVENTS)

    async def process(self):
        """
        Process mobile app events and collect metrics.
        """
        logger.debug(f"MobileAppEventsAgent {self.agent_id} processing")

        # Get recent mobile app events from database
        try:
            db = next(get_db())
            await self._process_recent_engagements(db)
            await self._calculate_mobile_metrics(db)

            # Send processed data to analysis agents
            await self._send_data_to_analysis_agents()

        except Exception as e:
            logger.error(f"Error processing mobile app events: {str(e)}")
            raise

    async def _process_recent_engagements(self, db: Session):
        """
        Process recent mobile push notification engagements.

        Args:
            db (Session): Database session
        """
        # Define the cutoff time (e.g., last hour)
        cutoff_time = datetime.utcnow() - timedelta(hours=1)

        # Query recent mobile notification engagements
        recent_engagements = db.query(NotificationEngagement).join(Notification).filter(
            NotificationEngagement.timestamp >= cutoff_time,
            Notification.channel == NotificationChannel.PUSH
        ).all()

        # Process each engagement
        for engagement in recent_engagements:
            notification = engagement.notification

            # Create an event document
            event = {
                "user_id": notification.user_id,
                "event_type": "push_engagement",
                "channel": NotificationChannel.PUSH,
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
            self.user_events_collection.insert_one(event)

            logger.debug(
                f"Processed mobile push engagement for user {notification.user_id}, action: {engagement.action}")

    async def _calculate_mobile_metrics(self, db: Session):
        """
        Calculate mobile push notification engagement metrics for users.

        Args:
            db (Session): Database session
        """
        # Define the cutoff time (e.g., last week)
        cutoff_time = datetime.utcnow() - timedelta(days=7)

        # Query users who have received mobile push notifications
        active_users = db.query(User.id).join(Notification).filter(
            Notification.channel == NotificationChannel.PUSH,
            Notification.sent_at >= cutoff_time
        ).distinct().all()

        active_user_ids = [user.id for user in active_users]

        for user_id in active_user_ids:
            # Get all sent notifications for this user
            sent_notifications = db.query(Notification).filter(
                Notification.user_id == user_id,
                Notification.channel == NotificationChannel.PUSH,
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

            dismisses = db.query(func.count(NotificationEngagement.id)).filter(
                NotificationEngagement.notification_id.in_(notification_ids),
                NotificationEngagement.action == EngagementAction.DISMISS
            ).scalar() or 0

            # Calculate metrics
            open_rate = opens / total_sent if total_sent > 0 else 0
            click_rate = clicks / total_sent if total_sent > 0 else 0
            dismiss_rate = dismisses / total_sent if total_sent > 0 else 0

            # Create a metrics document
            metrics = {
                "user_id": user_id,
                "metric_type": "mobile_push_engagement",
                "period_start": cutoff_time,
                "period_end": datetime.utcnow(),
                "metrics": {
                    "total_sent": total_sent,
                    "total_opens": opens,
                    "total_clicks": clicks,
                    "total_dismisses": dismisses,
                    "open_rate": open_rate,
                    "click_rate": click_rate,
                    "dismiss_rate": dismiss_rate
                }
            }

            # Store the metrics in MongoDB
            get_mongo_collection("user_metrics").insert_one(metrics)

            logger.debug(
                f"Calculated mobile metrics for user {user_id}: {open_rate:.1%} open rate, {click_rate:.1%} click rate")

    async def _send_data_to_analysis_agents(self):
        """
        Send collected data to analysis agents.
        """
        # Get recent mobile metrics
        metrics = list(get_mongo_collection("user_metrics").find(
            {"metric_type": "mobile_push_engagement"},
            sort=[("period_end", -1)],
            limit=100
        ))

        # Send to Frequency Analysis Agent
        frequency_data = {
            "mobile_engagement": [
                {
                    "user_id": metric["user_id"],
                    "timestamp": metric["period_end"],
                    "open_rate": metric["metrics"]["open_rate"],
                    "click_rate": metric["metrics"]["click_rate"],
                    "dismiss_rate": metric["metrics"]["dismiss_rate"]
                }
                for metric in metrics
            ],
            "channel": NotificationChannel.PUSH
        }
        await self.send_message(AgentType.FREQUENCY_ANALYSIS, frequency_data)

        # Send to Channel Analysis Agent
        channel_data = {
            "channel_engagement": [
                {
                    "user_id": metric["user_id"],
                    "timestamp": metric["period_end"],
                    "channel": NotificationChannel.PUSH,
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

        logger.info(f"Sent mobile metrics for {len(metrics)} users to analysis agents")

    async def _get_notification_type_metrics(self) -> List[Dict[str, Any]]:
        """
        Get engagement metrics broken down by notification type.

        Returns:
            List[Dict[str, Any]]: List of notification type metrics by user
        """
        # Get all mobile push engagement events from the past week
        cutoff_time = datetime.utcnow() - timedelta(days=7)

        pipeline = [
            {
                "$match": {
                    "event_type": "push_engagement",
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
                                    actions.get(EngagementAction.OPEN, 0) * 0.5 -
                                    actions.get(EngagementAction.DISMISS,
                                                0) * 0.2) / total_actions if total_actions > 0 else 0

                formatted_results.append({
                    "user_id": user_id,
                    "notification_type": notification_type,
                    "channel": NotificationChannel.PUSH,
                    "engagement_score": engagement_score,
                    "actions": actions
                })

        return formatted_results

    def _calculate_engagement_level(self, metrics: Dict[str, Any]) -> float:
        """
        Calculate an engagement level score from mobile metrics.

        Args:
            metrics (Dict[str, Any]): The metrics to calculate from

        Returns:
            float: Engagement level score (0-1)
        """
        # Weighted score based on open, click, and dismiss rates
        open_score = metrics["open_rate"] * 0.3
        click_score = metrics["click_rate"] * 0.5
        dismiss_penalty = metrics["dismiss_rate"] * 0.2

        return max(0, open_score + click_score - dismiss_penalty)

    async def handle_message(self, message: Dict[str, Any], sender: Dict[str, Any]):
            """
            Handle messages from other agents.

            Args:
                message (Dict[str, Any]): The message content
                sender (Dict[str, Any]): Information about the sender
            """
            # Feedback from Push Notification Service
            if "delivery_data" in message and sender.get("agent_type") == AgentType.PUSH_NOTIFICATION:
                delivery_data = message["delivery_data"]

                # Store delivery confirmation data
                for delivery in delivery_data:
                    event = {
                        "user_id": delivery["user_id"],
                        "event_type": "push_delivery",
                        "channel": NotificationChannel.PUSH,
                        "timestamp": delivery["timestamp"],
                        "details": {
                            "notification_id": delivery["notification_id"],
                            "status": delivery["status"],
                            "device_info": delivery.get("device_info", {})
                        }
                    }
                    self.user_events_collection.insert_one(event)

                logger.info(f"Processed {len(delivery_data)} push notification delivery events")