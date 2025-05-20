import json
from typing import Any, List, Literal

from pydantic import Field

from agents.tool_call import ToolCallAgent
from utils.logger import logger
from prompts.umlagent import NEXT_STEP_PROMPT, PLANNING_SYSTEM_PROMPT
from utils.entity import AgentState, Message, ToolCall
# from tools import CreateChatCompletion, Terminate, ToolCollection, CodeExcute, Bash, FileSaver,FileSeeker,Github,UML,REASK
from tools import Terminate, ToolCollection


class SWEAgent(ToolCallAgent):
    system_prompt:str = SWE_SYSTEM_PROMPT
    next_step_prompt:str = SWE_NEXT_STEP_PROMPT 
    available_tools: ToolCollection = ToolCollection(
        Terminate())
    
    special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])
    tool_choice:Literal['none','auto','required'] =  "required"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.available_tools.add_tools(
            CreateChatCompletion(),
            
        )
        if kwargs.get('available_tools') is not None:
            self.available_tools.add_tools(*kwargs.get('available_tools').tools)