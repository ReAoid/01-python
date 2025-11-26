from typing import Optional
from backend.core.agent.agent import Agent
from backend.core.llm.llm_interface import LLMInterface
from backend.core.tools.registry import ToolRegistry
from backend.core.memory.message import UserMessage, SystemMessage, AssistantMessage
from backend.core.logger.log_system import logger
from backend.core.config import Config

class PlanAndExecuteAgent(Agent):
    pass