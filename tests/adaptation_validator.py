# adaptation_validator.py - updated for newer SQLAlchemy versions
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import func, desc, case, literal
from app.db.database import get_db
from app.db.models import (
    User, Notification, NotificationEngagement,
    UserSession, PageView, UserMetric
)


async def validate_adaptation():
    """Validate that notification frequency correlates with user behavior"""
    print("Validating notification adaptation to user behavior")

    db = next(get_db())
    results = {}

    # Get users grouped by activity level based on the prefix in their username
    high_activity_users = db.query(User.id).filter(User.username.like("high_%")).all()
    medium_activity_users = db.query(User.id).filter(User.username.like("medium_%")).all()
    low_activity_users = db.query(User.id).filter(User.username.like("low_%")).all()

    # Extract IDs
    high_activity_ids = [user.id for user in high_activity_users]
    medium_activity_ids = [user.id for user in medium_activity_users]
    low_activity_ids = [user.id for user in low_activity_users]

    # Get notification counts for each group over the last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    for group_name, user_ids in [
        ("high_activity", high_activity_ids),
        ("medium_activity", medium_activity_ids),
        ("low_activity", low_activity_ids)
    ]:
        if not user_ids:
            continue

        # Count notifications sent to this user group
        notification_count = db.query(
            func.count(Notification.id)
        ).filter(
            Notification.user_id.in_(user_ids),
            Notification.created_at > thirty_days_ago,
            Notification.is_sent == True
        ).scalar() or 0

        # Get engagement statistics using the updated case syntax
        opens_count = db.query(
            func.count(NotificationEngagement.id)
        ).join(
            Notification,
            NotificationEngagement.notification_id == Notification.id
        ).filter(
            Notification.user_id.in_(user_ids),
            NotificationEngagement.timestamp > thirty_days_ago,
            NotificationEngagement.action == 'open'
        ).scalar() or 0

        clicks_count = db.query(
            func.count(NotificationEngagement.id)
        ).join(
            Notification,
            NotificationEngagement.notification_id == Notification.id
        ).filter(
            Notification.user_id.in_(user_ids),
            NotificationEngagement.timestamp > thirty_days_ago,
            NotificationEngagement.action == 'click'
        ).scalar() or 0

        total_engagements = db.query(
            func.count(NotificationEngagement.id)
        ).join(
            Notification,
            NotificationEngagement.notification_id == Notification.id
        ).filter(
            Notification.user_id.in_(user_ids),
            NotificationEngagement.timestamp > thirty_days_ago
        ).scalar() or 0

        # Get session counts
        session_count = db.query(
            func.count(UserSession.id)
        ).filter(
            UserSession.user_id.in_(user_ids),
            UserSession.started_at > thirty_days_ago
        ).scalar() or 0

        # Get average session duration - using a simpler approach
        if session_count > 0:
            # Only consider sessions that have ended
            avg_duration = db.query(
                func.avg(func.extract('epoch', UserSession.ended_at) - func.extract('epoch', UserSession.started_at))
            ).filter(
                UserSession.user_id.in_(user_ids),
                UserSession.started_at > thirty_days_ago,
                UserSession.ended_at != None
            ).scalar() or 0
        else:
            avg_duration = 0

        # Get page views per session
        page_view_count = db.query(
            func.count(PageView.id)
        ).join(
            UserSession,
            PageView.session_id == UserSession.id
        ).filter(
            UserSession.user_id.in_(user_ids),
            PageView.view_time > thirty_days_ago
        ).scalar() or 0

        avg_page_views = page_view_count / session_count if session_count > 0 else 0

        # Calculate metrics
        avg_notifications = notification_count / len(user_ids) if user_ids else 0
        engagement_rate = total_engagements / notification_count if notification_count > 0 else 0
        open_rate = opens_count / notification_count if notification_count > 0 else 0
        click_rate = clicks_count / notification_count if notification_count > 0 else 0

        # Store results
        results[group_name] = {
            "user_count": len(user_ids),
            "avg_notifications_per_user": avg_notifications,
            "engagement_rate": engagement_rate,
            "open_rate": open_rate,
            "click_rate": click_rate,
            "avg_sessions": session_count / len(user_ids) if user_ids else 0,
            "avg_session_duration": avg_duration,
            "avg_page_views_per_session": avg_page_views
        }

    # Analyze adaptation effectiveness
    if all(k in results for k in ["high_activity", "low_activity"]):
        high_to_low_ratio = (
            results["high_activity"]["avg_notifications_per_user"] /
            results["low_activity"]["avg_notifications_per_user"]
            if results["low_activity"]["avg_notifications_per_user"] > 0 else float('inf')
        )

        print("\n=== ADAPTATION ANALYSIS RESULTS ===")
        print(
            f"High activity users ({results['high_activity']['user_count']}): {results['high_activity']['avg_notifications_per_user']:.2f} notifications/user")
        print(f"- Engagement rate: {results['high_activity']['engagement_rate'] * 100:.2f}%")
        print(f"- Click rate: {results['high_activity']['click_rate'] * 100:.2f}%")
        print(f"- Average sessions: {results['high_activity']['avg_sessions']:.2f}")
        print(f"- Average pages/session: {results['high_activity']['avg_page_views_per_session']:.2f}")

        if 'medium_activity' in results:
            print(
                f"\nMedium activity users ({results['medium_activity']['user_count']}): {results['medium_activity']['avg_notifications_per_user']:.2f} notifications/user")
            print(f"- Engagement rate: {results['medium_activity']['engagement_rate'] * 100:.2f}%")
            print(f"- Click rate: {results['medium_activity']['click_rate'] * 100:.2f}%")
            print(f"- Average sessions: {results['medium_activity']['avg_sessions']:.2f}")
            print(f"- Average pages/session: {results['medium_activity']['avg_page_views_per_session']:.2f}")

        print(
            f"\nLow activity users ({results['low_activity']['user_count']}): {results['low_activity']['avg_notifications_per_user']:.2f} notifications/user")
        print(f"- Engagement rate: {results['low_activity']['engagement_rate'] * 100:.2f}%")
        print(f"- Click rate: {results['low_activity']['click_rate'] * 100:.2f}%")
        print(f"- Average sessions: {results['low_activity']['avg_sessions']:.2f}")
        print(f"- Average pages/session: {results['low_activity']['avg_page_views_per_session']:.2f}")

        print(f"\nHigh-to-low notification ratio: {high_to_low_ratio:.2f}")

        # Expected pattern: high activity users get more notifications than low activity users
        if isinstance(high_to_low_ratio, float) and high_to_low_ratio > 1.5:
            print("\n✅ SYSTEM IS SUCCESSFULLY ADAPTING: High activity users receive more notifications")
        else:
            print("\n⚠️ SYSTEM IS NOT ADAPTING PROPERLY: High activity users should receive more notifications")

        # Check engagement rates
        if results["low_activity"]["engagement_rate"] > results["high_activity"]["engagement_rate"]:
            print("✅ Low-activity users show higher engagement per notification (quality over quantity working)")
        else:
            print("ℹ️ High-activity users show higher engagement per notification")

        # Channel analysis in a simplified form
        await analyze_channel_preferences()


