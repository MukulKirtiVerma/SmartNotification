import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List

from loguru import logger
from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent
from app.db.database import get_db, get_mongo_collection
from config.constants import AgentType, Collections, NotificationType


class TypeAnalysisAgent(BaseAgent):
    """
    Agent that analyzes which types of notifications a user prefers.
    Identifies patterns in engagement based on notification content type.
    """

    def __init__(self, name: str = "Type Analysis"):
        super().__init__(AgentType.TYPE_ANALYSIS, name)
        self.user_profiles_collection = get_mongo_collection(Collections.USER_PROFILES)

    async def process(self):
        """
        Analyze notification type preferences based on engagement data.
        """
        logger.debug(f"TypeAnalysisAgent {self.agent_id} processing")

        # Process accumulated type engagement data and update user profiles
        await self._analyze_type_preferences()

        # Send updated type recommendations to User Profile Service
        await self._send_recommendations_to_profile_service()

    async def _analyze_type_preferences(self):
        """
        Analyze notification type preferences for each user.
        """
        # Get all stored type engagement metrics
        metrics = list(get_mongo_collection("engagement_metrics").find({
            "metric_type": "notification_type"
        }))

        # Group metrics by user
        user_metrics = {}
        for metric in metrics:
            user_id = metric["user_id"]
            if user_id not in user_metrics:
                user_metrics[user_id] = []
            user_metrics[user_id].append(metric)

        # Calculate type preferences for each user
        for user_id, user_data in user_metrics.items():
            # Load existing user profile or create new one
            user_profile = self.user_profiles_collection.find_one({"user_id": user_id})
            if not user_profile:
                user_profile = {
                    "user_id": user_id,
                    "frequency_preferences": {},
                    "channel_preferences": {},
                    "content_preferences": {},
                    "time_preferences": {},
                    "last_updated": datetime.utcnow()
                }

            # Initialize preference scores for all notification types
            type_scores = {
                notification_type: 0.0
                for notification_type in NotificationType.ALL
            }

            # Count of data points for each type
            type_counts = {
                notification_type: 0
                for notification_type in NotificationType.ALL
            }

            # Process each metric
            for metric in user_data:
                notification_type = metric.get("notification_type")
                if notification_type not in type_scores:
                    continue

                engagement_score = metric.get("engagement_score", 0.0)
                type_scores[notification_type] += engagement_score
                type_counts[notification_type] += 1

            # Calculate average scores
            for notification_type in type_scores:
                if type_counts[notification_type] > 0:
                    type_scores[notification_type] /= type_counts[notification_type]

            # Normalize scores to a 0-1 range
            max_score = max(type_scores.values()) if type_scores.values() else 1.0
            if max_score > 0:
                for notification_type in type_scores:
                    type_scores[notification_type] /= max_score

            # Update content preferences in user profile
            user_profile["content_preferences"] = {
                "type_scores": type_scores,
                "preferred_types": sorted(
                    type_scores.keys(),
                    key=lambda t: type_scores[t],
                    reverse=True
                ),
                "last_updated": datetime.utcnow()
            }

            # Update user profile
            self.user_profiles_collection.update_one(
                {"user_id": user_id},
                {"$set": {
                    "content_preferences": user_profile["content_preferences"],
                    "last_updated": datetime.utcnow()
                }},
                upsert=True
            )

            logger.debug(
                f"Updated content preferences for user {user_id}: top type {user_profile['content_preferences']['preferred_types'][0]}")

    async def _send_recommendations_to_profile_service(self):
        """
        Send content type recommendations to the User Profile Service.
        """
        # Get recently updated profiles
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        profiles = list(self.user_profiles_collection.find({
            "last_updated": {"$gte": cutoff_time}
        }))

        # Prepare recommendations
        recommendations = []
        for profile in profiles:
            if "content_preferences" not in profile:
                continue

            user_recommendation = {
                "user_id": profile["user_id"],
                "content_preferences": profile["content_preferences"]
            }
            recommendations.append(user_recommendation)

        # Send recommendations to User Profile Service
        if recommendations:
            await self.send_message(AgentType.USER_PROFILE, {
                "content_recommendations": recommendations
            })

            logger.info(f"Sent content recommendations for {len(recommendations)} users to User Profile Service")

    async def handle_message(self, message: Dict[str, Any], sender: Dict[str, Any]):
        """
        Handle messages from other agents.

        Args:
            message (Dict[str, Any]): The message content
            sender (Dict[str, Any]): Information about the sender
        """
        # Handle notification type engagement data
        if "notification_type_engagement" in message:
            metrics = message["notification_type_engagement"]

            logger.info(f"Received {len(metrics)} notification type metrics from {sender.get('agent_name')}")

            # Store metrics for later analysis
            for metric in metrics:
                get_mongo_collection("engagement_metrics").insert_one({
                    "user_id": metric["user_id"],
                    "notification_type": metric["notification_type"],
                    "channel": metric["channel"],
                    "metric_type": "notification_type",
                    "engagement_score": metric["engagement_score"],
                    "actions": metric.get("actions", {}),
                    "timestamp": datetime.utcnow(),
                    "source_agent": sender.get("agent_id")
                })

        # Handle dashboard section views
        elif "dashboard_section_views" in message:
            section_views = message["dashboard_section_views"]

            logger.info(f"Received {len(section_views)} dashboard section views from {sender.get('agent_name')}")

            # Map dashboard sections to notification types
            section_to_type = {
                "shipments": NotificationType.SHIPMENT,
                "orders": NotificationType.ORDER_CONFIRMATION,
                "payments": NotificationType.PAYMENT,
                "deliveries": NotificationType.DELIVERY,
                "returns": NotificationType.RETURN,
                "promotions": NotificationType.PROMOTION
            }

            # Process section views
            for view in section_views:
                user_id = view["user_id"]
                sections = view["sections"]

                # Map viewed sections to notification types
                viewed_types = []
                for section in sections:
                    if section in section_to_type:
                        viewed_types.append(section_to_type[section])

                # Calculate engagement score for each type
                for notification_type in viewed_types:
                    get_mongo_collection("engagement_metrics").insert_one({
                        "user_id": user_id,
                        "notification_type": notification_type,
                        "channel": "dashboard",
                        "metric_type": "notification_type",
                        "engagement_score": 1.0,  # Viewing a section indicates interest
                        "timestamp": view.get("timestamp", datetime.utcnow()),
                        "source_agent": sender.get("agent_id")
                    })