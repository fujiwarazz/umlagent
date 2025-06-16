
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

@mtool(
    name = "get_weather_tool",
    description = "A tool to get the current weather information for a specified location.",
    strict = True
)
async def weather(location: Annotated[str,IsRequired]) -> str:
    """
    Args:
        location (str): The name of the location to get the weather for.
    """

    return ToolResult(
        output=f"The current weather in {location} is sunny with a temperature of 25°C."
    )
@mtool(
    name = 'python_execute',
    description = "A tool to execute Python code.",
    strict = True,
)
async def python_execute(code: Annotated[str, IsRequired]) -> str:
    """
    Args:
        code (Annotated[str, IsRequired]): The Python code to execute.
    """
    async def run_code_with_timeout(code, timeout=5):
        loop = asyncio.get_running_loop()
        def exec_code():
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()
            try:
                exec(code, {})
                output = sys.stdout.getvalue()
                error = sys.stderr.getvalue()
                return output + error
            except Exception as e:
                return str(e)
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

        return await asyncio.wait_for(loop.run_in_executor(None, exec_code), timeout=timeout)

    try:
        result = await run_code_with_timeout(code, timeout=5)
    except asyncio.TimeoutError:
        result = "Execution timed out."
    return ToolResult(output=result)

async def main():
    tools:ToolCollection = ToolCollection(Terminate(),python_execute,weather,CreateChatCompletion(),FinalResponse())
    code = str("print(1+1)")
    agent = ToolCallAgent(available_tools=tools,description="A helpful assistant.")
    res = await agent.run(f"请执行这段代码：{code}")
    print(res)

if __name__ == "__main__":
    asyncio.run(main())