async def analyze_channel_preferences():
    """Analyze which channels are preferred for different user groups"""
    db = next(get_db())

    # Get user groups
    high_activity_ids = [user.id for user in db.query(User.id).filter(User.username.like("high_%")).all()]
    medium_activity_ids = [user.id for user in db.query(User.id).filter(User.username.like("medium_%")).all()]
    low_activity_ids = [user.id for user in db.query(User.id).filter(User.username.like("low_%")).all()]

    print("\n=== CHANNEL PREFERENCE ANALYSIS ===")

    for group_name, user_ids in [
        ("high_activity", high_activity_ids),
        ("medium_activity", medium_activity_ids),
        ("low_activity", low_activity_ids)
    ]:
        if not user_ids:
            continue

        print(f"\n{group_name.upper()} USERS:")

        # Channel distribution
        channel_counts = db.query(
            Notification.channel,
            func.count(Notification.id).label('count')
        ).filter(
            Notification.user_id.in_(user_ids),
            Notification.is_sent == True
        ).group_by(
            Notification.channel
        ).order_by(
            desc('count')
        ).all()

        total = sum(c.count for c in channel_counts) if channel_counts else 0
        if total == 0:
            print("  No notifications found")
            continue

        for channel, count in channel_counts:
            percentage = (count / total) * 100
            print(f"  {channel}: {count} notifications ({percentage:.1f}%)")


if __name__ == "__main__":
    asyncio.run(validate_adaptation())