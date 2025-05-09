from abc import ABC, abstractmethod
from typing import Optional

from pydantic import Field

from agents.base import BaseAgent
from llm import LLM
from utils.entity import AgentState, Memory

# class ReActAgent(BaseAgent,ABC):
#     class Config:
#         arbitrary_types_allowed = True
#         extra = "allow"  
        
#     name: str
#     description: Optional[str] = None

#     system_prompt: Optional[str] = None
#     next_step_prompt: Optional[str] = None

#     llm: Optional[LLM] = Field(default_factory=LLM)
#     memory: Memory = Field(default_factory=Memory)
#     state: AgentState = AgentState.IDLE

#     max_steps: int = 10
#     current_step: int = 0
    
#     @abstractmethod
#     async def think() -> bool:
#         """agent是否需要继续运行，如果是那么就会通过think更新后的memories进行act,否则就中断"""
        
    

#     @abstractmethod
#     async def act(self) -> str:
#         """Execute decided actions and return tool called result"""

    
#     async def step(self,) -> str:
#         act_res = await self.act()
#         if not act_res:
#             return f"agent {self.name} thinking completed, no actions needed"
#         return await self.act()


class ReActAgent(BaseAgent, ABC):
    name: str
    description: Optional[str] = None

    system_prompt: Optional[str] = None
    next_step_prompt: Optional[str] = None

    llm: Optional[LLM] = Field(default_factory=LLM)
    memory: Memory = Field(default_factory=Memory)
    state: AgentState = AgentState.IDLE

    max_steps: int = 10
    current_step: int = 0

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
