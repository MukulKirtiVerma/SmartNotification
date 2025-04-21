import sys
import logging
from pathlib import Path

from loguru import logger

from config.config import current_config


def setup_logging():
    """Configure logging for the application."""
    # Remove default loguru handler
    logger.remove()

    # Configure console logging
    logger.add(
        sys.stdout,
        level=current_config.LOG_LEVEL,
        format=current_config.LOG_FORMAT
    )

    # Configure file logging
    log_folder = Path("logs")
    log_folder.mkdir(exist_ok=True)

    logger.add(
        log_folder / "notification_system_{time}.log",
        rotation="100 MB",
        retention="30 days",
        level=current_config.LOG_LEVEL,
        format=current_config.LOG_FORMAT
    )

    # Configure different log level for third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

    logger.info("Logging configured")

    return logger


def get_logger():
    """Get the configured logger."""
    return logger