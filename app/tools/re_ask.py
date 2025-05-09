from tools.base import BaseTool, ToolResult, ToolFailure
from utils.logger import logger

class ReAsk(BaseTool):
    name:str = "re ask"
    description:str = """
    a special tool for re-asking to user,use this tool when you very not sure something need to be done or something doesn't need to be done
    or when you need more detail imformation from user.  if you can use available tools,you should use them instead of this tool to re-ask.
    """
    strict:bool = True
    parameters:dict = {
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
    
    async def execute(self, question:str,reason:str=None):
        logger.info(f"🧐agent 因为:{reason},因此向你重新提问:{question}") if reason is not None \
        else logger.info(f"🧐agent为了更了解你的目的, 因此向你重新提问:{question}")
        
        user_response: str
        try:
            import sys
            import asyncio
            if sys.version_info >= (3, 9): # 检查Python版本是否支持 asyncio.to_thread
                user_response = await asyncio.to_thread(input, f"{question} ")
            else:
                user_response = input(f"{question} ")
            
            return ToolResult(output=f"for question:{question},user response:{user_response}")
        except Exception as e:
            logger.error(f"⚠️ 错误:{e}")
            raise ToolFailure(f"⚠️ 错误:{e}")
            