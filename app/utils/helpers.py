from datetime import datetime, timedelta
import json
import uuid
import hashlib

from app.db.database import get_redis


def generate_unique_id(prefix=""):
    """Generate a unique ID."""
    return f"{prefix}{uuid.uuid4().hex}"


def get_time_period(dt=None):
    """
    Get the current time period based on the TimeOfDay class.

    Args:
        dt (datetime, optional): Datetime to check. Defaults to current time.

    Returns:
        str: Time period name
    """
    from config.constants import TimeOfDay

    if dt is None:
        dt = datetime.utcnow()

    hour = dt.hour

    for period, (start, end) in TimeOfDay.BOUNDARIES.items():
        if start <= hour < end:
            return period
        # Handle periods that cross midnight
        if start > end and (hour >= start or hour < end):
            return period

    return TimeOfDay.MORNING  # Default fallback


def calculate_engagement_score(open_rate, click_rate, dismiss_rate=0):
    """
    Calculate a normalized engagement score from rates.

    Args:
        open_rate (float): Rate of opens (0-1)
        click_rate (float): Rate of clicks (0-1)
        dismiss_rate (float, optional): Rate of dismisses (0-1). Defaults to 0.

    Returns:
        float: Engagement score (0-1)
    """
    # Weighted combination of positive engagement minus dismisses
    score = 0.3 * open_rate + 0.7 * click_rate - 0.2 * dismiss_rate

    # Clamp to 0-1 range
    return max(0, min(1, score))


def cache_get(key, default=None):
    """
    Get a value from Redis cache.

    Args:
        key (str): Cache key
        default: Default value if key doesn't exist

    Returns:
        The cached value or default
    """
    redis = get_redis()
    cached = redis.get(key)

    if cached is None:
        return default

    try:
        return json.loads(cached)
    except:
        return cached.decode('utf-8')


def cache_set(key, value, expire=3600):
    """
    Set a value in Redis cache.

    Args:
        key (str): Cache key
        value: Value to cache
        expire (int, optional): Expiration time in seconds. Defaults to 3600.
    """
    redis = get_redis()

    if isinstance(value, (dict, list)):
        value = json.dumps(value)

    redis.set(key, value, ex=expire)


def hash_password(password):
    """
    Hash a password securely.

    Args:
        password (str): Password to hash

    Returns:
        str: Hashed password
    """
    # This is a simple example - in production use a proper password hashing library
    salt = uuid.uuid4().hex
    return hashlib.sha256(salt.encode() + password.encode()).hexdigest() + ':' + salt


def verify_password(hashed_password, password):
    """
    Verify a password against a hash.

    Args:
        hashed_password (str): Stored password hash
        password (str): Password to verify

    Returns:
        bool: True if password matches
    """
    password_hash, salt = hashed_password.split(':')
    return password_hash == hashlib.sha256(salt.encode() + password.encode()).hexdigest()