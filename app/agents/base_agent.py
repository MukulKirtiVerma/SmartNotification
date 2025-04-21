import asyncio
import time
import traceback
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.db.database import get_db, get_mongo_collection
from app.db.models import AgentLog
from config.config import current_config
from config.constants import Collections, AgentType
from app.agents.agent_registry import AgentRegistry


class BaseAgent(ABC):
    """Base class for all agents in the system."""

    def __init__(self, agent_type: str, agent_name: str):
        """
        Initialize the base agent.

        Args:
            agent_type (str): Type of the agent (from AgentType constants)
            agent_name (str): Unique name for this agent instance
        """
        self.agent_type = agent_type
        self.agent_name = agent_name
        self.agent_id = f"{agent_type}_{uuid.uuid4().hex[:8]}"
        self.running = False
        self.check_interval = current_config.AGENT_CHECK_INTERVAL
        self.log_collection = get_mongo_collection(Collections.AGENT_LOGS)
        self.last_run_time = None

        # Register with the agent registry
        AgentRegistry.register_agent(agent_type, self)

        logger.info(f"Agent {self.agent_id} ({agent_name}) initialized")

    async def start(self):
        """Start the agent's main loop."""
        self.running = True
        logger.info(f"Agent {self.agent_id} ({self.agent_name}) starting")

        while self.running:
            start_time = time.time()

            try:
                # Process any messages from other agents
                await AgentRegistry.process_agent_messages(self.agent_id, self.receive_message)

                # Run the agent's main processing logic
                await self.process()
                self.last_run_time = datetime.utcnow()

                # Log successful execution
                self._log_action("process", "success", {
                    "execution_time": time.time() - start_time
                })

            except Exception as e:
                # Log any exceptions that occur during processing
                error_details = {
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "execution_time": time.time() - start_time
                }
                self._log_action("process", "failure", error_details)
                logger.error(f"Error in agent {self.agent_id}: {str(e)}")
                logger.debug(traceback.format_exc())

            # Sleep until the next check interval
            elapsed = time.time() - start_time
            sleep_time = max(0, self.check_interval - elapsed)
            await asyncio.sleep(sleep_time)

    async def stop(self):
        """Stop the agent's main loop."""
        logger.info(f"Stopping agent {self.agent_id} ({self.agent_name})")
        self.running = False

        # Unregister from the agent registry
        AgentRegistry.unregister_agent(self.agent_type, self.agent_id)

    @abstractmethod
    async def process(self):
        """
        Main processing logic for the agent.
        This method should be implemented by all subclasses.
        """
        pass

    def _log_action(self, action: str, status: str, details: Dict[str, Any] = None):
        """
        Log an agent action to both SQL and MongoDB.

        Args:
            action (str): The action being performed
            status (str): The status of the action (success, failure, etc.)
            details (Dict[str, Any], optional): Additional details about the action
        """
        # Log to MongoDB (more detailed)
        log_entry = {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "agent_name": self.agent_name,
            "action": action,
            "status": status,
            "details": details or {},
            "timestamp": datetime.utcnow()
        }
        self.log_collection.insert_one(log_entry)

        # Log to SQL (summary)
        try:
            # Create a database session
            db = next(get_db())

            # Create and add the log entry
            agent_log = AgentLog(
                agent_type=self.agent_type,
                action=action,
                status=status,
                details=details,
                timestamp=datetime.utcnow()
            )
            db.add(agent_log)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to log to SQL: {str(e)}")

    async def send_message(self, target_agent_type: str, message: Dict[str, Any]):
        """
        Send a message to another agent.

        Args:
            target_agent_type (str): Type of the target agent
            message (Dict[str, Any]): Message to send
        """
        message_envelope = {
            "sender": {
                "agent_id": self.agent_id,
                "agent_type": self.agent_type,
                "agent_name": self.agent_name
            },
            "timestamp": datetime.utcnow().isoformat(),
            "message_id": str(uuid.uuid4()),
            "content": message
        }

        # Log the message sending
        self._log_action("send_message", "attempt", {
            "target_agent_type": target_agent_type,
            "message_id": message_envelope["message_id"]
        })

        # Deliver the message through the agent registry
        await AgentRegistry.deliver_message(target_agent_type, message_envelope)

        # Log successful delivery
        self._log_action("send_message", "success", {
            "target_agent_type": target_agent_type,
            "message_id": message_envelope["message_id"]
        })

    async def receive_message(self, message_envelope: Dict[str, Any]):
        """
        Process a received message from another agent.

        Args:
            message_envelope (Dict[str, Any]): The received message with metadata
        """
        sender = message_envelope.get("sender", {})
        message_id = message_envelope.get("message_id", "unknown")
        content = message_envelope.get("content", {})

        # Log message receipt
        self._log_action("receive_message", "received", {
            "sender_agent_id": sender.get("agent_id"),
            "sender_agent_type": sender.get("agent_type"),
            "message_id": message_id
        })

        # Process the message based on its content
        try:
            await self.handle_message(content, sender)

            # Log successful processing
            self._log_action("receive_message", "processed", {
                "sender_agent_id": sender.get("agent_id"),
                "message_id": message_id
            })
        except Exception as e:
            # Log failure to process message
            error_details = {
                "sender_agent_id": sender.get("agent_id"),
                "message_id": message_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            self._log_action("receive_message", "failed", error_details)
            logger.error(f"Error processing message in {self.agent_id}: {str(e)}")

    @abstractmethod
    async def handle_message(self, message: Dict[str, Any], sender: Dict[str, Any]):
        """
        Handle a message received from another agent.
        This method should be implemented by all subclasses.

        Args:
            message (Dict[str, Any]): The message content
            sender (Dict[str, Any]): Information about the sender
        """
        pass