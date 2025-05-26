from agents.tool_call import ToolCallAgent
from agents.umlagent import UMLAgent
from agents.sweagent import SWEAgent
from tools import ToolCollection, Terminate,PlanningTool,BaiduSearch,GitHubRepoCloner,FileSaver,FileSeeker,ReAsk,CreateChatCompletion,CodeToUMLTool,FinalResponse
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from utils.logger import logger
from config.app_config import CODE_PATH
app = FastAPI()


active_agents: dict[str, ToolCallAgent] = {}

### origin

# @app.websocket("/ws")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     client_id = str(websocket.client.host) + ":" + str(websocket.client.port)
#     logger.info(f"WebSocket connection accepted from {client_id}")
#     try:
#         from tools import RAG,CodeAnalyzer,BlueprintTool,FileOperatorTool
#         sweagent = SWEAgent(
#             available_tools=ToolCollection(
#                 FinalResponse(),
#                 BaiduSearch(),
#                 Terminate(),
#                 CreateChatCompletion(),
#                 FileOperatorTool()
#                 )) #  用于分析代码的专用agent

#         agent = UMLAgent(available_tools=ToolCollection(
#             PlanningTool(),
#             FinalResponse(),
#             BaiduSearch(),
#            # ReAsk(websocket),# deadlock bug need to fix
#             CodeToUMLTool(websocket=websocket),
#             Terminate(),
#             CreateChatCompletion(),
#             GitHubRepoCloner(local_clone_base_dir=CODE_PATH),
#             FileSeeker(),
#             FileSaver()
#             ),
#                          #sweagent= sweagent
#             )
#         active_agents[client_id] = agent        
#         while True:
#             data = await websocket.receive_text()
#             if data.startswith("<<<REASK_RESPONSE>>>"):
#                 agent.available_tools.get_tool("re_ask").response_queue.put(data[len("<<<REASK_RESPONSE>>>"):])
            
#             logger.info(f"Received message from {client_id}: {data}")
#             await agent.run(query=data, websocket=websocket)

#     except WebSocketDisconnect:
#         logger.info(f"WebSocket connection disconnected from {client_id}")
#         # Clean up the agent instance for this client
#         if client_id in active_agents:
#             del active_agents[client_id]
#     except Exception as e:
#         logger.error(f"Error in WebSocket handler for {client_id}: {e}")
#         try:
#             await websocket.send_text(f"An error occurred: {e}")
#         except RuntimeError:
#             # Handle cases where the websocket is already closed
#             pass
#     finally:
#         # Ensure agent is removed even if other exceptions occur
#         if client_id in active_agents:
#             del active_agents[client_id]
#         logger.info(f"Cleaned up resources for {client_id}")

## need tests

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_id = str(websocket.client.host) + ":" + str(websocket.client.port)
    logger.info(f"WebSocket connection accepted from {client_id}")

    # 初始化 agent 和 reask_tool
    # 注意：ReAsk 初始化时需要 websocket 实例
    reask_tool_instance = ReAsk(websocket=websocket) # 实例化 ReAsk
    
    agent = UMLAgent(available_tools=ToolCollection(
        PlanningTool(),
        FinalResponse(),
        BaiduSearch(),
        reask_tool_instance, # 使用上面实例化的 reask_tool
        CodeToUMLTool(websocket=websocket),
        Terminate(),
        CreateChatCompletion(),
        GitHubRepoCloner(local_clone_base_dir="D:\\deep_learning\\codes\\workspace"),
        FileSeeker(),
        FileSaver()
        ),
        # sweagent=sweagent
    )
    active_agents[client_id] = agent

    # 创建一个队列，用于将从客户端收到的新查询传递给 agent 处理循环
    agent_query_queue = asyncio.Queue()

    async def agent_processing_loop():
        """
        这个异步函数在一个独立的任务中运行，
        负责从 agent_query_queue 中获取查询并执行 agent.run()。
        """
        while True:
            try:
                query = await agent_query_queue.get()
                if query is None:  # 收到 None 作为信号，表示结束循环
                    logger.info(f"Agent processing loop for {client_id} stopping.")
                    break
                
                logger.info(f"Agent processing query from {client_id}: {query}")
                # agent.run 可能会调用 ReAsk，ReAsk 会等待 reask_tool_instance.response_queue
                await agent.run(query=query, websocket=websocket)
                logger.info(f"Agent finished processing query from {client_id}: {query}")

            except Exception as e:
                logger.error(f"Error in agent_processing_loop for {client_id}: {e}")
                try:
                    await websocket.send_text(f"An error occurred during agent processing: {e}")
                except Exception:
                    pass # 连接可能已断开
            finally:
                agent_query_queue.task_done() # 通知队列任务已完成

    # 创建并启动 agent_processing_loop 任务
    agent_task = asyncio.create_task(agent_processing_loop())
    logger.info(f"Agent processing task created for {client_id}")

    try:
        while True:
            # 这个循环现在只负责接收消息并分发
            data = await websocket.receive_text()
            logger.info(f"Received message from {client_id}: {data}")

            if data.startswith("<<<REASK_RESPONSE>>>"):
                response_content = data[len("<<<REASK_RESPONSE>>>"):]
                logger.info(f"Received REASK_RESPONSE from {client_id}: {response_content}")
                try:
                    # 重要: 使用 await 来调用异步队列的 put 方法
                    await reask_tool_instance.response_queue.put(response_content)
                    logger.info(f"Put REASK_RESPONSE into queue for {client_id}")
                except Exception as e:
                    logger.error(f"Error putting to reask_tool.response_queue for {client_id}: {e}")
            elif data.startswith("<<<END_OF_SESSION>>>"): # 举例：一个客户端主动结束会话的信号
                logger.info(f"Received end of session signal from {client_id}")
                break # 退出接收循环
            else:
                # 这是用户的新查询，放入 agent_query_queue，由 agent_task 处理
                logger.info(f"Putting new query into agent_query_queue for {client_id}: {data}")
                await agent_query_queue.put(data)

    except WebSocketDisconnect:
        logger.info(f"WebSocket connection disconnected from {client_id}")
    except Exception as e:
        logger.error(f"Error in WebSocket handler for {client_id}: {e}")
        try:
            await websocket.send_text(f"An error occurred: {e}")
        except RuntimeError:
            pass
    finally:
        logger.info(f"Cleaning up resources for {client_id}...")
        # 1. 通知 agent_processing_loop 结束
        if agent_query_queue is not None: # 检查队列是否已初始化
             await agent_query_queue.put(None) # 发送 None 作为结束信号
        
        # 2. 等待 agent_task 完成
        if agent_task is not None: # 检查任务是否已创建
            try:
                await asyncio.wait_for(agent_task, timeout=5.0) # 等待任务结束，设置超时
                logger.info(f"Agent processing task for {client_id} finished.")
            except asyncio.TimeoutError:
                logger.warning(f"Timeout waiting for agent_task of {client_id} to finish. Cancelling.")
                agent_task.cancel()
            except Exception as e_task:
                logger.error(f"Exception during agent_task cleanup for {client_id}: {e_task}")


        # 3. 清理 active_agents
        if client_id in active_agents:
            del active_agents[client_id]
            logger.info(f"Removed agent for {client_id} from active_agents.")
        
        # 4. 确保 WebSocket 安全关闭 (FastAPI 通常会自动处理)
        # await websocket.close() # 通常不需要手动调用，除非特殊情况

        logger.info(f"Cleaned up resources for {client_id}")
