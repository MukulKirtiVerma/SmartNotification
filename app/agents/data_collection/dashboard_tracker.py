import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List

from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.agents.base_agent import BaseAgent
from app.db.database import get_db, get_mongo_collection
from app.db.models import User, UserSession, PageView
from config.constants import AgentType, Collections, NotificationChannel


class DashboardTrackerAgent(BaseAgent):
    """
    Agent that tracks user interaction with the dashboard.
    Collects data on dashboard visit frequency, time spent, and sections viewed.
    """

    def __init__(self, name: str = "Dashboard Tracker"):
        super().__init__(AgentType.DASHBOARD_TRACKER, name)
        self.user_events_collection = get_mongo_collection(Collections.USER_EVENTS)

    async def process(self):
        """
        Process dashboard interactions and collect metrics.
        """
        logger.debug(f"DashboardTrackerAgent {self.agent_id} processing")

        # Get recent page views from database
        try:
            db = next(get_db())
            await self._process_recent_page_views(db)
            await self._calculate_dashboard_metrics(db)

            # Send processed data to analysis agents
            await self._send_data_to_analysis_agents()

        except Exception as e:
            logger.error(f"Error processing dashboard tracking: {str(e)}")
            raise

    async def _process_recent_page_views(self, db: Session):
        """
        Process recent page views to extract dashboard interaction data.

        Args:
            db (Session): Database session
        """
        # Define the cutoff time (e.g., last hour)
        cutoff_time = datetime.utcnow() - timedelta(hours=1)

        # Query recent page views
        recent_views = db.query(PageView).join(UserSession).filter(
            PageView.view_time >= cutoff_time,
            PageView.url.like('/dashboard%')  # Only dashboard-related pages
        ).all()

        # Process each page view
        for view in recent_views:
            # Extract user ID from the session
            user_id = view.session.user_id

            # Create an event document
            event = {
                "user_id": user_id,
                "event_type": "dashboard_view",
                "channel": NotificationChannel.DASHBOARD,
                "timestamp": view.view_time,
                "details": {
                    "url": view.url,
                    "duration": view.duration,
                    "section": self._extract_dashboard_section(view.url),
                    "page_view_id": view.id
                },
                "context": {
                    "session_id": view.session.session_id,
                    "ip": view.session.ip_address,
                    "user_agent": view.session.user_agent
                }
            }

            # Store the event in MongoDB
            self.user_events_collection.insert_one(event)

            logger.debug(f"Processed dashboard view for user {user_id}, section: {event['details']['section']}")

    async def _calculate_dashboard_metrics(self, db: Session):
        """
        Calculate dashboard engagement metrics for users.

        Args:
            db (Session): Database session
        """
        # Define the cutoff time (e.g., last day)
        cutoff_time = datetime.utcnow() - timedelta(days=1)

        # Query users who have viewed the dashboard recently
        active_users = db.query(User.id).join(UserSession).join(PageView).filter(
            PageView.view_time >= cutoff_time,
            PageView.url.like('/dashboard%')
        ).distinct().all()

        active_user_ids = [user.id for user in active_users]

        for user_id in active_user_ids:
            # Get all dashboard views for this user
            views = db.query(PageView).join(UserSession).filter(
                UserSession.user_id == user_id,
                PageView.view_time >= cutoff_time,
                PageView.url.like('/dashboard%')
            ).all()

            # Calculate metrics
            total_views = len(views)
            total_duration = sum(view.duration or 0 for view in views)
            avg_duration = total_duration / total_views if total_views > 0 else 0

            # Get distinct sections viewed
            sections = set(self._extract_dashboard_section(view.url) for view in views)

            # Create a metrics document
            metrics = {
                "user_id": user_id,
                "metric_type": "dashboard_engagement",
                "period_start": cutoff_time,
                "period_end": datetime.utcnow(),
                "metrics": {
                    "total_views": total_views,
                    "total_duration": total_duration,
                    "avg_duration": avg_duration,
                    "distinct_sections": list(sections),
                    "frequency": total_views / 24.0  # Views per hour
                }
            }

            # Store the metrics in MongoDB
            get_mongo_collection("user_metrics").insert_one(metrics)

            logger.debug(
                f"Calculated dashboard metrics for user {user_id}: {total_views} views, {avg_duration:.1f}s avg duration")

    async def _send_data_to_analysis_agents(self):
        """
        Send collected data to analysis agents.
        """
        # Get recent dashboard metrics
        metrics = list(get_mongo_collection("user_metrics").find(
            {"metric_type": "dashboard_engagement"},
            sort=[("period_end", -1)],
            limit=100
        ))

        # Send to Frequency Analysis Agent
        frequency_data = {
            "dashboard_metrics": [
                {
                    "user_id": metric["user_id"],
                    "timestamp": metric["period_end"],
                    "frequency": metric["metrics"]["frequency"],
                    "total_views": metric["metrics"]["total_views"],
                    "total_duration": metric["metrics"]["total_duration"]
                }
                for metric in metrics
            ],
            "channel": NotificationChannel.DASHBOARD
        }
        await self.send_message(AgentType.FREQUENCY_ANALYSIS, frequency_data)

        # Send to Type Analysis Agent
        content_data = {
            "dashboard_section_views": [
                {
                    "user_id": metric["user_id"],
                    "timestamp": metric["period_end"],
                    "sections": metric["metrics"]["distinct_sections"]
                }
                for metric in metrics
            ]
        }
        await self.send_message(AgentType.TYPE_ANALYSIS, content_data)

        # Send to Channel Analysis Agent
        channel_data = {
            "channel_engagement": [
                {
                    "user_id": metric["user_id"],
                    "timestamp": metric["period_end"],
                    "channel": NotificationChannel.DASHBOARD,
                    "engagement_level": self._calculate_engagement_level(metric["metrics"])
                }
                for metric in metrics
            ]
        }
        await self.send_message(AgentType.CHANNEL_ANALYSIS, channel_data)

        logger.info(f"Sent dashboard metrics for {len(metrics)} users to analysis agents")

    def _extract_dashboard_section(self, url: str) -> str:
        """
        Extract the dashboard section from a URL.

        Args:
            url (str): The URL to extract from

        Returns:
            str: The dashboard section
        """
        # Dashboard URLs are expected to be in the format /dashboard/section
        parts = url.strip('/').split('/')
        if len(parts) > 1 and parts[0] == 'dashboard':
            return parts[1] if len(parts) > 1 else 'main'
        return 'main'

    def _calculate_engagement_level(self, metrics: Dict[str, Any]) -> float:
        """
        Calculate an engagement level score from metrics.

        Args:
            metrics (Dict[str, Any]): The metrics to calculate from

        Returns:
            float: Engagement level score (0-1)
        """
        # Simple scoring based on frequency and duration
        frequency_score = min(1.0, metrics["frequency"] / 5.0)  # 5+ views per hour = max score
        duration_score = min(1.0, metrics["avg_duration"] / 300.0)  # 5+ mins avg = max score
        sections_score = min(1.0, len(metrics["distinct_sections"]) / 5.0)  # 5+ sections = max score

        # Combined score with weights
        return 0.4 * frequency_score + 0.4 * duration_score + 0.2 * sections_score

    async def handle_message(self, message: Dict[str, Any], sender: Dict[str, Any]):
        """
        Handle messages from other agents.

        Args:
            message (Dict[str, Any]): The message content
            sender (Dict[str, Any]): Information about the sender
        """
        # Feedback from Notification Management Layer
        if "view_data" in message and sender.get("agent_type") == AgentType.DASHBOARD_ALERT:
            notification_views = message["view_data"]

            # Store notification interaction data
            for view in notification_views:
                event = {
                    "user_id": view["user_id"],
                    "event_type": "notification_interaction",
                    "channel": NotificationChannel.DASHBOARD,
                    "timestamp": view["timestamp"],
                    "details": {
                        "notification_id": view["notification_id"],
                        "action": view["action"],
                        "duration": view.get("duration")
                    }
                }
                self.user_events_collection.insert_one(event)

            logger.info(f"Processed {len(notification_views)} dashboard notification interactions")