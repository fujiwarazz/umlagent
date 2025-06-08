from agents.tool_call import ToolCallAgent
from agents.umlagent import UMLAgent
from agents.sweagent import SWEAgent
from tools import ToolCollection, Terminate,PlanningTool,BaiduSearch,GitHubRepoCloner,FileSaver,FileSeeker,ReAsk,CreateChatCompletion,CodeToUMLTool,PythonExecute,FinalResponse,EnsureInitPyTool

   

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from utils.logger import logger
app = FastAPI()
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from utils.logger import logger
from config.app_config import CODE_PATH

app = FastAPI()


active_agents: dict[str, ToolCallAgent] = {}




@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_id = str(websocket.client.host) + ":" + str(websocket.client.port)
    logger.info(f"WebSocket connection accepted from {client_id}")
    try:
        from tools import RAG,CodeAnalyzer,FileOperatorTool,BlueprintTool
        
        
        sweagent = SWEAgent(available_tools=ToolCollection(
            RAG(),
            CodeAnalyzer(),FileOperatorTool(workspace_root=CODE_PATH),BlueprintTool(),PythonExecute()
            )) #  用于分析代码的专用agent

        agent = UMLAgent(
            available_tools=ToolCollection(
                                PlanningTool(),
                                FinalResponse(),
                                BaiduSearch(),
                                #ReAsk(websocket), deadlock bug 
                                CodeToUMLTool(websocket=websocket),
                                Terminate(),
                                CreateChatCompletion(),
                                GitHubRepoCloner(local_clone_base_dir=CODE_PATH),
                                FileSeeker(),
                                FileSaver(),
                                EnsureInitPyTool()
                                ),
            websocket=websocket,
            hands_offs=[sweagent]
            )
        
        active_agents[client_id] = agent        
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received message from {client_id}: {data}")
            await agent.run(query=data)

    except WebSocketDisconnect:
        logger.info(f"WebSocket connection disconnected from {client_id}")
        if client_id in active_agents:
            del active_agents[client_id]
    finally:
        if client_id in active_agents:
            del active_agents[client_id]
        await websocket.send_text("<<<END_OF_RESPONSE>>>")
        logger.info(f"Cleaned up resources for {client_id}")


