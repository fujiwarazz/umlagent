from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import List, Literal, Optional

from pydantic import BaseModel, Field,model_validator
from llm import LLM
from utils.logger import logger
from utils.entity import AgentState, Memory, Message
from config.llm_config import llm_settings
from fastapi import FastAPI, WebSocket
class BaseAgent(ABC,BaseModel):
    class Config:
        arbitrary_types_allowed = True
        extra = "allow"  
        
    name: str = Field(..., description="Unique name of the agent")
    
    system_prompt: Optional[str] = Field(
        None, description="系统prompt"
    )
    websocket:WebSocket = Field(default=None)
    
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
    
    
    async def summerize_memories(self, count=10):
        """总结agent的memory,用于减少模型上下文长度"""
        messages = self.memory.messages
        if count >0:
            prev_messages = messages[:count]
            
            summary = self.llm.summerize_memories(prev_messages)
            messages = [summary] + messages[count:]
            
            self.memory.messages = messages
        else:
            raise ValueError("memory summerized count must be greater than 0")


    # agent的运行函数，所有agent都通用，run -> step call
    async def run(self, query: Optional[str] = None,websocket:Optional[WebSocket] = None) -> str:
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
        
        if websocket is not None:
            self.websocket = websocket
            logger.info(f"websocket initialized finish, state:{self.websocket.state}")

        results: List[str] = []
        times = 1
        async with self.state_context(AgentState.RUNNING):
            while self.current_step < self.max_steps and self.state != AgentState.FINISHED:
                self.current_step += 1
                logger.info(f"Executing step {self.current_step}/{self.max_steps}")
                # current step llm called result
                step_result = await self.step()
                ## todo: 新增等待超时重试机制
                
                results.append(f"Step {self.current_step}: {step_result}")
                
                ## 记忆总结，维护短期记忆
                if self.current_step == 10 * times:
                    tokens = self.memory.count_tokens()
                    if tokens >= 8192 // 2:
                        self.summerize_memories(count=10)

            if self.current_step >= self.max_steps:
                results.append(f"Terminated: Reached max steps ({self.max_steps})")

        return "\n".join(results) if results else "No steps executed"


    @abstractmethod
    async def step(self) -> str:
        """
            执行一个步骤
        """
        
        
    @property
    def messages(self) -> List[Message]:
        """Retrieve a list of messages from the agent's memory."""
        return self.memory.messages

    @messages.setter
    def messages(self, value: List[Message]):
        """Set the list of messages in the agent's memory."""
        self.memory.messages = value


# class BaseAgent(BaseModel, ABC):
#     """Abstract base class for managing agent state and execution.

#     Provides foundational functionality for state transitions, memory management,
#     and a step-based execution loop. Subclasses must implement the `step` method.
#     """

#     # Core attributes
#     name: str = Field(..., description="Unique name of the agent")
#     description: Optional[str] = Field(None, description="Optional agent description")

#     # Prompts
#     system_prompt: Optional[str] = Field(
#         None, description="System-level instruction prompt"
#     )
#     next_step_prompt: Optional[str] = Field(
#         None, description="Prompt for determining next action"
#     )

#     # Dependencies
#     llm: LLM = Field(default_factory=LLM, description="Language model instance")
#     memory: Memory = Field(default_factory=Memory, description="Agent's memory store")
#     state: AgentState = Field(
#         default=AgentState.IDLE, description="Current agent state"
#     )

#     # Execution control
#     max_steps: int = Field(default=10, description="Maximum steps before termination")
#     current_step: int = Field(default=0, description="Current step in execution")

#     duplicate_threshold: int = 2

#     class Config:
#         arbitrary_types_allowed = True
#         extra = "allow"  # Allow extra fields for flexibility in subclasses

#     # after说明在参数被初始化后再验证，before说明在初始化前验证，即验证原始输入
#     @model_validator(mode="after")
#     def initialize_agent(self) -> "BaseAgent":
#         """Initialize agent with default settings if not provided."""
#         if self.llm is None or not isinstance(self.llm, LLM):
#             self.llm = LLM(config_name=self.name.lower())
#         if not isinstance(self.memory, Memory):
#             self.memory = Memory()
#         return self

