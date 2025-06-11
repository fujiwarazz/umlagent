import asyncio # 在这个工具中可能不需要，因为没有阻塞的I/O操作
from tools.base import BaseTool, ToolResult, ToolFailure # 假设这些基类已定义
from utils.logger import logger # 假设您有一个名为 logger 的日志记录器

class FinalResponse(BaseTool):
    name: str = "final_response" 
    description: str = """
        A special tool for delivering the final summary of actions, results, or a conclusive response to the user.
        You should only use this tool when you have completed all necessary steps to address the user's query and are ready to end the interaction.
        Typically, this is the last tool to call before invoking the 'terminate' tool.
        The content provided here will be treated as the agent's final output to the user.
    """
    strict: bool = True # 因为有必需的参数
    parameters: dict = {
        "type": "object",
        "properties": {
            "content_to_deliver": { 
                "description": "A comprehensive final message, summary of actions, findings, or a direct answer to be presented to the user. This tool should be used when a summary is required for the user. The response should be a standalone, complete reply of type string.",
                "type": "string",
            }
        },
        "required": ["content_to_deliver"],
    }

    async def execute(self, content_to_deliver: str):
        """
        执行最终响应/总结的呈现。

        参数:
        - content_to_deliver: 代理准备好的，要传达给用户的最终内容。
        """
        try:
           
            logger.info(f"🏁 代理的最终回应: {content_to_deliver}")
            return ToolResult(output=f"代理已得出以下最终回应: {str(content_to_deliver)}")
        except Exception as e:
            logger.error(f"⚠️ 在 FinalResponse 工具中发生错误: {e}")
            raise ToolFailure(f"⚠️ 传递最终回应时发生错误: {e}")