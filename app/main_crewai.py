import asyncio
import os
import sys
import signal
import uvicorn
import threading
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

from config.config import current_config

# CrewAI imports
from crewai import Crew, Agent, Task, Process
from crewai.tools.base_tool import Tool

# --- Initialize FastAPI App ---
app = FastAPI(
    title=current_config.API_TITLE,
    description=current_config.API_DESCRIPTION,
    version=current_config.API_VERSION,
    debug=current_config.API_DEBUG
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routes
app.include_router(api_router, prefix=current_config.API_PREFIX)

# --- Logging Setup ---
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

# --- Global Variables ---
crew = None
agent_loop = asyncio.new_event_loop()
original_agents = {}

# --- Helper Functions ---

def run_agent_loop_in_thread():
    asyncio.set_event_loop(agent_loop)
    agent_loop.run_forever()

agent_thread = threading.Thread(target=run_agent_loop_in_thread, daemon=True)
agent_thread.start()  # Start the thread immediately at boot

def create_agent_tools():
    """Create CrewAI tools that connect to your agents"""
    tools = {}

    # Instantiate agents
    original_agents["dashboard_tracker"] = DashboardTrackerAgent()
    original_agents["email_engagement"] = EmailEngagementAgent()
    original_agents["mobile_app_events"] = MobileAppEventsAgent()
    original_agents["sms_interaction"] = SMSInteractionAgent()
    original_agents["frequency_analysis"] = FrequencyAnalysisAgent()
    original_agents["type_analysis"] = TypeAnalysisAgent()
    original_agents["channel_analysis"] = ChannelAnalysisAgent()
    original_agents["user_profile"] = UserProfileAgent()
    original_agents["recommendation"] = RecommendationAgent()
    original_agents["ab_testing"] = ABTestingAgent()
    original_agents["email_service"] = EmailServiceAgent()
    original_agents["push_notification"] = PushNotificationAgent()
    original_agents["sms_gateway"] = SMSGatewayAgent()
    original_agents["dashboard_alert"] = DashboardAlertAgent()

    # Define async wrapper
    async def run_agent_process(agent_name):
        agent = original_agents.get(agent_name)
        if not agent:
            return f"Agent {agent_name} not found"
        future = asyncio.run_coroutine_threadsafe(agent.process(), agent_loop)
        try:
            result = future.result(timeout=30)
            return f"Agent {agent_name} process completed: {result}"
        except Exception as e:
            return f"Error running agent {agent_name}: {str(e)}"

    # Wrap all agents with Tools
    agent_tool_map = {
        "dashboard_tracking": ("track_dashboard_activity", "Track dashboard user activity", "dashboard_tracker"),
        "email_engagement_tracking": ("track_email_engagement", "Track email opens, clicks", "email_engagement"),
        "mobile_event_tracking": ("track_mobile_events", "Track mobile app notifications", "mobile_app_events"),
        "sms_tracking": ("track_sms_interactions", "Track SMS responses", "sms_interaction"),
        "analyze_frequency": ("analyze_notification_frequency", "Analyze notification frequency", "frequency_analysis"),
        "analyze_content_types": ("analyze_content_preferences", "Analyze notification content preferences", "type_analysis"),
        "analyze_channels": ("analyze_channel_preferences", "Analyze preferred notification channels", "channel_analysis"),
        "update_user_profiles": ("update_user_profiles", "Update user profile preferences", "user_profile"),
        "generate_recommendations": ("generate_recommendations", "Generate notification strategies", "recommendation"),
        "run_ab_tests": ("run_ab_tests", "Run A/B tests on notifications", "ab_testing"),
        "send_emails": ("send_email_notifications", "Send email notifications", "email_service"),
        "send_push": ("send_push_notifications", "Send push notifications", "push_notification"),
        "send_sms": ("send_sms_notifications", "Send SMS notifications", "sms_gateway"),
        "send_dashboard_alerts": ("send_dashboard_alerts", "Send dashboard alerts", "dashboard_alert"),
    }

    for tool_key, (name, desc, agent_name) in agent_tool_map.items():
        print(f"Creating tool: {name} with agent {agent_name}")  # Debugging line
        tools[tool_key] = Tool(
            name=name,
            description=desc,
            func=lambda agent_name: run_agent_process(agent_name)
        )

    return tools

def create_crew_agents(tools):
    """Define CrewAI agents based on Tools"""
    agents = [
        Agent(name="DashboardTracker", role="Dashboard Activity Monitor", goal="Track dashboard usage", tools=[tools["dashboard_tracking"]],     backstory="Some relevant information about the agent",
),
        Agent(name="EmailEngagement", role="Email Engagement Tracker", goal="Analyze email metrics", tools=[tools["email_engagement_tracking"]],    backstory="Some relevant information about the agent",
),
        Agent(name="MobileAppEvents", role="Mobile App Event Tracker", goal="Track mobile interactions", tools=[tools["mobile_event_tracking"]],     backstory="Some relevant information about the agent",
),
        Agent(name="SMSInteraction", role="SMS Response Tracker", goal="Track SMS metrics", tools=[tools["sms_tracking"]],     backstory="Some relevant information about the agent",
),
        Agent(name="FrequencyAnalysis", role="Frequency Analyzer", goal="Optimize notification timing", tools=[tools["analyze_frequency"]],     backstory="Some relevant information about the agent",
),
        Agent(name="TypeAnalysis", role="Content Preference Analyzer", goal="Analyze content types", tools=[tools["analyze_content_types"]],     backstory="Some relevant information about the agent",
),
        Agent(name="ChannelAnalysis", role="Channel Preference Analyzer", goal="Analyze preferred channels", tools=[tools["analyze_channels"]],     backstory="Some relevant information about the agent",
),
        Agent(name="UserProfile", role="User Profile Updater", goal="Update user profiles", tools=[tools["update_user_profiles"]],     backstory="Some relevant information about the agent",
),
        Agent(name="RecommendationSystem", role="Recommendation Engine", goal="Suggest notification strategies", tools=[tools["generate_recommendations"]],     backstory="Some relevant information about the agent",
),
        Agent(name="ABTesting", role="A/B Testing Manager", goal="Run notification tests", tools=[tools["run_ab_tests"]],     backstory="Some relevant information about the agent",
),
        Agent(name="EmailService", role="Email Notification Sender", goal="Send email alerts", tools=[tools["send_emails"]],     backstory="Some relevant information about the agent",
),
        Agent(name="PushNotification", role="Push Notification Sender", goal="Send push alerts", tools=[tools["send_push"]],     backstory="Some relevant information about the agent",
),
        Agent(name="SMSGateway", role="SMS Sender", goal="Deliver SMS alerts", tools=[tools["send_sms"]],     backstory="Some relevant information about the agent",
),
        Agent(name="DashboardAlert", role="Dashboard Alert Sender", goal="Show dashboard notifications", tools=[tools["send_dashboard_alerts"]],     backstory="Some relevant information about the agent",
),
    ]
    return agents


def create_crew_tasks(agents):
    """Create tasks corresponding to agents"""
    tasks = []
    task_descriptions = [
        "Track dashboard user activities",
        "Track email notification engagements",
        "Track mobile app notification interactions",
        "Track SMS notification responses",
        "Analyze notification frequency",
        "Analyze preferred notification types",
        "Analyze preferred notification channels",
        "Update user preference profiles",
        "Generate delivery recommendations",
        "Run A/B tests on notification strategies",
        "Send email notifications",
        "Send mobile push notifications",
        "Send SMS notifications",
        "Display dashboard notifications",
    ]

    # Create all tasks as synchronous except the last one
    for i, (agent, desc) in enumerate(zip(agents, task_descriptions)):
        # Only make the last task asynchronous
        is_async = (i == len(agents) - 1)

        tasks.append(Task(
            description=desc,
            agent=agent,
            expected_output=f"{desc} completed",
            async_execution=is_async  # Only True for the last task
        ))

    return tasks

# --- Initialize Crew ---
@app.on_event("startup")
async def startup_event():
    global crew
    tools = create_agent_tools()
    agents = create_crew_agents(tools)
    tasks = create_crew_tasks(agents)
    crew = Crew(
        agents=agents,
        tasks=tasks,
        process=Process.sequential  # or Process.concurrent if you want
    )
    logger.info("Crew initialized successfully.")

# --- Uvicorn Run ---
if __name__ == "__main__":
    uvicorn.run("app.main_crewai:app", host="0.0.0.0", port=8000, reload=True)
