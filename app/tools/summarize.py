import asyncio # 在这个工具中可能不需要，因为没有阻塞的I/O操作
from tools.base import BaseTool, ToolResult, ToolFailure # 假设这些基类已定义
from utils.logger import logger # 假设您有一个名为 logger 的日志记录器

class FinalResponse(BaseTool):
    name: str = "final_response" # 工具名称，遵循小写和空格的模式
    description: str = """
    一个特殊的工具，用于向用户提供最终的行动总结、结果或结论性答复。
    仅当您已完成处理用户查询的所有必要步骤并准备结束交互时，才应使用此工具。
    这通常是在调用 'terminate' 工具之前的最后一个工具。
    此处提供的内容将被视为代理给用户的最终输出。
    """
    strict: bool = True # 因为有必需的参数
    parameters: dict = {
        "type": "object",
        "properties": {
            "content_to_deliver": { # 参数名称
                "description": "需要呈现给用户的全面最终消息、行动总结、调查结果或直接答案。这应该是一个独立的、完整的回复。",
                "type": "string",
            }
        },
        "required": ["content_to_deliver"], # 声明 content_to_deliver 是必需的
    }

    async def execute(self, re: str):
        """
        执行最终响应/总结的呈现。

        参数:
        - content_to_deliver: 代理准备好的，要传达给用户的最终内容。
        """
        try:
            # 使用 logger 记录代理的最终陈述
            # 使用 🏁 (终点旗帜) 表情符号来表示这是一个最终步骤
            logger.info(f"🏁 代理的最终回应: {content_to_deliver}")

            # 此工具的主要目的是让代理正式地声明其最终输出。
            # 代理框架可能会直接使用此工具的输出，或者根据此工具被调用的事实，
            # 来标志主动处理的结束并将此内容作为最终消息呈现给用户。

            # ToolResult 的 output 可以确认代理已声明了什么。
            return ToolResult(output=f"代理已得出以下最终回应: {content_to_deliver}")
        except Exception as e:
            logger.error(f"⚠️ 在 FinalResponse 工具中发生错误: {e}")
            # 这个简单的工具本身不太可能引发异常，除非 logger.info 失败。
            # 但为了稳健性，还是加上了异常处理。
            raise ToolFailure(f"⚠️ 传递最终回应时发生错误: {e}")