import asyncio
import os
import sys
import signal
import uvicorn
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sqlalchemy.orm import Session

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import get_db, Base, engine
from app.api.routes import router as api_router
from app.agents.base_agent import BaseAgent
from app.agents.agent_registry import AgentRegistry

# Import agents
from app.agents.data_collection.dashboard_tracker import DashboardTrackerAgent
from app.agents.data_collection.email_engagement import EmailEngagementAgent
from app.agents.data_collection.mobile_app_events import MobileAppEventsAgent
from app.agents.data_collection.sms_interaction import SMSInteractionAgent
from app.agents.analysis.frequency_analysis import FrequencyAnalysisAgent
from app.agents.analysis.type_analysis import TypeAnalysisAgent
from app.agents.analysis.channel_analysis import ChannelAnalysisAgent
from app.agents.decision_engine.user_profile import UserProfileAgent
from app.agents.decision_engine.recommendation import RecommendationAgent
from app.agents.decision_engine.ab_testing import ABTestingAgent
from app.agents.notification.email_service import EmailServiceAgent
from app.agents.notification.push_notification import PushNotificationAgent
from app.agents.notification.sms_gateway import SMSGatewayAgent
from app.agents.notification.dashboard_alert import DashboardAlertAgent
from fastapi import FastAPI, BackgroundTasks

from config.config import current_config

# Initialize the application
app = FastAPI(
    title=current_config.API_TITLE,
    description=current_config.API_DESCRIPTION,
    version=current_config.API_VERSION,
    debug=current_config.API_DEBUG
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix=current_config.API_PREFIX)

# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    level=current_config.LOG_LEVEL,
    format=current_config.LOG_FORMAT
)
logger.add(
    "logs/notification_system_{time}.log",
    rotation="100 MB",
    level=current_config.LOG_LEVEL,
    format=current_config.LOG_FORMAT
)

# List of all agents to be started
agents = []


@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    logger.info("Starting Smart Notification System")

    try:
        # Create database tables if they don't exist
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized")

        # Initialize and start agents in background
        # asyncio.create_task(initialize_agents())

        logger.info("Smart Notification System started successfully")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        # Log the full exception traceback for debugging
        import traceback
        logger.error(traceback.format_exc())


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    logger.info("Shutting down Smart Notification System")

    # Stop all agents
    await stop_agents()

    logger.info("Smart Notification System shutdown complete")


# Simple health check endpoint that doesn't rely on agents or database
@app.get("/health")
def health_check():
    """Basic health check endpoint."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


async def initialize_agents():
    """Initialize and start all agents."""
    global agents

    try:
        agents.extend([
            DashboardTrackerAgent(),
            EmailEngagementAgent(),
            MobileAppEventsAgent(),
            SMSInteractionAgent(),

            FrequencyAnalysisAgent(),
            TypeAnalysisAgent(),
            ChannelAnalysisAgent(),

            UserProfileAgent(),
            RecommendationAgent(),
            ABTestingAgent(),

            EmailServiceAgent(),
            PushNotificationAgent(),
            SMSGatewayAgent(),
            DashboardAlertAgent(),
        ])

        logger.info(f"Starting {len(agents)} agents")

        # Start agents in separate background tasks
        for agent in agents:
            if hasattr(agent, "start") and callable(agent.start):
                # Create a separate task for each agent
                asyncio.create_task(agent.start())
                logger.info(f"Started agent: {agent.__class__.__name__}")
                # Small delay to avoid overwhelming the system with all agents at once
                await asyncio.sleep(0.1)

        logger.info("All agents started")
    except Exception as e:
        logger.error(f"Error initializing agents: {str(e)}")
        # Log the full exception traceback for debugging
        import traceback
        logger.error(traceback.format_exc())


async def stop_agents():
    """Stop all running agents."""
    global agents

    if not agents:
        return

    logger.info(f"Stopping {len(agents)} agents")

    # Stop all agents
    for agent in agents:
        try:
            await agent.stop()
        except Exception as e:
            logger.error(f"Error stopping agent {agent.__class__.__name__}: {str(e)}")

    agents = []

    logger.info("All agents stopped")


# Define signal handlers for graceful shutdown
def handle_exit_signal(sig, frame):
    """Handle exit signals gracefully."""
    logger.info(f"Received exit signal {sig}")

    # Get the current event loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # If no running loop, create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Schedule shutdown_event
    loop.create_task(shutdown_event())

    # Stop the loop after a small delay to allow shutdown_event to complete
    def stop_loop():
        logger.info("Stopping event loop...")
        loop.stop()

    loop.call_later(2, stop_loop)  # Give 2 seconds for graceful shutdown


# Register signal handlers
signal.signal(signal.SIGINT, handle_exit_signal)
signal.signal(signal.SIGTERM, handle_exit_signal)

if __name__ == "__main__":
    # Use host 0.0.0.0 to make it accessible from all network interfaces
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # Changed from 127.0.0.1 to make it externally accessible
        port=8000,
        reload=current_config.DEBUG,
        log_level="debug"
    )