from agents.tool_call import ToolCallAgent
from agents.umlagent import UMLAgent
from tools.planning import PlanningTool
from tools import ToolCollection, Terminate

async def main():
    # Configure and run the agent
    agent = UMLAgent(available_tools=ToolCollection(PlanningTool(), Terminate()))
    result = await agent.run("Help me plan a trip to the moon")
    print(result)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
