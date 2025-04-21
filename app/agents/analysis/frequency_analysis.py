import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List

from loguru import logger
from sqlalchemy.orm import Session
import pandas as pd
import numpy as np

from app.agents.base_agent import BaseAgent
from app.db.database import get_db, get_mongo_collection
from config.constants import AgentType, Collections, NotificationChannel, TimeOfDay


class FrequencyAnalysisAgent(BaseAgent):
    """
    Agent that analyzes user engagement patterns to determine optimal notification frequency.
    """

    def __init__(self, name: str = "Frequency Analysis"):
        super().__init__(AgentType.FREQUENCY_ANALYSIS, name)
        self.user_profiles_collection = get_mongo_collection(Collections.USER_PROFILES)

    async def process(self):
        """
        Analyze engagement data to determine optimal notification frequency for users.
        """
        logger.debug(f"FrequencyAnalysisAgent {self.agent_id} processing")

        # Process accumulated engagement data and update user profiles
        await self._analyze_user_frequency_preferences()
        await self._analyze_optimal_timing()

        # Send updated frequency recommendations to User Profile Service
        await self._send_recommendations_to_profile_service()

    async def _analyze_user_frequency_preferences(self):
        """
        Analyze engagement patterns to determine frequency preferences for each user.
        """
        # Get engagement metrics from the past 30 days
        cutoff_time = datetime.utcnow() - timedelta(days=30)

        # Get metrics from all channels
        metrics = list(get_mongo_collection("user_metrics").find({
            "period_end": {"$gte": cutoff_time},
            "metric_type": {
                "$in": ["email_engagement", "mobile_push_engagement", "sms_engagement", "dashboard_engagement"]}
        }))

        # Group metrics by user
        user_metrics = {}
        for metric in metrics:
            user_id = metric["user_id"]
            if user_id not in user_metrics:
                user_metrics[user_id] = []
            user_metrics[user_id].append(metric)

        # Calculate frequency preferences for each user
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

            # Calculate engagement rate for each channel
            email_metrics = [m for m in user_data if m["metric_type"] == "email_engagement"]
            push_metrics = [m for m in user_data if m["metric_type"] == "mobile_push_engagement"]
            sms_metrics = [m for m in user_data if m["metric_type"] == "sms_engagement"]
            dashboard_metrics = [m for m in user_data if m["metric_type"] == "dashboard_engagement"]

            # Calculate overall engagement level
            engagement_levels = []

            if email_metrics:
                avg_open_rate = sum(m["metrics"]["open_rate"] for m in email_metrics) / len(email_metrics)
                avg_click_rate = sum(m["metrics"]["click_rate"] for m in email_metrics) / len(email_metrics)
                email_engagement = avg_open_rate * 0.4 + avg_click_rate * 0.6
                engagement_levels.append(email_engagement)

            if push_metrics:
                avg_open_rate = sum(m["metrics"]["open_rate"] for m in push_metrics) / len(push_metrics)
                avg_click_rate = sum(m["metrics"]["click_rate"] for m in push_metrics) / len(push_metrics)
                push_engagement = avg_open_rate * 0.3 + avg_click_rate * 0.7
                engagement_levels.append(push_engagement)

            if sms_metrics:
                avg_response_rate = sum(m["metrics"]["response_rate"] for m in sms_metrics) / len(sms_metrics)
                sms_engagement = avg_response_rate
                engagement_levels.append(sms_engagement)

            if dashboard_metrics:
                # Dashboard engagement is calculated differently
                pass

            # Average engagement level
            overall_engagement = sum(engagement_levels) / len(engagement_levels) if engagement_levels else 0.5

            # Determine frequency preference based on engagement
            # Higher engagement = higher frequency tolerance
            frequency_score = min(1.0, overall_engagement * 1.5)  # Scale up but cap at 1.0

            # Map frequency score to notification frequency
            if frequency_score < 0.2:
                freq_pref = "very_low"  # Once a week or less
                max_daily = 1
            elif frequency_score < 0.4:
                freq_pref = "low"  # 2-3 times per week
                max_daily = 2
            elif frequency_score < 0.6:
                freq_pref = "medium"  # Once daily
                max_daily = 3
            elif frequency_score < 0.8:
                freq_pref = "high"  # 2-3 times daily
                max_daily = 5
            else:
                freq_pref = "very_high"  # Multiple times daily
                max_daily = 10

            # Update frequency preferences in user profile
            user_profile["frequency_preferences"] = {
                "level": freq_pref,
                "score": frequency_score,
                "max_daily_notifications": max_daily,
                "last_updated": datetime.utcnow()
            }

            # Update user profile
            self.user_profiles_collection.update_one(
                {"user_id": user_id},
                {"$set": {
                    "frequency_preferences": user_profile["frequency_preferences"],
                    "last_updated": datetime.utcnow()
                }},
                upsert=True
            )

            logger.debug(f"Updated frequency preferences for user {user_id}: {freq_pref} ({frequency_score:.2f})")

    async def _analyze_optimal_timing(self):
        """
        Analyze engagement patterns to determine optimal timing for notifications.
        """
        # Get engagement events from the past 30 days
        cutoff_time = datetime.utcnow() - timedelta(days=30)

        # Get engagement events from MongoDB
        events = list(get_mongo_collection(Collections.USER_EVENTS).find({
            "timestamp": {"$gte": cutoff_time},
            "event_type": {"$in": ["email_engagement", "push_engagement", "sms_engagement", "dashboard_view"]}
        }))

        # Group events by user
        user_events = {}
        for event in events:
            user_id = event["user_id"]
            if user_id not in user_events:
                user_events[user_id] = []
            user_events[user_id].append(event)

        # Calculate optimal timing for each user
        for user_id, user_data in user_events.items():
            # Extract timestamps and map to time of day
            times = []
            for event in user_data:
                # Convert timestamp to hour of day
                timestamp = event["timestamp"]
                hour = timestamp.hour
                times.append(hour)

            if not times:
                continue

            # Analyze distribution of activity
            time_distribution = {}
            for time_period in TimeOfDay.ALL:
                start_hour, end_hour = TimeOfDay.BOUNDARIES[time_period]

                # Handle time periods that cross midnight
                if start_hour > end_hour:
                    in_range = [t for t in times if t >= start_hour or t < end_hour]
                else:
                    in_range = [t for t in times if start_hour <= t < end_hour]

                time_distribution[time_period] = len(in_range) / len(times)

            # Load existing user profile
            user_profile = self.user_profiles_collection.find_one({"user_id": user_id})
            if not user_profile:
                continue

            # Update time preferences in user profile
            user_profile["time_preferences"] = {
                "distribution": time_distribution,
                "peak_period": max(time_distribution, key=time_distribution.get),
                "last_updated": datetime.utcnow()
            }

            # Update user profile
            self.user_profiles_collection.update_one(
                {"user_id": user_id},
                {"$set": {
                    "time_preferences": user_profile["time_preferences"],
                    "last_updated": datetime.utcnow()
                }}
            )

            logger.debug(
                f"Updated time preferences for user {user_id}: peak period {user_profile['time_preferences']['peak_period']}")

    async def _send_recommendations_to_profile_service(self):
        """
        Send frequency and timing recommendations to the User Profile Service.
        """
        # Get recently updated profiles
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        profiles = list(self.user_profiles_collection.find({
            "last_updated": {"$gte": cutoff_time}
        }))

        # Prepare recommendations
        recommendations = []
        for profile in profiles:
            user_recommendation = {
                "user_id": profile["user_id"],
                "frequency_preference": profile.get("frequency_preferences", {}),
                "time_preference": profile.get("time_preferences", {})
            }
            recommendations.append(user_recommendation)

        # Send recommendations to User Profile Service
        if recommendations:
            await self.send_message(AgentType.USER_PROFILE, {
                "frequency_recommendations": recommendations
            })

            logger.info(f"Sent frequency recommendations for {len(recommendations)} users to User Profile Service")

    async def handle_message(self, message: Dict[str, Any], sender: Dict[str, Any]):
        """
        Handle messages from other agents.

        Args:
            message (Dict[str, Any]): The message content
            sender (Dict[str, Any]): Information about the sender
        """
        # Handle engagement data from dashboard tracker
        if "dashboard_metrics" in message and sender.get("agent_type") in AgentType.DATA_COLLECTION:
            # Process dashboard metrics
            metrics = message["dashboard_metrics"]

            logger.info(f"Received {len(metrics)} dashboard metrics from {sender.get('agent_name')}")

            # Store metrics for later analysis
            for metric in metrics:
                get_mongo_collection("engagement_metrics").insert_one({
                    "user_id": metric["user_id"],
                    "channel": message.get("channel", NotificationChannel.DASHBOARD),
                    "metric_type": "frequency",
                    "value": metric.get("frequency", 0),
                    "timestamp": metric.get("timestamp", datetime.utcnow()),
                    "source_agent": sender.get("agent_id")
                })

        # Handle email engagement metrics
        elif "email_engagement" in message and sender.get("agent_type") in AgentType.DATA_COLLECTION:
            # Process email engagement metrics
            metrics = message["email_engagement"]

            logger.info(f"Received {len(metrics)} email engagement metrics from {sender.get('agent_name')}")

            # Store metrics for later analysis
            for metric in metrics:
                get_mongo_collection("engagement_metrics").insert_one({
                    "user_id": metric["user_id"],
                    "channel": message.get("channel", NotificationChannel.EMAIL),
                    "metric_type": "frequency",
                    "open_rate": metric.get("open_rate", 0),
                    "click_rate": metric.get("click_rate", 0),
                    "timestamp": metric.get("timestamp", datetime.utcnow()),
                    "source_agent": sender.get("agent_id")
                })

        # Handle mobile/push engagement metrics
        elif "mobile_engagement" in message and sender.get("agent_type") in AgentType.DATA_COLLECTION:
            # Process mobile engagement metrics
            metrics = message["mobile_engagement"]

            logger.info(f"Received {len(metrics)} mobile engagement metrics from {sender.get('agent_name')}")

            # Store metrics for later analysis
            for metric in metrics:
                get_mongo_collection("engagement_metrics").insert_one({
                    "user_id": metric["user_id"],
                    "channel": message.get("channel", NotificationChannel.PUSH),
                    "metric_type": "frequency",
                    "open_rate": metric.get("open_rate", 0),
                    "click_rate": metric.get("click_rate", 0),
                    "dismiss_rate": metric.get("dismiss_rate", 0),
                    "timestamp": metric.get("timestamp", datetime.utcnow()),
                    "source_agent": sender.get("agent_id")
                })

        # Handle SMS engagement metrics
        elif "sms_engagement" in message and sender.get("agent_type") in AgentType.DATA_COLLECTION:
            # Process SMS engagement metrics
            metrics = message["sms_engagement"]

            logger.info(f"Received {len(metrics)} SMS engagement metrics from {sender.get('agent_name')}")

            # Store metrics for later analysis
            for metric in metrics:
                get_mongo_collection("engagement_metrics").insert_one({
                    "user_id": metric["user_id"],
                    "channel": message.get("channel", NotificationChannel.SMS),
                    "metric_type": "frequency",
                    "response_rate": metric.get("response_rate", 0),
                    "timestamp": metric.get("timestamp", datetime.utcnow()),
                    "source_agent": sender.get("agent_id")
                })