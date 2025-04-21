import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List

from loguru import logger
from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent
from app.db.database import get_db, get_mongo_collection
from config.constants import AgentType, Collections, NotificationChannel


class ChannelAnalysisAgent(BaseAgent):
    """
    Agent that analyzes which notification channels a user prefers.
    Determines optimal delivery channels based on engagement patterns.
    """

    def __init__(self, name: str = "Channel Analysis"):
        super().__init__(AgentType.CHANNEL_ANALYSIS, name)
        self.user_profiles_collection = get_mongo_collection(Collections.USER_PROFILES)

    async def process(self):
        """
        Analyze channel preferences based on engagement data.
        """
        logger.debug(f"ChannelAnalysisAgent {self.agent_id} processing")

        # Process accumulated channel engagement data and update user profiles
        await self._analyze_channel_preferences()

        # Send updated channel recommendations to User Profile Service
        await self._send_recommendations_to_profile_service()

    async def _analyze_channel_preferences(self):
        """
        Analyze notification channel preferences for each user.
        """
        # Get all stored channel engagement metrics
        metrics = list(get_mongo_collection("engagement_metrics").find({
            "metric_type": "channel"
        }))

        # Group metrics by user
        user_metrics = {}
        for metric in metrics:
            user_id = metric["user_id"]
            if user_id not in user_metrics:
                user_metrics[user_id] = []
            user_metrics[user_id].append(metric)

        # Calculate channel preferences for each user
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

            # Initialize engagement scores for all channels
            channel_scores = {
                channel: 0.0
                for channel in NotificationChannel.ALL
            }

            # Count of data points for each channel
            channel_counts = {
                channel: 0
                for channel in NotificationChannel.ALL
            }

            # Process each metric
            for metric in user_data:
                channel = metric.get("channel")
                if channel not in channel_scores:
                    continue

                engagement_level = metric.get("engagement_level", 0.0)
                channel_scores[channel] += engagement_level
                channel_counts[channel] += 1

            # Calculate average scores
            for channel in channel_scores:
                if channel_counts[channel] > 0:
                    channel_scores[channel] /= channel_counts[channel]

            # Normalize scores to a 0-1 range
            max_score = max(channel_scores.values()) if channel_scores.values() else 1.0
            if max_score > 0:
                for channel in channel_scores:
                    channel_scores[channel] /= max_score

            # Rank channels by preference
            ranked_channels = sorted(
                channel_scores.keys(),
                key=lambda c: channel_scores[c],
                reverse=True
            )

            # Update channel preferences in user profile
            user_profile["channel_preferences"] = {
                "channel_scores": channel_scores,
                "ranked_channels": ranked_channels,
                "last_updated": datetime.utcnow()
            }

            # Update user profile
            self.user_profiles_collection.update_one(
                {"user_id": user_id},
                {"$set": {
                    "channel_preferences": user_profile["channel_preferences"],
                    "last_updated": datetime.utcnow()
                }},
                upsert=True
            )

            logger.debug(
                f"Updated channel preferences for user {user_id}: top channel {ranked_channels[0] if ranked_channels else 'none'}")

    async def _send_recommendations_to_profile_service(self):
        """
        Send channel recommendations to the User Profile Service.
        """
        # Get recently updated profiles
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        profiles = list(self.user_profiles_collection.find({
            "last_updated": {"$gte": cutoff_time}
        }))

        # Prepare recommendations
        recommendations = []
        for profile in profiles:
            if "channel_preferences" not in profile:
                continue

            user_recommendation = {
                "user_id": profile["user_id"],
                "channel_preferences": profile["channel_preferences"]
            }
            recommendations.append(user_recommendation)

        # Send recommendations to User Profile Service
        if recommendations:
            await self.send_message(AgentType.USER_PROFILE, {
                "channel_recommendations": recommendations
            })

            logger.info(f"Sent channel recommendations for {len(recommendations)} users to User Profile Service")

    async def handle_message(self, message: Dict[str, Any], sender: Dict[str, Any]):
        """
        Handle messages from other agents.

        Args:
            message (Dict[str, Any]): The message content
            sender (Dict[str, Any]): Information about the sender
        """
        # Handle channel engagement data
        if "channel_engagement" in message:
            engagements = message["channel_engagement"]

            logger.info(f"Received {len(engagements)} channel engagements from {sender.get('agent_name')}")

            # Store metrics for later analysis
            for engagement in engagements:
                get_mongo_collection("engagement_metrics").insert_one({
                    "user_id": engagement["user_id"],
                    "channel": engagement["channel"],
                    "metric_type": "channel",
                    "engagement_level": engagement["engagement_level"],
                    "timestamp": engagement.get("timestamp", datetime.utcnow()),
                    "source_agent": sender.get("agent_id")
                })