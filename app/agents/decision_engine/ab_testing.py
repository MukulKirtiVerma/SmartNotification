import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List
import random

from loguru import logger
from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent
from app.db.database import get_db, get_mongo_collection
from app.db.models import ABTest, ABTestAssignment, User, Notification
from config.constants import AgentType, Collections, NotificationChannel, NotificationType
from config.config import current_config

from app.db.models import ABTest, ABTestAssignment, User, Notification, NotificationEngagement


class ABTestingAgent(BaseAgent):
    """
    Agent that manages A/B testing of notification strategies.
    Creates test variants, assigns users, and analyzes results.
    """

    def __init__(self, name: str = "A/B Testing Module"):
        super().__init__(AgentType.AB_TESTING, name)
        self.ab_test_results = get_mongo_collection(Collections.AB_TEST_RESULTS)

    async def process(self):
        """
        Process A/B tests, assign users, and analyze results.
        """
        logger.debug(f"ABTestingAgent {self.agent_id} processing")

        # Check for new tests to initialize
        db = next(get_db())
        await self._initialize_new_tests(db)

        # Check for tests that need user assignments
        await self._assign_users_to_tests(db)

        # Analyze results for ongoing tests
        await self._analyze_test_results(db)

        # Check for tests to conclude
        await self._conclude_tests(db)

    async def _initialize_new_tests(self, db: Session):
        """
        Initialize newly created A/B tests.

        Args:
            db (Session): Database session
        """
        # Find tests that are active but not initialized
        new_tests = db.query(ABTest).filter(
            ABTest.is_active == True,
            ~ABTest.id.in_(
                db.query(ABTestAssignment.ab_test_id).distinct()
            )
        ).all()

        for test in new_tests:
            logger.info(f"Initializing new A/B test: {test.name} (ID: {test.id})")

            # Validate test configuration
            if not test.variants or "control" not in test.variants:
                logger.error(f"A/B test {test.name} (ID: {test.id}) missing control variant")
                continue

            # Initialize test-specific data structures if needed
            # This could include creating experiment metadata, etc.

            logger.info(f"A/B test {test.name} (ID: {test.id}) initialized with variants: {list(test.variants.keys())}")

    async def _assign_users_to_tests(self, db: Session):
        """
        Assign users to test variants for active tests.

        Args:
            db (Session): Database session
        """
        # Get active tests
        active_tests = db.query(ABTest).filter(ABTest.is_active == True).all()

        for test in active_tests:
            # Check if we've reached the target sample size
            current_assignments = db.query(ABTestAssignment).filter(
                ABTestAssignment.ab_test_id == test.id
            ).count()

            target_size = current_config.AB_TEST_SAMPLE_SIZE

            if current_assignments >= target_size:
                continue

            # How many more users to assign
            remaining = target_size - current_assignments

            # Get eligible users not already assigned to this test
            assigned_user_ids = db.query(ABTestAssignment.user_id).filter(
                ABTestAssignment.ab_test_id == test.id
            ).all()

            assigned_user_ids = [u.user_id for u in assigned_user_ids]

            eligible_users = db.query(User).filter(
                User.is_active == True,
                ~User.id.in_(assigned_user_ids) if assigned_user_ids else True
            ).limit(remaining).all()

            if not eligible_users:
                logger.warning(f"No eligible users found for A/B test {test.name} (ID: {test.id})")
                continue

            # Get available variants
            variants = list(test.variants.keys())

            # Assign users to variants
            for user in eligible_users:
                # Randomly select a variant
                variant = random.choice(variants)

                # Create assignment
                assignment = ABTestAssignment(
                    ab_test_id=test.id,
                    user_id=user.id,
                    variant=variant,
                    created_at=datetime.utcnow()
                )

                db.add(assignment)

                logger.debug(f"Assigned user {user.id} to variant {variant} for test {test.id}")

            # Commit all assignments
            db.commit()

            logger.info(f"Assigned {len(eligible_users)} users to A/B test {test.name} (ID: {test.id})")

    async def _analyze_test_results(self, db: Session):
        """
        Analyze results for ongoing A/B tests.

        Args:
            db (Session): Database session
        """
        # Get active tests running for at least the minimum duration
        min_start_date = datetime.utcnow() - timedelta(days=current_config.AB_TEST_MIN_DURATION_DAYS)

        active_tests = db.query(ABTest).filter(
            ABTest.is_active == True,
            ABTest.start_date <= min_start_date
        ).all()

        for test in active_tests:
            logger.info(f"Analyzing results for A/B test {test.name} (ID: {test.id})")

            # Get metrics to analyze from test configuration
            metrics = test.metrics or ["open_rate", "click_rate", "engagement_score"]

            # Get test variants
            variants = list(test.variants.keys())

            # Get user assignments for this test
            assignments = db.query(ABTestAssignment).filter(
                ABTestAssignment.ab_test_id == test.id
            ).all()

            # Group users by variant
            users_by_variant = {}
            for variant in variants:
                users_by_variant[variant] = [
                    a.user_id for a in assignments if a.variant == variant
                ]

            # For each metric, calculate results per variant
            for metric in metrics:
                variant_results = await self._calculate_metric_by_variant(
                    db, test.id, metric, users_by_variant
                )

                # Store results in MongoDB
                for variant, value in variant_results.items():
                    self.ab_test_results.update_one(
                        {
                            "test_id": test.id,
                            "variant": variant,
                            "metric": metric
                        },
                        {"$set": {
                            "value": value,
                            "sample_size": len(users_by_variant[variant]),
                            "timestamp": datetime.utcnow(),
                            "processed": False
                        }},
                        upsert=True
                    )

                logger.info(f"Updated results for test {test.id}, metric {metric}: {variant_results}")

    async def _calculate_metric_by_variant(
            self, db: Session, test_id: int, metric: str, users_by_variant: Dict[str, List[int]]
    ) -> Dict[str, float]:
        """
        Calculate a specific metric for each variant.

        Args:
            db (Session): Database session
            test_id (int): A/B test ID
            metric (str): Metric to calculate
            users_by_variant (Dict[str, List[int]]): Dict of variant -> list of user IDs

        Returns:
            Dict[str, float]: Dict of variant -> metric value
        """
        results = {}

        # For each variant, calculate the metric
        for variant, user_ids in users_by_variant.items():
            if not user_ids:
                results[variant] = 0.0
                continue

            # Different calculation based on metric type
            if metric == "open_rate":
                # Get notifications sent to these users
                notifications = db.query(Notification).filter(
                    Notification.user_id.in_(user_ids),
                    Notification.is_sent == True
                ).all()

                notification_ids = [n.id for n in notifications]

                if not notification_ids:
                    results[variant] = 0.0
                    continue

                # Count how many were opened

                opens = db.query(NotificationEngagement).filter(
                    NotificationEngagement.notification_id.in_(notification_ids),
                    NotificationEngagement.action == "open"
                ).count()

                # Calculate open rate
                open_rate = opens / len(notification_ids)
                results[variant] = open_rate

            elif metric == "click_rate":
                # Similar calculation for click rate
                notifications = db.query(Notification).filter(
                    Notification.user_id.in_(user_ids),
                    Notification.is_sent == True
                ).all()

                notification_ids = [n.id for n in notifications]

                if not notification_ids:
                    results[variant] = 0.0
                    continue

                # Count how many were clicked
                clicks = db.query(NotificationEngagement).filter(
                    NotificationEngagement.notification_id.in_(notification_ids),
                    NotificationEngagement.action == "click"
                ).count()

                # Calculate click rate
                click_rate = clicks / len(notification_ids)
                results[variant] = click_rate

            elif metric == "engagement_score":
                # More complex engagement score from user profiles
                profiles = list(get_mongo_collection(Collections.USER_PROFILES).find({
                    "user_id": {"$in": user_ids}
                }))

                if not profiles:
                    results[variant] = 0.0
                    continue

                # Calculate average engagement score
                engagement_scores = []
                for profile in profiles:
                    # Sum up channel scores
                    if "channel_preferences" in profile and "channel_scores" in profile["channel_preferences"]:
                        channel_scores = profile["channel_preferences"]["channel_scores"]
                        avg_channel_score = sum(channel_scores.values()) / len(channel_scores) if channel_scores else 0
                        engagement_scores.append(avg_channel_score)

                if engagement_scores:
                    results[variant] = sum(engagement_scores) / len(engagement_scores)
                else:
                    results[variant] = 0.0

            else:
                # Unsupported metric
                logger.warning(f"Unsupported metric {metric} for test {test_id}")
                results[variant] = 0.0

        return results

    async def _conclude_tests(self, db: Session):
        """
        Check for tests that should be concluded and finalize results.

        Args:
            db (Session): Database session
        """
        # Find tests that have an end date in the past
        concluded_tests = db.query(ABTest).filter(
            ABTest.is_active == True,
            ABTest.end_date.isnot(None),
            ABTest.end_date <= datetime.utcnow()
        ).all()

        for test in concluded_tests:
            logger.info(f"Concluding A/B test {test.name} (ID: {test.id})")

            # Determine winning variant
            winning_variant = await self._determine_winning_variant(test.id, test.metrics)

            # Update test status
            test.is_active = False
            test.updated_at = datetime.utcnow()

            # Store conclusion data
            test_conclusion = {
                "winning_variant": winning_variant,
                "conclusion_time": datetime.utcnow()
            }

            # We need to explicitly set this as JSON because SQLAlchemy doesn't handle nested dicts well
            db.execute(
                f"UPDATE ab_tests SET conclusion = '{test_conclusion}' WHERE id = {test.id}"
            )

            db.commit()

            logger.info(f"Concluded A/B test {test.name} (ID: {test.id}), winning variant: {winning_variant}")

            # Notify Recommendation System about the test conclusion
            await self.send_message(AgentType.RECOMMENDATION, {
                "test_conclusion": {
                    "test_id": test.id,
                    "test_name": test.name,
                    "winning_variant": winning_variant
                }
            })

    async def _determine_winning_variant(self, test_id: int, metrics: List[str] = None) -> str:
        """
        Determine the winning variant for a test based on metrics.

        Args:
            test_id (int): A/B test ID
            metrics (List[str], optional): List of metrics to consider. Defaults to None.

        Returns:
            str: The winning variant
        """
        if not metrics:
            metrics = ["open_rate", "click_rate", "engagement_score"]

        # Get results for all variants
        results = {}
        for metric in metrics:
            metric_results = list(self.ab_test_results.find({
                "test_id": test_id,
                "metric": metric
            }))

            for result in metric_results:
                variant = result["variant"]
                if variant not in results:
                    results[variant] = []

                # Normalize score to 0-1 range
                value = result["value"]
                results[variant].append(value)

        # If no results, return control
        if not results:
            return "control"

        # Calculate average score across metrics for each variant
        avg_scores = {}
        for variant, scores in results.items():
            if scores:
                avg_scores[variant] = sum(scores) / len(scores)
            else:
                avg_scores[variant] = 0

        # Find the variant with the highest score
        winning_variant = max(avg_scores, key=avg_scores.get)

        return winning_variant

    async def handle_message(self, message: Dict[str, Any], sender: Dict[str, Any]):
        """
        Handle messages from other agents.

        Args:
            message (Dict[str, Any]): The message content
            sender (Dict[str, Any]): Information about the sender
        """
        # Handle notification delivery confirmations for A/B test tracking
        if "delivery_confirmation" in message:
            confirmation = message["delivery_confirmation"]

            # Check if this notification is part of an A/B test
            notification_id = confirmation.get("notification_id")
            if not notification_id:
                return

            db = next(get_db())

            # Get notification details
            notification = db.query(Notification).filter(Notification.id == notification_id).first()
            if not notification:
                logger.warning(f"Notification {notification_id} not found for A/B test tracking")
                return

            # Check if user is assigned to a test
            test_assignment = db.query(ABTestAssignment).filter(
                ABTestAssignment.user_id == notification.user_id
            ).first()

            if not test_assignment:
                return

            # Record this delivery for A/B test analysis
            delivery_data = {
                "test_id": test_assignment.ab_test_id,
                "variant": test_assignment.variant,
                "notification_id": notification_id,
                "user_id": notification.user_id,
                "delivery_status": confirmation.get("status"),
                "delivery_time": confirmation.get("timestamp", datetime.utcnow()),
                "channel": confirmation.get("channel")
            }

            get_mongo_collection("ab_test_deliveries").insert_one(delivery_data)

            logger.debug(
                f"Recorded A/B test delivery for notification {notification_id}, test {test_assignment.ab_test_id}")

        # Handle notification engagement events for A/B test tracking
        elif "engagement_event" in message:
            event = message["engagement_event"]

            # Check if this notification is part of an A/B test
            notification_id = event.get("notification_id")
            if not notification_id:
                return

            db = next(get_db())

            # Get notification details
            notification = db.query(Notification).filter(Notification.id == notification_id).first()
            if not notification:
                logger.warning(f"Notification {notification_id} not found for A/B test tracking")
                return

            # Check if user is assigned to a test
            test_assignment = db.query(ABTestAssignment).filter(
                ABTestAssignment.user_id == notification.user_id
            ).first()

            if not test_assignment:
                return

            # Record this engagement for A/B test analysis
            engagement_data = {
                "test_id": test_assignment.ab_test_id,
                "variant": test_assignment.variant,
                "notification_id": notification_id,
                "user_id": notification.user_id,
                "action": event.get("action"),
                "timestamp": event.get("timestamp", datetime.utcnow()),
                "channel": event.get("channel")
            }

            get_mongo_collection("ab_test_engagements").insert_one(engagement_data)

            logger.debug(
                f"Recorded A/B test engagement for notification {notification_id}, test {test_assignment.ab_test_id}")