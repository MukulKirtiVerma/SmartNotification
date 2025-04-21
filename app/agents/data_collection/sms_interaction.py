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


class SMSInteractionAgent(BaseAgent):
    """
    Agent that tracks user interaction with SMS notifications.
    Collects data on delivery confirmations and responses to SMS notifications.
    """

    def __init__(self, name: str = "SMS Interaction Tracker"):
        super().__init__(AgentType.SMS_INTERACTION, name)
        self.user_events_collection = get_mongo_collection(Collections.USER_EVENTS)

    async def process(self):
        """
        Process SMS interaction data and collect metrics.
        """
        logger.debug(f"SMSInteractionAgent {self.agent_id} processing")

        # Get recent SMS interactions from database
        try:
            db = next(get_db())
            await self._process_recent_interactions(db)
            await self._calculate_sms_metrics(db)

            # Send processed data to analysis agents
            await self._send_data_to_analysis_agents()

        except Exception as e:
            logger.error(f"Error processing SMS interactions: {str(e)}")
            raise

    async def _process_recent_interactions(self, db: Session):
        """
        Process recent SMS notification interactions.

        Args:
            db (Session): Database session
        """
        # Define the cutoff time (e.g., last hour)
        cutoff_time = datetime.utcnow() - timedelta(hours=1)

        # Query recent SMS notification engagements
        recent_engagements = db.query(NotificationEngagement).join(Notification).filter(
            NotificationEngagement.timestamp >= cutoff_time,
            Notification.channel == NotificationChannel.SMS
        ).all()

        # Process each engagement
        for engagement in recent_engagements:
            notification = engagement.notification

            # Create an event document
            event = {
                "user_id": notification.user_id,
                "event_type": "sms_engagement",
                "channel": NotificationChannel.SMS,
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

            logger.debug(f"Processed SMS engagement for user {notification.user_id}, action: {engagement.action}")

    async def _calculate_sms_metrics(self, db: Session):
        """
        Calculate SMS notification engagement metrics for users.

        Args:
            db (Session): Database session
        """
        # Define the cutoff time (e.g., last week)
        cutoff_time = datetime.utcnow() - timedelta(days=7)

        # Query users who have received SMS notifications
        active_users = db.query(User.id).join(Notification).filter(
            Notification.channel == NotificationChannel.SMS,
            Notification.sent_at >= cutoff_time
        ).distinct().all()

        active_user_ids = [user.id for user in active_users]

        for user_id in active_user_ids:
            # Get all sent notifications for this user
            sent_notifications = db.query(Notification).filter(
                Notification.user_id == user_id,
                Notification.channel == NotificationChannel.SMS,
                Notification.sent_at >= cutoff_time,
                Notification.is_sent == True
            ).all()

            # Count total sent
            total_sent = len(sent_notifications)

            if total_sent == 0:
                continue

            # Get notification IDs
            notification_ids = [n.id for n in sent_notifications]

            # Count engagements (For SMS, we typically track responses)
            responses = db.query(func.count(NotificationEngagement.id)).filter(
                NotificationEngagement.notification_id.in_(notification_ids),
                NotificationEngagement.action == "response"  # Custom action for SMS responses
            ).scalar() or 0

            # Calculate metrics
            response_rate = responses / total_sent if total_sent > 0 else 0

            # Create a metrics document
            metrics = {
                "user_id": user_id,
                "metric_type": "sms_engagement",
                "period_start": cutoff_time,
                "period_end": datetime.utcnow(),
                "metrics": {
                    "total_sent": total_sent,
                    "total_responses": responses,
                    "response_rate": response_rate
                }
            }

            # Store the metrics in MongoDB
            get_mongo_collection("user_metrics").insert_one(metrics)

            logger.debug(f"Calculated SMS metrics for user {user_id}: {response_rate:.1%} response rate")

    async def _send_data_to_analysis_agents(self):
        """
        Send collected data to analysis agents.
        """
        # Get recent SMS metrics
        metrics = list(get_mongo_collection("user_metrics").find(
            {"metric_type": "sms_engagement"},
            sort=[("period_end", -1)],
            limit=100
        ))

        # Send to Frequency Analysis Agent
        frequency_data = {
            "sms_engagement": [
                {
                    "user_id": metric["user_id"],
                    "timestamp": metric["period_end"],
                    "response_rate": metric["metrics"]["response_rate"]
                }
                for metric in metrics
            ],
            "channel": NotificationChannel.SMS
        }
        await self.send_message(AgentType.FREQUENCY_ANALYSIS, frequency_data)

        # Send to Channel Analysis Agent
        channel_data = {
            "channel_engagement": [
                {
                    "user_id": metric["user_id"],
                    "timestamp": metric["period_end"],
                    "channel": NotificationChannel.SMS,
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

        logger.info(f"Sent SMS metrics for {len(metrics)} users to analysis agents")

    async def _get_notification_type_metrics(self) -> List[Dict[str, Any]]:
        """
        Get engagement metrics broken down by notification type.

        Returns:
            List[Dict[str, Any]]: List of notification type metrics by user
        """
        # Get all SMS engagement events from the past week
        cutoff_time = datetime.utcnow() - timedelta(days=7)

        pipeline = [
            {
                "$match": {
                    "event_type": "sms_engagement",
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
                engagement_score = actions.get("response", 0) / total_actions if total_actions > 0 else 0

                formatted_results.append({
                    "user_id": user_id,
                    "notification_type": notification_type,
                    "channel": NotificationChannel.SMS,
                    "engagement_score": engagement_score,
                    "actions": actions
                })

        return formatted_results

    def _calculate_engagement_level(self, metrics: Dict[str, Any]) -> float:
        """
        Calculate an engagement level score from SMS metrics.

        Args:
            metrics (Dict[str, Any]): The metrics to calculate from

        Returns:
            float: Engagement level score (0-1)
        """
        # For SMS, the main metric is response rate
        return metrics["response_rate"]

    async def handle_message(self, message: Dict[str, Any], sender: Dict[str, Any]):
        """
        Handle messages from other agents.

        Args:
            message (Dict[str, Any]): The message content
            sender (Dict[str, Any]): Information about the sender
        """
        # Feedback from SMS Gateway
        if "delivery_data" in message and sender.get("agent_type") == AgentType.SMS_GATEWAY:
            delivery_data = message["delivery_data"]

            # Store delivery confirmation data
            for delivery in delivery_data:
                event = {
                    "user_id": delivery["user_id"],
                    "event_type": "sms_delivery",
                    "channel": NotificationChannel.SMS,
                    "timestamp": delivery["timestamp"],
                    "details": {
                        "notification_id": delivery["notification_id"],
                        "status": delivery["status"],
                        "provider": delivery.get("provider")
                    }
                }
                self.user_events_collection.insert_one(event)

            logger.info(f"Processed {len(delivery_data)} SMS delivery events")

        # Record SMS responses
        elif "response_data" in message and sender.get("agent_type") == AgentType.SMS_GATEWAY:
            response_data = message["response_data"]

            # Store response data
            for response in response_data:
                db = next(get_db())

                # Find the notification this is a response to
                notification = db.query(Notification).filter(
                    Notification.user_id == response["user_id"],
                    Notification.channel == NotificationChannel.SMS,
                    Notification.is_sent == True
                ).order_by(Notification.sent_at.desc()).first()


                if notification:
                    # Create engagement record
                    engagement = NotificationEngagement(
                        notification_id=notification.id,
                        action="response",
                        timestamp=response["timestamp"],
                        meta_data={"content": response.get("content")}
                    )
                    db.add(engagement)
                    db.commit()

                    logger.debug(f"Recorded SMS response for notification {notification.id}")
                else:
                    logger.warning(
                        f"Could not find related notification for SMS response from user {response['user_id']}")