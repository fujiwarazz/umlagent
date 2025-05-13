from agents.tool_call import ToolCallAgent
from agents.umlagent import UMLAgent
from tools import ToolCollection, Terminate,PlanningTool,BaiduSearch,GitHubRepoCloner,FileSaver,FileSeeker,ReAsk,CreateChatCompletion,CodeToUMLTool,FinalResponse

async def main():
    # Configure and run the agent
    agent = UMLAgent(available_tools=ToolCollection(PlanningTool(),FinalResponse(),BaiduSearch(),ReAsk(),CodeToUMLTool(),Terminate(),CreateChatCompletion(),GitHubRepoCloner(local_clone_base_dir="D:\\deep_learning\\codes\\workspace"),FileSeeker(),FileSaver() ))
    """
        1、 添加长期记忆模块rag，管理短期记忆模块
        2、 添加multi agent模块，添加一个agent来管理所有agent
        3、 添加mcp agent
    """
    result = await agent.run(r"帮我找一个关于llama3的项目，并且pull到本地，分析代码uml")
# print(result)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
   
