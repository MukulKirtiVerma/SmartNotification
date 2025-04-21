import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Base configuration class."""
    ENV = os.getenv("ENV", "development")
    DEBUG = ENV == "development"

    # Database configurations

    DATABASE_URL = os.getenv("DATABASE_URL",
                             "")
    REDIS_URL = os.getenv("REDIS_URL",
                          "")
    MONGODB_URL = os.getenv("MONGODB_URL",
                            "")

    # API configurations
    API_PREFIX = "/api/v1"
    API_DEBUG = DEBUG
    API_TITLE = "Smart Notification System API"
    API_VERSION = "1.0.0"
    API_DESCRIPTION = "API for interacting with the Smart Notification System"

    # JWT settings
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-for-jwt")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION = 3600  # 1 hour

    # Notification settings
    MAX_NOTIFICATIONS_PER_DAY = 10
    NOTIFICATION_COOLDOWN_MINUTES = 30

    # Agent configuration
    AGENT_CHECK_INTERVAL = 60  # seconds

    # Logging configuration
    LOG_LEVEL = "DEBUG" if DEBUG else "INFO"
    LOG_FORMAT = "{time} {level} {message}"

    # A/B Testing configuration
    AB_TEST_SAMPLE_SIZE = 1000
    AB_TEST_MIN_DURATION_DAYS = 7


class DevelopmentConfig(Config):
    """Development configuration."""
    pass


class TestingConfig(Config):
    """Testing configuration."""
    ENV = "testing"
    DEBUG = True
    DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://user:password@localhost:5432/notification_system_test")
    MONGODB_URL = os.getenv("TEST_MONGODB_URL", "mongodb://localhost:27017/notification_system_test")


class ProductionConfig(Config):
    """Production configuration."""
    ENV = "production"
    DEBUG = False
    MAX_NOTIFICATIONS_PER_DAY = 20

    # Override with production values
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")  # Must be set in production

    # Stricter logging in production
    LOG_LEVEL = "WARNING"


# Configuration dictionary to select the right configuration based on environment
config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig
}

# Get the current configuration
current_config = config_by_name[os.getenv("ENV", "development")]