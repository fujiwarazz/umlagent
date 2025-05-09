from agents.tool_call import ToolCallAgent
from agents.umlagent import UMLAgent
from tools import ToolCollection, Terminate,PlanningTool,BaiduSearch,GitHubRepoCloner,FileSaver,FileSeeker,ReAsk,CreateChatCompletion,CodeToUMLTool,FinalResponse

async def main():
    # Configure and run the agent
    agent = UMLAgent(available_tools=ToolCollection(PlanningTool(),FinalResponse(),BaiduSearch(),ReAsk(),CodeToUMLTool(),Terminate(),CreateChatCompletion(),GitHubRepoCloner(local_clone_base_dir="D:\\deep_learning\\codes\\workspace"),FileSeeker(),FileSaver() ))
    
    result = await agent.run(r"帮我找一个关于qwen2.5的项目，并且pull到本地，分析代码")
# print(result)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
   
