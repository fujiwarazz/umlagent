
from tools.base import BaseTool,ToolResult
_PLANNING_TOOL_DESCRIPTION = """
        a special tool that can be used to terminate this interaction, use this tool when you think you have finished user's query 
        OR when you think you can not finish user's query in what you have and what you know
        """
        
class Terminate(BaseTool):
    name:str = 'terminate'
    description:str = _PLANNING_TOOL_DESCRIPTION
    strict: bool= True
    parameters:dict = {
        "type": "object",
        "properties": {
            "status": {
                "description": "The finish status of the interaction.",
                "enum": ["success", "failure"],
                "type": "string",
            },
        },
        "required": ["command"],
        "additionalProperties": False,
    }
    
    async def execute(self, status):
        return f"The interaction has been completed with status: {status}"
