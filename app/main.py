# import asyncio
# import os
# import sys
# import signal
# import uvicorn
# import threading
# from datetime import datetime
# from apscheduler.schedulers.asyncio import AsyncIOScheduler
# from apscheduler.schedulers.background import BackgroundScheduler
#
# from fastapi import FastAPI, Depends, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from loguru import logger
# from sqlalchemy.orm import Session
#
# # Add the project root to the path
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#
# from app.db.database import get_db, Base, engine
# from app.api.routes import router as api_router
# from app.agents.base_agent import BaseAgent
# from app.agents.agent_registry import AgentRegistry
#
# # Import agents
# from app.agents.data_collection.dashboard_tracker import DashboardTrackerAgent
# from app.agents.data_collection.email_engagement import EmailEngagementAgent
# from app.agents.data_collection.mobile_app_events import MobileAppEventsAgent
# from app.agents.data_collection.sms_interaction import SMSInteractionAgent
# from app.agents.analysis.frequency_analysis import FrequencyAnalysisAgent
# from app.agents.analysis.type_analysis import TypeAnalysisAgent
# from app.agents.analysis.channel_analysis import ChannelAnalysisAgent
# from app.agents.decision_engine.user_profile import UserProfileAgent
# from app.agents.decision_engine.recommendation import RecommendationAgent
# from app.agents.decision_engine.ab_testing import ABTestingAgent
# from app.agents.notification.email_service import EmailServiceAgent
# from app.agents.notification.push_notification import PushNotificationAgent
# from app.agents.notification.sms_gateway import SMSGatewayAgent
# from app.agents.notification.dashboard_alert import DashboardAlertAgent
# from fastapi import FastAPI, BackgroundTasks
#
# from config.config import current_config
#
# # Initialize the application
# app = FastAPI(
#     title=current_config.API_TITLE,
#     description=current_config.API_DESCRIPTION,
#     version=current_config.API_VERSION,
#     debug=current_config.API_DEBUG
# )
#
# # Add CORS middleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
#
# # Include API routes
# app.include_router(api_router, prefix=current_config.API_PREFIX)
#
# # Configure logging
# logger.remove()
# logger.add(
#     sys.stdout,
#     level=current_config.LOG_LEVEL,
#     format=current_config.LOG_FORMAT
# )
# logger.add(
#     "logs/notification_system_{time}.log",
#     rotation="100 MB",
#     level=current_config.LOG_LEVEL,
#     format=current_config.LOG_FORMAT
# )
#
# # Global variables for agent management
# agents = []
# scheduler = None
# agent_tasks = {}
#
# # Create a separate event loop for agent operations
# agent_loop = asyncio.new_event_loop()
#
#
# def run_agent_loop_in_thread():
#     """Run the agent event loop in a separate thread."""
#     asyncio.set_event_loop(agent_loop)
#     agent_loop.run_forever()
#
#
# # Start the agent thread
# agent_thread = threading.Thread(target=run_agent_loop_in_thread, daemon=True)
#
#
# def schedule_agent_process(agent):
#     """Schedule an agent's process method to run periodically."""
#     agent_id = agent.agent_id
#
#     async def run_process():
#         try:
#             await agent.process()
#         except Exception as e:
#             logger.error(f"Error in agent {agent_id} process: {str(e)}")
#             import traceback
#             logger.error(traceback.format_exc())
#
#     # Schedule the agent to run every X seconds based on its check_interval
#     interval = agent.check_interval
#     scheduler.add_job(
#         run_process,
#         'interval',
#         seconds=interval,
#         id=f"agent_{agent_id}",
#         replace_existing=True
#     )
#     logger.info(f"Scheduled agent {agent.__class__.__name__} to run every {interval} seconds")
#
#
# @app.on_event("startup")
# async def startup_event():
#     """Initialize the application on startup."""
#     global scheduler, agent_thread
#
#     logger.info("Starting Smart Notification System")
#
#     try:
#         # Create database tables if they don't exist
#         Base.metadata.create_all(bind=engine)
#         logger.info("Database tables initialized")
#
#         # Start agent thread if not already running
#         if not agent_thread.is_alive():
#             agent_thread.start()
#             logger.info("Agent thread started")
#
#         # Create and start background scheduler for agents
#         scheduler = AsyncIOScheduler(event_loop=agent_loop)
#         scheduler.start()
#         logger.info("Agent scheduler started")
#
#         # Initialize agents (non-blocking)
#         asyncio.create_task(initialize_agents())
#
#         logger.info("Smart Notification System started successfully")
#     except Exception as e:
#         logger.error(f"Error during startup: {str(e)}")
#         import traceback
#         logger.error(traceback.format_exc())
#
#
# @app.on_event("shutdown")
# async def shutdown_event():
#     """Clean up resources on shutdown."""
#     global scheduler, agents, agent_loop
#
#     logger.info("Shutting down Smart Notification System")
#
#     # Stop scheduler if running
#     if scheduler and scheduler.running:
#         scheduler.shutdown()
#         logger.info("Agent scheduler stopped")
#
#     # Stop all agents
#     await stop_agents()
#
#     # Stop agent event loop
#     if not agent_loop.is_closed():
#         agent_loop.call_soon_threadsafe(agent_loop.stop)
#         logger.info("Agent event loop stopped")
#
#     logger.info("Smart Notification System shutdown complete")
#
#
# # Simple health check endpoint that doesn't rely on agents or database
# @app.get("/health")
# def health_check():
#     """Basic health check endpoint."""
#     global agents
#     return {
#         "status": "ok",
#         "timestamp": datetime.utcnow().isoformat(),
#         "agent_count": len(agents)
#     }
#
#
# async def initialize_agents():
#     """Initialize and register all agents."""
#     global agents
#
#     try:
#         # Create agent instances
#         agents = [
#             # Data Collection Layer
#             DashboardTrackerAgent(),
#             EmailEngagementAgent(),
#             MobileAppEventsAgent(),
#             SMSInteractionAgent(),
#
#             # Analysis Layer
#             FrequencyAnalysisAgent(),
#             TypeAnalysisAgent(),
#             ChannelAnalysisAgent(),
#
#             # Decision Engine
#             UserProfileAgent(),
#             RecommendationAgent(),
#             ABTestingAgent(),
#
#             # Notification Management Layer
#             EmailServiceAgent(),
#             PushNotificationAgent(),
#             SMSGatewayAgent(),
#             DashboardAlertAgent(),
#         ]
#
#         logger.info(f"Created {len(agents)} agent instances")
#
#         # Register each agent with the registry and schedule it
#         for i, agent in enumerate(agents):
#             # Submit initialization task to agent thread
#             future = asyncio.run_coroutine_threadsafe(
#                 initialize_single_agent(agent, i),
#                 agent_loop
#             )
#             # Wait for initial registration to complete
#             future.result(timeout=2)
#
#             # Add a small delay between agent registrations
#             await asyncio.sleep(0.1)
#
#         logger.info("All agents initialized and scheduled")
#     except Exception as e:
#         logger.error(f"Error initializing agents: {str(e)}")
#         import traceback
#         logger.error(traceback.format_exc())
#
#
# async def initialize_single_agent(agent, index):
#     """Initialize a single agent and schedule its processing."""
#     try:
#         # Register agent with registry
#         AgentRegistry.register_agent(agent.agent_type, agent)
#
#         # Schedule the agent's process method
#         schedule_agent_process(agent)
#
#         logger.info(f"Initialized agent {index + 1}/{len(agents)}: {agent.__class__.__name__}")
#     except Exception as e:
#         logger.error(f"Error initializing agent {agent.__class__.__name__}: {str(e)}")
#         raise
#
#
# async def stop_agents():
#     """Stop all running agents."""
#     global agents, scheduler
#
#     if not agents:
#         return
#
#     logger.info(f"Stopping {len(agents)} agents")
#
#     # Remove all scheduled jobs
#     if scheduler and scheduler.running:
#         scheduler.remove_all_jobs()
#
#     # Stop all agents
#     for agent in agents:
#         try:
#             # Submit stop task to agent thread
#             future = asyncio.run_coroutine_threadsafe(
#                 agent.stop(),
#                 agent_loop
#             )
#             # Wait for stop to complete with timeout
#             future.result(timeout=2)
#         except Exception as e:
#             logger.error(f"Error stopping agent {agent.__class__.__name__}: {str(e)}")
#
#     agents = []
#
#     logger.info("All agents stopped")
#
#
# # Define signal handlers for graceful shutdown
# def handle_exit_signal(sig, frame):
#     """Handle exit signals gracefully."""
#     logger.info(f"Received exit signal {sig}")
#
#     # Get the current event loop
#     try:
#         loop = asyncio.get_running_loop()
#     except RuntimeError:
#         # If no running loop, create a new one
#         loop = asyncio.new_event_loop()
#         asyncio.set_event_loop(loop)
#
#     # Schedule shutdown_event
#     loop.create_task(shutdown_event())
#
#     # Stop the loop after a small delay to allow shutdown_event to complete
#     def stop_loop():
#         logger.info("Stopping event loop...")
#         loop.stop()
#
#     loop.call_later(2, stop_loop)  # Give 2 seconds for graceful shutdown
#
#
# # Register signal handlers
# signal.signal(signal.SIGINT, handle_exit_signal)
# signal.signal(signal.SIGTERM, handle_exit_signal)
#
# if __name__ == "__main__":
#     # Add APScheduler to requirements.txt if not already there
#
#     # Use host 0.0.0.0 to make it accessible from all network interfaces
#     uvicorn.run(
#         "app.main:app",
#         host="0.0.0.0",  # Changed from 127.0.0.1 to make it externally accessible
#         port=8000,
#         reload=current_config.DEBUG,
#         log_level="debug"
#     )