#     # @asynccontextmanager 允许我们使用 async with 语句来管理代码块的执行上下文。用于安全地管理 Agent 的状态转换
#     @asynccontextmanager
#     async def state_context(self, new_state: AgentState):
#         """Context manager for safe agent state transitions.

#         Args:
#             new_state: The state to transition to during the context.

#         Yields:
#             None: Allows execution within the new state.

#         Raises:
#             ValueError: If the new_state is invalid.
#         """
#         if not isinstance(new_state, AgentState):
#             raise ValueError(f"Invalid state: {new_state}")

#         previous_state = self.state
#         self.state = new_state
#         try:
#             yield
#         except Exception as e:
#             self.state = AgentState.ERROR  # Transition to ERROR on failure
#             raise e
#         finally:
#             # 无论如何，agent的状态都会被设定为先前的状态，
#             self.state = previous_state  # Revert to previous state

#     def update_memory(
#         self,
#         role: Literal["user", "system", "assistant", "tool"],
#         content: str,
#         **kwargs,
#     ) -> None:
#         """Add a message to the agent's memory.

#         Args:
#             role: The role of the message sender (user, system, assistant, tool).
#             content: The message content.
#             **kwargs: Additional arguments (e.g., tool_call_id for tool messages).

#         Raises:
#             ValueError: If the role is unsupported.
#         """
#         message_map = {
#             "user": Message.user_message,
#             "system": Message.system_message,
#             "assistant": Message.assistant_message,
#             "tool": lambda content, **kw: Message.tool_message(content, **kw),
#         }

#         if role not in message_map:
#             raise ValueError(f"Unsupported message role: {role}")

#         msg_factory = message_map[role]
#         msg = msg_factory(content, **kwargs) if role == "tool" else msg_factory(content)
#         self.memory.add_message(msg)

#     async def run(self, request: Optional[str] = None) -> str:
#         """Execute the agent's main loop asynchronously.

#         Args:
#             request: Optional initial user request to process.

#         Returns:
#             A string summarizing the execution results.

#         Raises:
#             RuntimeError: If the agent is not in IDLE state at start.
#         """
#         if self.state != AgentState.IDLE:
#             raise RuntimeError(f"Cannot run agent from state: {self.state}")

#         if request:
#             self.update_memory("user", request)

#         results: List[str] = []
#         async with self.state_context(AgentState.RUNNING):
#             while self.current_step < self.max_steps and self.state != AgentState.FINISHED:
#                 self.current_step += 1
#                 logger.info(f"Executing step {self.current_step}/{self.max_steps}")
#                 # current step llm called result
#                 step_result = await self.step()

#                 # Check for stuck state
#                 if self.is_stuck():
#                     self.handle_stuck_state()

#                 results.append(f"Step {self.current_step}: {step_result}")

#             if self.current_step >= self.max_steps:
#                 results.append(f"Terminated: Reached max steps ({self.max_steps})")

#         return "\n".join(results) if results else "No steps executed"


#     # 抽象方法由子类实现
#     @abstractmethod
#     async def step(self) -> str:
#         """Execute a single step in the agent's workflow.

#         Must be implemented by subclasses to define specific behavior.
#         """

#     def handle_stuck_state(self):
#         """Handle stuck state by adding a prompt to change strategy"""
#         stuck_prompt = "\
#         Observed duplicate responses. Consider new strategies and avoid repeating ineffective paths already attempted."
#         self.next_step_prompt = f"{stuck_prompt}\n{self.next_step_prompt}"
#         logger.warning(f"Agent detected stuck state. Added prompt: {stuck_prompt}")

#     def is_stuck(self) -> bool:
#         """Check if the agent is stuck in a loop by detecting duplicate content"""
#         if len(self.memory.messages) < 2:
#             return False

#         last_message = self.memory.messages[-1]
#         if not last_message.content:
#             return False

#         # Count identical content occurrences
#         duplicate_count = sum(
#             1
#             for msg in reversed(self.memory.messages[:-1])
#             if msg.role == "assistant" and msg.content == last_message.content
#         )

#         return duplicate_count >= self.duplicate_threshold

#     @property
#     def messages(self) -> List[Message]:
#         """Retrieve a list of messages from the agent's memory."""
#         return self.memory.messages

#     @messages.setter
#     def messages(self, value: List[Message]):
#         """Set the list of messages in the agent's memory."""
#         self.memory.messages = value
