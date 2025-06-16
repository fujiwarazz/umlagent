
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))  

from agents.tool_call import ToolCallAgent
from agents.umlagent import UMLAgent
from agents.sweagent import SWEAgent
from agents.tool_call import ToolCallAgent

from tools import ToolCollection, Terminate,PlanningTool,BaiduSearch,GitHubRepoCloner,FileSaver,FileSeeker,ReAsk,CreateChatCompletion,CodeToUMLTool,PythonExecute,FinalResponse,EnsureInitPyTool,RAG,CodeAnalyzer,FileOperatorTool,BlueprintTool

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from utils.logger import logger
app = FastAPI()
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from utils.logger import logger
from config.app_config import CODE_PATH
from typing import Annotated

app = FastAPI()

active_agents: dict[str, ToolCallAgent] = {}

from tools.factory.mtool import mtool,IsRequired
from tools.base import ToolResult
import sys
import io
import asyncio

async def main():
   
    english = ToolCallAgent(available_tools=ToolCollection(Terminate(),BaiduSearch(),CreateChatCompletion(),FinalResponse()),
                            system_prompt="A helpful english translator. Translate the input to English.",
                            name="english agent")
    franch = ToolCallAgent(available_tools=ToolCollection(Terminate(),BaiduSearch(),CreateChatCompletion(),FinalResponse()),
                            system_prompt="A helpful french translator.Translate the input to French.",
                            name="french agent")
    
    agent = ToolCallAgent(available_tools=ToolCollection(Terminate(),BaiduSearch(),CreateChatCompletion(),FinalResponse(),),
                            description="A helpful translator.",
                            hands_offs=[english,franch])
    
    res = await agent.run("将：你现在在杭州吗？这句话翻译为法语和英语")
    print(res)

if __name__ == "__main__":
    asyncio.run(main())
  