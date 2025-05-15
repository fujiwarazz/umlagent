from agents.tool_call import ToolCallAgent
from agents.umlagent import UMLAgent
from tools import ToolCollection, Terminate,PlanningTool,BaiduSearch,GitHubRepoCloner,FileSaver,FileSeeker,ReAsk,CreateChatCompletion,CodeToUMLTool,FinalResponse

# async def main():
#     # Configure and run the agent
#     agent = UMLAgent(available_tools=ToolCollection(PlanningTool(),FinalResponse(),BaiduSearch(),ReAsk(),CodeToUMLTool(),Terminate(),CreateChatCompletion(),GitHubRepoCloner(local_clone_base_dir="D:\\deep_learning\\codes\\workspace"),FileSeeker(),FileSaver() ))
#     """
#         1、 添加长期记忆模块rag，管理短期记忆模块
#         2、 添加multi agent模块，添加一个agent来管理所有agent
#         3、 添加mcp agent
#     """
#     result = await agent.run(r"帮我找一个关于llama3的项目，并且pull到本地，分析代码uml")
# # print(result)


# if __name__ == "__main__":
#     import asyncio

#     asyncio.run(main())
   

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from utils.logger import logger
app = FastAPI()


active_agents: dict[str, ToolCallAgent] = {}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_id = str(websocket.client.host) + ":" + str(websocket.client.port)
    logger.info(f"WebSocket connection accepted from {client_id}")
    try:
      
        agent = UMLAgent(available_tools=ToolCollection(
            PlanningTool(),
            FinalResponse(),
            BaiduSearch(),
            #ReAsk(websocket), deadlock bug 
            CodeToUMLTool(websocket=websocket),
            Terminate(),
            CreateChatCompletion(),
            GitHubRepoCloner(local_clone_base_dir="D:\\deep_learning\\codes\\workspace"),
            FileSeeker(),
            FileSaver()
            )
            )
        
        active_agents[client_id] = agent        
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received message from {client_id}: {data}")
            await agent.run(query=data, websocket=websocket)

    except WebSocketDisconnect:
        logger.info(f"WebSocket connection disconnected from {client_id}")
        # Clean up the agent instance for this client
        if client_id in active_agents:
            del active_agents[client_id]
    except Exception as e:
        logger.error(f"Error in WebSocket handler for {client_id}: {e}")
        try:
            await websocket.send_text(f"An error occurred: {e}")
        except RuntimeError:
            # Handle cases where the websocket is already closed
            pass
    finally:
        # Ensure agent is removed even if other exceptions occur
        if client_id in active_agents:
            del active_agents[client_id]
        logger.info(f"Cleaned up resources for {client_id}")

@app.websocket("/simple")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_id = str(websocket.client.host) + ":" + str(websocket.client.port)
    logger.info(f"WebSocket connection accepted from {client_id}")
    while True:
            data = await websocket.receive_text()
            logger.info(f"Received message from {client_id}: {data}")
        
    

# To run this application:
# 1. Save the modified agent code (e.g., agents/tool_call.py).
# 2. Save the FastAPI code as main.py.
# 3. Make sure your project structure allows importing your agent components.
# 4. Run from your terminal in the project root:
#    uvicorn main:app --reload
# 5. Open your browser to http://127.0.0.1:8000/