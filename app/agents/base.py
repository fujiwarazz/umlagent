from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import List, Literal, Optional

from pydantic import BaseModel, Field,model_validator
from llm import LLM
from utils.logger import logger
from utils.entity import AgentState, Memory, Message
from config.llm_config import llm_settings
class BaseAgent(ABC,BaseModel):
    class Config:
        arbitrary_types_allowed = True
        extra = "allow"  
        
    name: str = Field(..., description="Unique name of the agent")
    
    system_prompt: Optional[str] = Field(
        None, description="系统prompt"
    )
    
    next_step_prompt: Optional[str] = Field(
        None, description="让llm进行下一步骤的prompt,用于让agent自己进行下一步操作"
    )
    
    llm: LLM = Field(default_factory=LLM, description="选择的llm模型,")
    memory: Memory = Field(default_factory=Memory, description="用于保存LLM记忆")
    
    state: AgentState = Field(
        default=AgentState.IDLE, description="用于表示LLM的状态,作用为判断是否可以进行下一步骤"
    )
    
    max_steps: int = Field(default=10, description="执行任务最大步骤数")
    current_step: int = Field(default=0, description="当前步骤数")
    
    @model_validator(mode="after")
    def initialize_agent(self) -> "BaseAgent":
        if self.llm is None or not isinstance(self.llm, LLM):
            print(f"llm seetings:{llm_settings}")
            self.llm = LLM(config_name=self.name.lower(),llm_config = llm_settings)
        if not isinstance(self.memory, Memory):
            self.memory = Memory()
        return self
    
    @asynccontextmanager
    async def state_context(self, new_state: AgentState):
        if not isinstance(new_state, AgentState):
            raise ValueError(f"Invalid state: {new_state}")

        previous_state = self.state
        self.state = new_state
        try:
            yield
        except Exception as e:
            self.state = AgentState.ERROR 
            raise e
        finally:
            self.state = previous_state  
    

    def update_memory(
        self,
        role: Literal["user", "system", "assistant", "tool"],
        content: str,
        **kwargs,
    ) -> None:
       
        message_map = {
            "user": Message.user_message,
            "system": Message.system_message,
            "assistant": Message.assistant_message,
            "tool": lambda content, **kw: Message.tool_message(content, **kw),
        }

        if role not in message_map:
            raise ValueError(f"Unsupported message role: {role}")

        msg_factory = message_map[role]
        msg = msg_factory(content, **kwargs) if role == "tool" else msg_factory(content)
        self.memory.add_message(msg)
    
    # def summerize_memories(self, count=0):
    #     """总结agent的memory,用于减少模型上下文长度"""
    #     messages = self.memory.messages
    #     if count >0:
    #         prev_messages = messages[:count]
            
    #         ##todo: update memory
    #         summary = self.llm.summerize_memories(prev_messages)
    #         messages = [summary] + messages[count:]
            
    #         self.memory.messages = messages
    #     else:
    #         raise ValueError("memory summerized count must be greater than 0")


    # agent的运行函数，所有agent都通用，run -> step call
    async def run(self, query: Optional[str] = None) -> str:
        """Execute the agent's main loop asynchronously.

        Args:
            query: Optional initial user query to process.

        Returns:
            A string summarizing the execution results.

        Raises:
            RuntimeError: If the agent is not in IDLE state at start.
        """
        if self.state != AgentState.IDLE:
            raise RuntimeError(f"Cannot run agent from state: {self.state}")

        if query:
            self.update_memory("user", query)

        results: List[str] = []
        async with self.state_context(AgentState.RUNNING):
            while self.current_step < self.max_steps and self.state != AgentState.FINISHED:
                self.current_step += 1
                logger.info(f"Executing step {self.current_step}/{self.max_steps}")
                # current step llm called result
                step_result = await self.step()
                ## todo: 新增等待超时重试机制
                
                results.append(f"Step {self.current_step}: {step_result}")

            if self.current_step >= self.max_steps:
                results.append(f"Terminated: Reached max steps ({self.max_steps})")

        return "\n".join(results) if results else "No steps executed"


    @abstractmethod
    async def step(self) -> str:
        """
            执行一个步骤
        """
        pass
        
    @property
    def messages(self) -> List[Message]:
        """Retrieve a list of messages from the agent's memory."""
        return self.memory.messages

    @messages.setter
    def messages(self, value: List[Message]):
        """Set the list of messages in the agent's memory."""
        self.memory.messages = value
