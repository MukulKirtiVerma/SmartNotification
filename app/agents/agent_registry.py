import asyncio
from collections import defaultdict
from typing import Dict, List, Any, Callable, Awaitable
import uuid

from loguru import logger

from config.constants import AgentType


class AgentRegistry:
    """
    Registry for managing all agents in the system.
    Handles agent registration, discovery, and message passing between agents.
    """
    # Map of agent types to list of agent instances
    _agents = defaultdict(list)

    # Message queue for agent communication
    _message_queues = defaultdict(asyncio.Queue)

    # For tracking registry statistics
    _stats = {
        "registered_agents": 0,
        "messages_delivered": 0,
        "active_agent_types": set()
    }

    @classmethod
    def register_agent(cls, agent_type: str, agent_instance):
        """
        Register an agent with the registry.

        Args:
            agent_type (str): Type of the agent
            agent_instance: Instance of the agent to register
        """
        cls._agents[agent_type].append(agent_instance)
        cls._stats["registered_agents"] += 1
        cls._stats["active_agent_types"].add(agent_type)
        logger.info(f"Agent {agent_instance.agent_id} registered as {agent_type}")

    @classmethod
    def unregister_agent(cls, agent_type: str, agent_id: str):
        """
        Unregister an agent from the registry.

        Args:
            agent_type (str): Type of the agent
            agent_id (str): ID of the agent to unregister

        Returns:
            bool: True if agent was successfully unregistered, False otherwise
        """
        if agent_type in cls._agents:
            before_count = len(cls._agents[agent_type])
            cls._agents[agent_type] = [a for a in cls._agents[agent_type] if a.agent_id != agent_id]
            after_count = len(cls._agents[agent_type])

            if before_count > after_count:
                cls._stats["registered_agents"] -= 1
                if not cls._agents[agent_type]:
                    cls._stats["active_agent_types"].remove(agent_type)
                logger.info(f"Agent {agent_id} unregistered from {agent_type}")
                return True

        logger.warning(f"Failed to unregister agent {agent_id} from {agent_type}: not found")
        return False

    @classmethod
    def get_agents(cls, agent_type: str = None):
        """
        Get all registered agents of a specific type, or all agents if type is None.

        Args:
            agent_type (str, optional): Type of agents to get. Defaults to None.

        Returns:
            list: List of agent instances
        """
        if agent_type:
            return cls._agents.get(agent_type, [])

        # If no type specified, return all agents
        all_agents = []
        for agents in cls._agents.values():
            all_agents.extend(agents)
        return all_agents

    @classmethod
    async def deliver_message(cls, target_agent_type: str, message_envelope: Dict[str, Any]):
        """
        Deliver a message to all agents of a specific type.

        Args:
            target_agent_type (str): Type of agents to deliver the message to
            message_envelope (Dict[str, Any]): Message envelope with metadata

        Returns:
            int: Number of agents the message was delivered to
        """
        # Get all agents of the target type
        target_agents = cls._agents.get(target_agent_type, [])

        # If no agents of this type, log and return
        if not target_agents:
            logger.warning(f"No agents of type {target_agent_type} to deliver message to")
            return 0

        # Add the message to the queue for each agent
        for agent in target_agents:
            # Add custom recipient field to message
            message_with_recipient = message_envelope.copy()
            message_with_recipient["recipient"] = {
                "agent_id": agent.agent_id,
                "agent_type": agent.agent_type,
                "agent_name": agent.agent_name
            }

            # Put the message in the agent's queue
            await cls._message_queues[agent.agent_id].put(message_with_recipient)

        cls._stats["messages_delivered"] += len(target_agents)
        logger.debug(f"Message delivered to {len(target_agents)} agents of type {target_agent_type}")
        return len(target_agents)

    @classmethod
    async def process_agent_messages(cls, agent_id: str, handler: Callable[[Dict[str, Any]], Awaitable[None]]):
        """
        Process all messages in the queue for a specific agent.

        Args:
            agent_id (str): ID of the agent to process messages for
            handler (callable): Async function to handle each message
        """
        # Get the queue for this agent
        queue = cls._message_queues[agent_id]

        # Process all messages in the queue
        while not queue.empty():
            message = await queue.get()
            try:
                await handler(message)
                queue.task_done()
            except Exception as e:
                logger.error(f"Error processing message for agent {agent_id}: {str(e)}")
                queue.task_done()  # Mark as done even if there was an error

    @classmethod
    def get_stats(cls):
        """
        Get statistics about the registry.

        Returns:
            Dict[str, Any]: Registry statistics
        """
        return {
            "registered_agents": cls._stats["registered_agents"],
            "messages_delivered": cls._stats["messages_delivered"],
            "active_agent_types": list(cls._stats["active_agent_types"]),
            "agents_by_type": {k: len(v) for k, v in cls._agents.items()}
        }