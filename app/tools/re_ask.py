from tools.base import BaseTool, ToolResult, ToolFailure
from utils.logger import logger
from fastapi import WebSocket
import asyncio # <-- 导入 asyncio
# from pydantic import Field # 如果需要更复杂的默认值或验证，可能需要Field
from pydantic import Field

class ReAsk(BaseTool):
    name:str = "re_ask"
    description:str = """
    a special tool for re-asking to user...
    """
    strict:bool = True
    parameters:dict = {
        # ... parameters definition ...
         "type": "object",
        "properties": {
            "question": {
                "description": "The question to ask the user.",
                "type": "string",
            },
            "reason" :{
              "description": "The reason for asking the question.",
              "type": "string",
            }
        },

        "required": ["question"],
    }

    websocket: WebSocket = None
    response_queue: asyncio.Queue = Field(default_factory=lambda: asyncio.Queue(maxsize=1))

    # 定义 __init__ 方法
    # 接受 websocket 参数和 **kwargs
    def __init__(self, websocket: WebSocket, **kwargs):
        super().__init__(websocket=websocket, **kwargs)


    async def execute(self, question: str, reason: str = None):
        log_message = f"🧐agent Because:{reason}, re-asking:{question}" if reason is not None \
            else f"🧐agent to understand your purpose better, re-asking:{question}"
        logger.info(log_message)

        await self.websocket.send_text(log_message)
        await self.websocket.send_text('<<<END_OF_RESPONSE_OF_REASK>>>')

        logger.info("waiting for user's re-ask response from queue...")

        try:
            # 在这里等待用户回复从队列中获取
            user_response: str = await self.response_queue.get()
            logger.info(f"Received user response for re-ask: {user_response}")

            # 如果你在类顶层保留了 re_ask_str 字段，并且想在这里更新它，可以加上这行：
            # self.re_ask_str = user_response

            return ToolResult(output=f"for question:'{question}', user response:'{user_response}'")

        except Exception as e:
            logger.error(f"⚠️ Error during re-ask execution: {e}")
            # 发送错误信息给客户端
            try:
                await self.websocket.send_text(f"Error processing re-ask response: {e}")
            except Exception:
                pass # 连接可能已断开

            # 清空队列，防止下次错误地获取到旧消息（保险起见）
            while not self.response_queue.empty():
                 try:
                     self.response_queue.get_nowait()
                 except asyncio.QueueEmpty:
                     pass

            raise ToolFailure(f"⚠️ Error during re-ask execution: {e}")