from typing import Dict, List, Literal, Optional, Union

from openai import (
    APIError,
    AsyncOpenAI,
    AuthenticationError,
    OpenAIError,
    RateLimitError,
)

from tenacity import retry, stop_after_attempt, wait_random_exponential
import json
from config.llm_config import LLMSettings
from utils.logger import logger  
from utils.entity import Message
from config.llm_config import llm_settings
from agents.base import BaseAgent
from utils.entity import Handoff
class LLM:
    
    # 单例模式创建LLM clinet，为了能够互不影响同时创建多个client
    _instances: Dict[str, "LLM"] = {}

    def __new__(
        cls, config_name: str = "default", llm_config: Optional[LLMSettings] = None
    ):
        if config_name not in cls._instances:
            instance = super().__new__(cls)
            instance.__init__(config_name, llm_settings)
            cls._instances[config_name] = instance
        return cls._instances[config_name]
    
    def __init__(
        self, config_name: str = "default", llm_config: Optional[LLMSettings] = None
    ):
        if not hasattr(self, "client"):  # Only initialize if not already initialized
            self.model = llm_config.model
            self.max_tokens = llm_config.max_tokens
            self.temperature = llm_config.temperature
            self.api_type = llm_config.api_type
            self.api_key = llm_config.api_key
            self.api_version = llm_config.api_version
            self.base_url = llm_config.base_url
            
            self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
                
                
    @staticmethod
    def format_messages(messages: List[Union[dict, Message]]) -> List[dict]:
        """
        将本地的message格式格式化为OPEN AI CLIENT的格式
        Args:
            messages: List of messages that can be either dict or Message objects

        Returns:
            List[dict]: List of formatted messages in OpenAI format

        Raises:
            ValueError: If messages are invalid or missing required fields
            TypeError: If unsupported message types are provided

        Examples:
            >>> msgs = [
            ...     Message.system_message("You are a helpful assistant"),
            ...     {"role": "user", "content": "Hello"}, # formatted msg
            ...     Message.user_message("How are you?")
            ... ]
            >>> formatted = LLM.format_messages(msgs)
        """
        formatted_messages = []

        for message in messages:
            if isinstance(message, dict):
                # If message is already a dict, ensure it has required fields
                if "role" not in message:
                    raise ValueError("Message dict must contain 'role' field")
                formatted_messages.append(message)
            elif isinstance(message, Message):
                # If message is a Message object, convert it to dict
                formatted_messages.append(message.to_dict())
            else:
                raise TypeError(f"Unsupported message type: {type(message)}")

        # Validate all messages have required fields
        for msg in formatted_messages:
            if msg["role"] not in ["system", "user", "assistant", "tool"]:
                raise ValueError(f"Invalid role: {msg['role']}")
            if "content" not in msg and "tool_calls" not in msg:
                raise ValueError(
                    "Message must contain either 'content' or 'tool_calls'"
                )

        return formatted_messages
    
    async def summerize_memories(self,messages: List[Message]):
        SUMMARIZE_PROMPT = """
        You are an expert at summarizing conversations.
        You are given a list of messages from a conversation.
        Your task is to summarize the conversation in a single message.
        """
        summary = await self.ask(
            history=messages,
            system_msgs=[SUMMARIZE_PROMPT],
            stream=False
        )
        return summary
        
    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(6),
    )
    async def ask(
        self,
        history: List[Union[dict, Message]],
        system_msgs: Optional[List[Union[dict, Message]]] = None,
        stream: bool = True,
        temperature: Optional[float] = None,
    ) -> str:
        if system_msgs  is not None:
            history = self.format_messages(system_msgs) + self.format_messages(history)
        else:
            history = self.format_messages(history)
            
        try:
            if not stream:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=history,
                    max_tokens=self.max_tokens,
                    temperature=temperature or self.temperature,
                    stream=False,
                )
                if not response.choices or not response.choices[0].message:
                    raise ValueError("LLM 没有返回任何信息")
                return response.choices[0].message.content
            else:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=history,
                    max_tokens=self.max_tokens,
                    temperature=temperature or self.temperature,
                    stream=True,
                )
                all_chunks = []
                async for chunk in response:
                    chunk_message = chunk.choices[0].delta.content or ""
                    all_chunks.append(chunk_message)
                    print(chunk_message, end="", flush=True)
                    
                print('\n\n')
                
                full_response = "".join(all_chunks).strip()
                if not full_response:
                    raise ValueError("LLM没返回任何信息")
                return full_response
            
        except ValueError as ve:
            logger.error(f"Validation error in ask_tool: {ve}")
            raise
        
        except OpenAIError as oe:
            if isinstance(oe, AuthenticationError):
                logger.error("Authentication failed. Check API key.")
            elif isinstance(oe, RateLimitError):
                logger.error("Rate limit exceeded. Consider increasing retry attempts.")
            elif isinstance(oe, APIError):
                logger.error(f"API error: {oe}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in ask_tool: {e}")
            raise 
        
    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(6),
    )
    async def ask_handoff(self, messages, system_msgs=None, handoffs_agents: Optional[List[BaseAgent]] = None, 
                     tools: Optional[List[dict]] = None, timeout: int = 60, temperature=0.6, **kwargs) -> Union[Handoff, str]:
        try:
            # 创建handoff工具定义
            handoff_tool = {
                "type": "function",
                "function": {
                    "name": "handoff_to_agent",
                    "description": "Hand off the conversation to another specialized agent",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "The name of the agent to hand off to"
                            },
                            "input": {
                                "type": "string", 
                                "description": "The input/query to pass to the agent"
                            }
                        },
                        "required": ["name", "input"]
                    }
                }
            }
            all_tools = tools or []
            if handoffs_agents:
                all_tools.append(handoff_tool)
            
            if system_msgs:
                system_msgs = self.format_messages(system_msgs)
                messages = system_msgs + self.format_messages(messages)
            else:
                agent_infos = [
                    {
                        "agent_name": agent.name,
                        "agent_description": agent.description,
                    } 
                    for agent in handoffs_agents] if handoffs_agents else []
                
                system_msgs = {
                    "role": "system",
                    "content": f"""You are a helpful assistant. Available agents: {agent_infos} 
                    Use the handoff_to_agent tool when you need to delegate to a specialized agent."""
                }
                messages = [system_msgs] + self.format_messages(messages)
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=self.max_tokens,
                tools=all_tools,
                tool_choice="auto",  
                timeout=timeout,
                **kwargs,
            )
            
            if not response.choices or not response.choices[0].message:
                raise ValueError("Invalid or empty response from LLM")
            
            message = response.choices[0].message
            
            # 检查是否有工具调用
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    if tool_call.function.name == "handoff_to_agent":
                        try:
                            args = json.loads(tool_call.function.arguments)
                            return Handoff(name=args["name"], input=args["input"])
                        except (json.JSONDecodeError, KeyError) as e:
                            logger.error(f"Failed to parse handoff arguments: {e}")
            
            # 如果没有工具调用，返回文本内容
            return message.content or "No response content"
            
        except Exception as e:
            logger.error(f"Error in ask_handoff: {e}")
            raise
        
    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(6),
    )
    async def ask_tools(
         self,
        messages: List[Union[dict, Message]],
        system_msgs: Optional[List[Union[dict, Message]]] = None,
        timeout: int = 60,
        tools: Optional[List[dict]] = None,
        handoffs_agents: Optional[List[BaseAgent]] = None,
        tool_choice: Literal["none", "auto", "required"] = "auto",
        temperature: Optional[float] = None,
        **kwargs,
    ):
        """
        Ask LLM using functions/tools and return the response.

        Args:
            messages: List of conversation messages
            system_msgs: Optional system messages to prepend
            timeout: Request timeout in seconds
            tools: List of tools to use
            tool_choice: Tool choice strategy
            temperature: Sampling temperature for the response
            **kwargs: Additional completion arguments

        Returns:
            ChatCompletionMessage: The model's response

        Raises:
            ValueError: If tools, tool_choice, or messages are invalid
            OpenAIError: If API call fails after retries
            Exception: For unexpected errors
        """
        try:
            handoff_tool = {
                "type": "function",
                "function": {
                    "name": "handoff_to_agent",
                    "description": "Hand off the conversation to another specialized agent",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "The name of the agent to hand off to"
                            },
                            "input": {
                                "type": "string", 
                                "description": "The input/query to pass to the agent"
                            }
                        },
                        "required": ["name", "input"]
                    }
                }
            }
            all_tools = tools or []
            if handoffs_agents:
                all_tools.append(handoff_tool)
                
            # Validate tool_choice
            if tool_choice not in ["none", "auto", "required"]:
                raise ValueError(f"Invalid tool_choice: {tool_choice}")
            agent_infos = [
                                {
                                    "agent_name": agent.name,
                                    "agent_description": agent.description,
                                } 
                                for agent in handoffs_agents] if handoffs_agents else []
                            
            system_msg = {
                "role": "system",
                "content": f"""You are a helpful assistant. Available agents: {agent_infos} 
                Use the `handoff_to_agent` tool when you need to delegate to a specialized agent."""
            } if handoffs_agents else None
            
            # Format messages
            if system_msgs:
                system_msgs = self.format_messages(system_msgs)
                if system_msg:
                    system_msgs = [system_msg] + system_msgs
                messages = system_msgs + self.format_messages(messages)
            else:
                if system_msg:
                    system_msgs = [system_msg]
                messages = system_msgs + self.format_messages(messages)

            # Validate tools if provided
            if tools:
                for tool in tools:
                    if not isinstance(tool, dict) or "type" not in tool:
                        raise ValueError("Each tool must be a dict with 'type' field")

            # Set up the completion request
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=self.max_tokens,
                tools=tools,
                tool_choice=tool_choice,
                timeout=timeout,
                **kwargs,
            )

            # Check if response is valid
            if not response.choices or not response.choices[0].message:
            #    print(response)
                raise ValueError("Invalid or empty response from LLM")

            return response.choices[0].message

        except ValueError as ve:
            logger.error(f"Validation error in ask_tool: {ve}")
            raise
        except OpenAIError as oe:
            if isinstance(oe, AuthenticationError):
                logger.error("Authentication failed. Check API key.")
            elif isinstance(oe, RateLimitError):
                logger.error("Rate limit exceeded. Consider increasing retry attempts.")
            elif isinstance(oe, APIError):
                logger.error(f"API error: {oe}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in ask_tool: {e}")
            raise
