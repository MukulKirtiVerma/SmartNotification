import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List

from loguru import logger
from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent
from app.db.database import get_db, get_mongo_collection
from config.constants import AgentType, Collections, NotificationChannel, NotificationType


class UserProfileAgent(BaseAgent):
    """
    Agent that maintains comprehensive user profiles with notification preferences.
    Aggregates data from analysis agents to build a complete picture of each user.
    """

    def __init__(self, name: str = "User Profile Service"):
        super().__init__(AgentType.USER_PROFILE, name)
        self.user_profiles_collection = get_mongo_collection(Collections.USER_PROFILES)

    async def process(self):
        """
        Periodically update and maintain user profiles.
        """
        logger.debug(f"UserProfileAgent {self.agent_id} processing")

        # Merge profiles that received partial updates
        await self._merge_profile_updates()

        # Update profile segments
        await self._update_user_segments()

        # Send updated profiles to the Recommendation System
        await self._send_profiles_to_recommendation_system()

    async def _merge_profile_updates(self):
        """
        Merge any partial profile updates into complete profiles.
        """
        # Find profiles that have been recently updated
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        updated_profiles = list(self.user_profiles_collection.find({
            "last_updated": {"$gte": cutoff_time}
        }))

        logger.info(f"Merging updates for {len(updated_profiles)} user profiles")

        # No special processing needed as updates are directly applied to profiles
        # This method is a placeholder for more complex merging logic if needed

    async def _update_user_segments(self):
        """
        Update user segments based on profile data.
        """
        # Find recently updated profiles
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        profiles = list(self.user_profiles_collection.find({
            "last_updated": {"$gte": cutoff_time}
        }))

        for profile in profiles:
            segments = []

            # Frequency-based segments
            if "frequency_preferences" in profile:
                freq_level = profile["frequency_preferences"].get("level")
                if freq_level:
                    segments.append(f"frequency_{freq_level}")

            # Channel preference segments
            if "channel_preferences" in profile and "ranked_channels" in profile["channel_preferences"]:
                top_channels = profile["channel_preferences"]["ranked_channels"]
                if top_channels:
                    segments.append(f"prefers_{top_channels[0]}")

            # Content preference segments
            if "content_preferences" in profile and "preferred_types" in profile["content_preferences"]:
                top_types = profile["content_preferences"]["preferred_types"]
                if top_types:
                    segments.append(f"prefers_{top_types[0]}")

            # Time preference segments
            if "time_preferences" in profile and "peak_period" in profile["time_preferences"]:
                peak_period = profile["time_preferences"]["peak_period"]
                if peak_period:
                    segments.append(f"active_{peak_period}")

            # Update segments in the profile
            self.user_profiles_collection.update_one(
                {"user_id": profile["user_id"]},
                {"$set": {
                    "segments": segments,
                    "last_segmented": datetime.utcnow()
                }}
            )

            logger.debug(f"Updated segments for user {profile['user_id']}: {segments}")

    async def _send_profiles_to_recommendation_system(self):
        """
        Send updated user profiles to the Recommendation System.
        """
        # Find recently updated profiles
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        profiles = list(self.user_profiles_collection.find({
            "last_updated": {"$gte": cutoff_time}
        }))

        if not profiles:
            return

        # Send profiles to Recommendation System
        await self.send_message(AgentType.RECOMMENDATION, {
            "updated_profiles": [
                {
                    "user_id": profile["user_id"],
                    "frequency_preferences": profile.get("frequency_preferences", {}),
                    "channel_preferences": profile.get("channel_preferences", {}),
                    "content_preferences": profile.get("content_preferences", {}),
                    "time_preferences": profile.get("time_preferences", {}),
                    "segments": profile.get("segments", [])
                }
                for profile in profiles
            ]
        })

        logger.info(f"Sent {len(profiles)} updated profiles to Recommendation System")

    async def handle_message(self, message: Dict[str, Any], sender: Dict[str, Any]):
        """
        Handle messages from other agents.

        Args:
            message (Dict[str, Any]): The message content
            sender (Dict[str, Any]): Information about the sender
        """
        # Handle frequency recommendations
        if "frequency_recommendations" in message:
            recommendations = message["frequency_recommendations"]

            logger.info(
                f"Received frequency recommendations for {len(recommendations)} users from {sender.get('agent_name')}")

            for recommendation in recommendations:
                user_id = recommendation["user_id"]
                frequency_pref = recommendation["frequency_preference"]
                time_pref = recommendation["time_preference"]

                # Update frequency and time preferences
                self.user_profiles_collection.update_one(
                    {"user_id": user_id},
                    {"$set": {
                        "frequency_preferences": frequency_pref,
                        "time_preferences": time_pref,
                        "last_updated": datetime.utcnow()
                    }},
                    upsert=True
                )

        # Handle channel recommendations
        elif "channel_recommendations" in message:
            recommendations = message["channel_recommendations"]

            logger.info(
                f"Received channel recommendations for {len(recommendations)} users from {sender.get('agent_name')}")

            for recommendation in recommendations:
                user_id = recommendation["user_id"]
                channel_pref = recommendation["channel_preferences"]

                # Update channel preferences
                self.user_profiles_collection.update_one(
                    {"user_id": user_id},
                    {"$set": {
                        "channel_preferences": channel_pref,
                        "last_updated": datetime.utcnow()
                    }},
                    upsert=True
                )

        # Handle content recommendations
        elif "content_recommendations" in message:
            recommendations = message["content_recommendations"]

            logger.info(
                f"Received content recommendations for {len(recommendations)} users from {sender.get('agent_name')}")

            for recommendation in recommendations:
                user_id = recommendation["user_id"]
                content_pref = recommendation["content_preferences"]

                # Update content preferences
                self.user_profiles_collection.update_one(
                    {"user_id": user_id},
                    {"$set": {
                        "content_preferences": content_pref,
                        "last_updated": datetime.utcnow()
                    }},
                    upsert=True
                )