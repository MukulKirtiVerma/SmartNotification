import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List

from loguru import logger
from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent
from app.db.database import get_db, get_mongo_collection
from app.db.models import Notification, User, NotificationEngagement
from config.constants import AgentType, Collections, NotificationChannel, NotificationType, TimeOfDay


class RecommendationAgent(BaseAgent):
    """
    Agent that generates personalized notification strategies for users.
    Uses profile data to determine optimal time, channel, and frequency.
    """

    def __init__(self, name: str = "Recommendation System"):
        super().__init__(AgentType.RECOMMENDATION, name)
        self.user_profiles_collection = get_mongo_collection(Collections.USER_PROFILES)
        self.pending_notifications = get_mongo_collection("pending_notifications")

    async def process(self):
        """
        Process pending notifications and generate delivery recommendations.
        """
        logger.debug(f"RecommendationAgent {self.agent_id} processing")

        # Get pending notifications
        await self._process_pending_notifications()

        # Check for A/B test results
        await self._check_ab_test_results()

    async def _process_pending_notifications(self):
        """
        Process notifications pending delivery and make recommendations.
        """
        # Load notifications that need recommendations
        pending = list(self.pending_notifications.find({
            "status": "pending",
            "scheduled_at": {"$lte": datetime.utcnow()}
        }))

        if not pending:
            return

        # Process each notification
        for notification in pending:
            user_id = notification["user_id"]
            notification_id = notification["notification_id"]
            notification_type = notification["type"]

            # Get user profile
            user_profile = self.user_profiles_collection.find_one({"user_id": user_id})

            if not user_profile:
                logger.warning(f"No profile found for user {user_id}, using default recommendations")
                # Use default recommendations
                channel = NotificationChannel.EMAIL
                delivery_time = datetime.utcnow()
            else:
                # Determine best channel
                channel = self._get_best_channel(user_profile, notification_type)

                # Determine best time
                delivery_time = self._get_best_delivery_time(user_profile)

            # Create recommendation
            recommendation = {
                "notification_id": notification_id,
                "user_id": user_id,
                "recommended_channel": channel,
                "recommended_time": delivery_time,
                "notification_type": notification_type,
                "created_at": datetime.utcnow()
            }

            # Update notification status
            self.pending_notifications.update_one(
                {"_id": notification["_id"]},
                {"$set": {
                    "status": "recommended",
                    "recommendation": recommendation
                }}
            )

            # Send recommendation to appropriate notification service
            await self._send_recommendation_to_service(recommendation)

            logger.info(
                f"Generated recommendation for notification {notification_id}: channel={channel}, time={delivery_time}")

    async def _check_ab_test_results(self):
        """
        Check for A/B test results and update recommendation strategies.
        """
        # Get recent A/B test results
        results = list(get_mongo_collection(Collections.AB_TEST_RESULTS).find({
            "processed": False
        }))

        if not results:
            return

        # Process test results
        for result in results:
            test_id = result["test_id"]
            variant = result["variant"]
            metric = result["metric"]
            value = result["value"]

            # Check if this variant is better than the control
            if variant != "control":
                control_result = get_mongo_collection(Collections.AB_TEST_RESULTS).find_one({
                    "test_id": test_id,
                    "variant": "control",
                    "metric": metric
                })

                if control_result and value > control_result["value"]:
                    # This variant performed better
                    logger.info(f"A/B test {test_id}: Variant {variant} outperformed control for metric {metric}")

                    # Update recommendation strategies based on test results
                    await self._update_strategies_from_test(test_id, variant, result)

            # Mark result as processed
            get_mongo_collection(Collections.AB_TEST_RESULTS).update_one(
                {"_id": result["_id"]},
                {"$set": {"processed": True}}
            )

    def _get_best_channel(self, user_profile: Dict[str, Any], notification_type: str) -> str:
        """
        Determine the best channel for a notification based on user profile.

        Args:
            user_profile (Dict[str, Any]): User profile data
            notification_type (str): Type of notification

        Returns:
            str: Recommended channel
        """
        # Default to email if no preferences
        if "channel_preferences" not in user_profile:
            return NotificationChannel.EMAIL

        # Get channel preferences
        if "ranked_channels" in user_profile["channel_preferences"]:
            ranked_channels = user_profile["channel_preferences"]["ranked_channels"]
            if ranked_channels:
                return ranked_channels[0]

                # Fall back to channel scores
        if "channel_scores" in user_profile["channel_preferences"]:
            channel_scores = user_profile["channel_preferences"]["channel_scores"]
            if channel_scores:
                return max(channel_scores, key=channel_scores.get)

        return NotificationChannel.EMAIL

    def _get_best_delivery_time(self, user_profile: Dict[str, Any]) -> datetime:
        """
        Determine the best delivery time based on user profile.

        Args:
            user_profile (Dict[str, Any]): User profile data

        Returns:
            datetime: Recommended delivery time
        """
        now = datetime.utcnow()

        # Default to immediate delivery
        if "time_preferences" not in user_profile:
            return now

        # If peak period is available, use it
        if "peak_period" in user_profile["time_preferences"]:
            peak_period = user_profile["time_preferences"]["peak_period"]

            # Get hour range for this period
            start_hour, end_hour = TimeOfDay.BOUNDARIES.get(peak_period, (8, 17))  # Default to work hours

            # Calculate target time
            current_hour = now.hour
            if start_hour <= current_hour < end_hour:
                # We're already in the peak period, deliver now
                return now
            elif start_hour > current_hour:
                # Peak period is later today
                return now.replace(hour=start_hour, minute=0, second=0) + timedelta(minutes=30)
            else:
                # Peak period is tomorrow
                return now.replace(hour=start_hour, minute=0, second=0) + timedelta(days=1, minutes=30)

        # Fall back to immediate delivery
        return now

    async def _send_recommendation_to_service(self, recommendation: Dict[str, Any]):
        """
        Send a recommendation to the appropriate notification service.

        Args:
            recommendation (Dict[str, Any]): The delivery recommendation
        """
        channel = recommendation["recommended_channel"]

        # Map channel to service agent
        if channel == NotificationChannel.EMAIL:
            target_agent = AgentType.EMAIL_SERVICE
        elif channel == NotificationChannel.PUSH:
            target_agent = AgentType.PUSH_NOTIFICATION
        elif channel == NotificationChannel.SMS:
            target_agent = AgentType.SMS_GATEWAY
        elif channel == NotificationChannel.DASHBOARD:
            target_agent = AgentType.DASHBOARD_ALERT
        else:
            logger.error(f"Unknown channel: {channel}")
            return

        # Send recommendation to service
        await self.send_message(target_agent, {
            "delivery_recommendation": recommendation
        })

    async def _update_strategies_from_test(self, test_id: int, variant: str, result: Dict[str, Any]):
        """
        Update recommendation strategies based on A/B test results.

        Args:
            test_id (int): ID of the A/B test
            variant (str): The successful variant
            result (Dict[str, Any]): The test result data
        """
        # Get test details from database
        from app.db import models
        db = next(get_db())

        ab_test = db.query(models.ABTest).filter_by(id=test_id).first()

        if not ab_test:
            logger.error(f"A/B test {test_id} not found in database")
            return

        # Extract variant details
        variant_details = ab_test.variants.get(variant, {})
        if not variant_details:
            logger.error(f"Variant {variant} details not found for test {test_id}")
            return

        # Extract strategy parameters from variant
        strategy_params = variant_details.get("strategy_params", {})

        # Update related recommendation strategies
        logger.info(f"Updating recommendation strategies based on test {test_id}, variant {variant}")

        # This would integrate with more complex strategy management
        # For now, we just log the new parameters
        logger.info(f"New strategy parameters: {strategy_params}")

        # As a simple example, we could update timing preferences if this was a timing test
        if "timing_strategy" in strategy_params:
            timing_strategy = strategy_params["timing_strategy"]
            logger.info(f"New timing strategy: {timing_strategy}")

    async def handle_message(self, message: Dict[str, Any], sender: Dict[str, Any]):
        """
        Handle messages from other agents.

        Args:
            message (Dict[str, Any]): The message content
            sender (Dict[str, Any]): Information about the sender
        """
        # Handle user profile updates
        if "updated_profiles" in message and sender.get("agent_type") == AgentType.USER_PROFILE:
            profiles = message["updated_profiles"]
            logger.info(f"Received {len(profiles)} updated profiles from User Profile Service")

            # Process updated profiles
            for profile in profiles:
                user_id = profile["user_id"]

                # Check for pending notifications for this user
                pending = list(self.pending_notifications.find({
                    "user_id": user_id,
                    "status": "pending"
                }))

                # Re-process pending notifications with updated profile
                if pending:
                    logger.info(f"Re-processing {len(pending)} pending notifications for user {user_id}")
                    for notification in pending:
                        self.pending_notifications.update_one(
                            {"_id": notification["_id"]},
                            {"$set": {"profile_update": True}}
                        )

        # Handle new notification requests from API
        elif "new_notification" in message:
            notification = message["new_notification"]

            # Store notification for processing
            self.pending_notifications.insert_one({
                "notification_id": notification["id"],
                "user_id": notification["user_id"],
                "type": notification["type"],
                "content": notification["content"],
                "status": "pending",
                "created_at": datetime.utcnow(),
                "scheduled_at": notification.get("scheduled_at", datetime.utcnow())
            })

            logger.info(f"Added notification {notification['id']} to pending queue")

        # Handle A/B test notifications
        elif "ab_test_assignment" in message and sender.get("agent_type") == AgentType.AB_TESTING:
            assignment = message["ab_test_assignment"]

            # Associate the notification with an A/B test
            if "notification_id" in assignment:
                self.pending_notifications.update_one(
                    {"notification_id": assignment["notification_id"]},
                    {"$set": {
                        "ab_test_id": assignment["ab_test_id"],
                        "ab_test_variant": assignment["variant"]
                    }}
                )

                logger.info(
                    f"Notification {assignment['notification_id']} assigned to A/B test {assignment['ab_test_id']}, variant {assignment['variant']}")