from abc import ABC, abstractmethod
from typing import Optional,List

from pydantic import Field

from agents.base import BaseAgent
from llm import LLM
from utils.entity import AgentState, Memory

class ReActAgent(BaseAgent, ABC):
    name: str
    description: Optional[str] = "An agent that can reason and act based on its state"

    system_prompt: Optional[str] = None
    next_step_prompt: Optional[str] = None

    llm: Optional[LLM] = Field(default_factory=LLM)
    memory: Memory = Field(default_factory=Memory)
    state: AgentState = AgentState.IDLE

    max_steps: int = 10
    current_step: int = 0
    
    hands_offs:Optional[List[BaseAgent]] = None

    @abstractmethod
    async def think(self) -> bool:
        """Process current state and decide next action"""

    @abstractmethod
    async def act(self) -> str:
        """Execute decided actions and return tool called result"""

    async def step(self) -> str:
        """Execute a single step: think and act."""
        should_act = await self.think()
        if not should_act:
            return "Thinking complete - no action needed"
        return await self.act()
