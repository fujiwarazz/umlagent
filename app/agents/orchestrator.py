# # import json
# # from typing import Any, List, Literal,Dict
# # from agents.base import BaseAgent
# # from agents.react import ReActAgent

# # from pydantic import Field,BaseModel
# # from utils.logger import logger


# #     """
# #     获得所有的agent
# #     获得agent所有的工具
# #     通过ask tools获得要调用的工具
# #     将工具分配给agent
    

# #     Returns:
# #         _type_: _description_
# #     """
# # # class Orchestrator(ReActAgent):
# # #     name:str= "orchestrator"
# # #     description:str = "an agent that can orchestrate agents to solve tasks."
    
# # #     ORCHESTRATOR_SYSTEM_PROMPT: str = """
# # # You are an orchestrator agent. Your goal is to understand the user's request and delegate it to the most appropriate specialized agent.
# # # You have the following specialized agents available as tools:
# # # {available_agents_description}

# # # Prioritization Rules:
# # # 1. If the user's request is complex, involves multiple steps, requires a sequence of actions, or explicitly asks for a plan, you MUST prioritize using the 'call_uml_agent' tool to create a plan first.
# # # 2. For specific software engineering tasks like writing code, debugging, or running tests, especially if a plan already exists or the task is straightforward, you can use the 'call_swe_agent' tool.
# # # 3. If unsure, it's generally safer to use 'call_uml_agent' to ensure proper planning.

# # # Based on the user's request, decide which agent (tool) to call.
# # # The input to the chosen tool should be the user's original request or a relevant sub-task.
# # # You MUST choose one of the available agent tools.
# # # """
    
# # #     sub_agents: Dict[str, Any] = Field(default_factory=dict) # 子Agent实例: {"agent_name": agent_instance}
# # #     async def think(self) -> bool:
        
    
# # #     async def act(self) -> str:
# # #         pass


    
# # class OrchestratorAgent(ReActAgent): # 或者继承你项目中的某个Agent基类
# #     name: str = "OrchestratorAgent"
# #     description: str = "An agent that understands user requests and delegates them to specialized agents. It prioritizes planning for complex tasks."
    
# #     sub_agents: Dict[str, Any] = Field(default_factory=dict) # 子Agent实例: {"agent_name": agent_instance}
# #     # planning_agent_name: str = "uml_agent" # 明确指定planning agent的名称

# #     # 覆盖系统提示，以指导LLM进行Agent选择和规划优先
# #     # 注意：这里的"tools"会是 call_uml_agent, call_swe_agent 等
# #     ORCHESTRATOR_SYSTEM_PROMPT: str = """
# # You are an orchestrator agent. Your goal is to understand the user's request and delegate it to the most appropriate specialized agent.
# # You have the following specialized agents available as tools:
# # {available_agents_description}

# # Prioritization Rules:
# # 1. If the user's request is complex, involves multiple steps, requires a sequence of actions, or explicitly asks for a plan, you MUST prioritize using the 'call_uml_agent' tool to create a plan first.
# # 2. For specific software engineering tasks like writing code, debugging, or running tests, especially if a plan already exists or the task is straightforward, you can use the 'call_swe_agent' tool.
# # 3. If unsure, it's generally safer to use 'call_uml_agent' to ensure proper planning.

# # Based on the user's request, decide which agent (tool) to call.
# # The input to the chosen tool should be the user's original request or a relevant sub-task.
# # You MUST choose one of the available agent tools.
# # """
# #     # LLM 实例 (可以从父类继承或在此处初始化)
# #     # llm: LLMInterface = Field(default_factory=LLMInterface) # 假设的LLM接口

# #     def __init__(self, sub_agents_list: List[Any], **data: Any): # Pydantic v2 style
# #         super().__init__(**data) # `name`, `description`, `llm`等会由ToolCallAgent处理
        
# #         # 注册子Agent并构建可供Orchestrator的LLM调用的"工具"
# #         _tools_for_orchestrator = []
# #         for agent_instance in sub_agents_list:
# #             if not hasattr(agent_instance, 'name') or not hasattr(agent_instance, 'description') or not hasattr(agent_instance, 'run') or not hasattr(agent_instance, 'as_tool_for_orchestrator'):
# #                 logger.warning(f"Agent instance {type(agent_instance)} does not have required attributes/methods (name, description, run, as_tool_for_orchestrator). Skipping.")
# #                 continue
            
# #             self.sub_agents[agent_instance.name] = agent_instance
# #             agent_tool = agent_instance.as_tool_for_orchestrator()
# #             _tools_for_orchestrator.append(agent_tool)
# #             logger.info(f"Registered sub-agent: {agent_instance.name} as tool {agent_tool.name}")

# #         self.available_tools = ToolCollection(*_tools_for_orchestrator) # Orchestrator的工具是调用子Agent
# #         self.tool_choices = "required" # Orchestrator必须选择一个子Agent（工具）来执行

# #         # 更新系统提示以包含动态生成的Agent描述
# #         self.system_prompt = self.ORCHESTRATOR_SYSTEM_PROMPT.format(
# #             available_agents_description="\n".join([f"- {tool.name}: {tool.description}" for tool in _tools_for_orchestrator])
# #         )
# #         logger.debug(f"Orchestrator System Prompt:\n{self.system_prompt}")


# #     async def _select_agent_and_prepare_task(self, request: str) -> Optional[ToolCall]:
# #         """
# #         Uses LLM to select the appropriate sub-agent (as a tool) and prepares the task.
# #         This is part of the Orchestrator's "think" phase.
# #         """
# #         self.messages.append(Message.user_message(request))

# #         # LLM选择要调用的子Agent（作为工具）
# #         llm_response = await self.llm.ask_tools(
# #             messages=self.messages, # 包含当前请求的对话历史
# #             system_msgs=[Message.system_message(self.system_prompt)],
# #             tools=self.available_tools.to_params(), # 子Agent被表示为工具
# #             tool_choice=self.tool_choices # 强制LLM选择一个工具
# #         )

# #         if llm_response.tool_calls and llm_response.tool_calls[0]:
# #             # 假设LLM返回的第一个ToolCall是我们要执行的
# #             # 这个ToolCall的name应该是 "call_uml_agent" 或 "call_swe_agent"
# #             # arguments应该包含传递给该子Agent的请求
# #             selected_tool_call = llm_response.tool_calls[0]
# #             self.messages.append(Message.from_tool_calls(content=llm_response.content, tool_calls=[selected_tool_call]))
# #             return selected_tool_call
# #         else:
# #             logger.warning("Orchestrator LLM did not select any agent tool.")
# #             # 可以选择返回一个错误信息或尝试默认行为
# #             self.messages.append(Message.assistant_message("I was unable to determine which agent to use for your request."))
# #             return None

# #     async def _delegate_to_agent(self, tool_call: ToolCall) -> str:
# #         """
# #         Delegates the task to the selected sub-agent.
# #         This is part of the Orchestrator's "act" phase.
# #         """
# #         chosen_agent_tool_name = tool_call.function.name # e.g., "call_uml_agent"
        
# #         # 从 "call_agent_name" 提取 "agent_name"
# #         # agent_name_to_call = chosen_agent_tool_name.replace("call_", "") 
        
# #         # 更稳健的方式：查找哪个注册的agent的tool名与之匹配
# #         target_agent_name = None
# #         for name, agent_instance in self.sub_agents.items():
# #             if agent_instance.as_tool_for_orchestrator().name == chosen_agent_tool_name:
# #                 target_agent_name = name
# #                 break
        
# #         if not target_agent_name or target_agent_name not in self.sub_agents:
# #             error_msg = f"Error: LLM selected an unknown agent tool: {chosen_agent_tool_name}"
# #             logger.error(error_msg)
# #             self.messages.append(Message.tool_message(content=error_msg, tool_call_id=tool_call.id, name=chosen_agent_tool_name))
# #             return error_msg

# #         selected_agent = self.sub_agents[target_agent_name]
        
# #         try:
# #             # 解析传递给子Agent的参数，这里简化为假设它总是 'user_request'
# #             import json
# #             tool_args = json.loads(tool_call.function.arguments)
# #             task_for_sub_agent = tool_args.get("user_request", "") # 或者LLM直接把原始请求放这
# #             if not task_for_sub_agent: # 如果LLM没有明确指定user_request参数，则使用原始请求
# #                  # 需要找到原始的用户请求，这取决于messages的结构
# #                  # 假设最后一个用户消息是原始请求，但更稳妥的做法是让LLM在arguments中明确指定
# #                 original_user_request = ""
# #                 for msg in reversed(self.messages):
# #                     if msg.role == "user":
# #                         original_user_request = msg.content
# #                         break
# #                 task_for_sub_agent = original_user_request

# #             logger.info(f"Orchestrator delegating task to {selected_agent.name}: '{task_for_sub_agent}'")
            
# #             # 调用子Agent的 run 方法
# #             result = await selected_agent.run(request=task_for_sub_agent)
            
# #             self.messages.append(Message.tool_message(content=result, tool_call_id=tool_call.id, name=chosen_agent_tool_name))
# #             return result
# #         except Exception as e:
# #             error_msg = f"Error occurred while {selected_agent.name} was processing the request: {e}"
# #             logger.error(error_msg, exc_info=True)
# #             self.messages.append(Message.tool_message(content=error_msg, tool_call_id=tool_call.id, name=chosen_agent_tool_name))
# #             return error_msg



# #     如果你的 ToolCallAgent 有 think 和 act 方法，你可能需要这样组织：
# #     async def think(self) -> bool:
# #         # 从 self.messages 中获取最新的用户请求
# #         latest_user_message = next((m.content for m in reversed(self.messages) if m.role == "user"), None)
# #         if not latest_user_message:
# #             logger.warning("Orchestrator think: No user message found to process.")
# #             return False # No action to take
        
# #         selected_tool_call = await self._select_agent_and_prepare_task(latest_user_message)
# #         if selected_tool_call:
# #             self.tool_calls = [selected_tool_call] # Store for act()
# #             return True # Indicates a tool call is pending
# #         return False

# #     async def act(self) -> str:
# <<<<<<< HEAD
# #         if not self.tool_calls:
# #             return "No action to perform."
        
# #         # 仅处理最新/第一个tool_call
# #         current_tool_call = self.tool_calls.pop(0) 
# #         result = await self._delegate_to_agent(current_tool_call)
# #         return result
# =======
# #         pass


    
# class OrchestratorAgent(ReActAgent): 
#     name: str = "OrchestratorAgent"
#     description: str = "An agent that understands user requests and delegates them to specialized agents. It prioritizes planning for complex tasks."
    
#     sub_agents: Dict[str, Any] = Field(default_factory=dict) 

#     ORCHESTRATOR_SYSTEM_PROMPT: str = """
# You are an orchestrator agent. Your goal is to understand the user's request and delegate it to the most appropriate specialized agent.
# You have the following specialized agents available as tools:
# {available_agents_description}

# Prioritization Rules:
# 1. If the user's request is complex, involves multiple steps, requires a sequence of actions, or explicitly asks for a plan, you MUST prioritize using the 'call_uml_agent' tool to create a plan first.
# 2. For specific software engineering tasks like writing code, debugging, or running tests, especially if a plan already exists or the task is straightforward, you can use the 'call_swe_agent' tool.
# 3. If unsure, it's generally safer to use 'call_uml_agent' to ensure proper planning.

# Based on the user's request, decide which agent (tool) to call.
# The input to the chosen tool should be the user's original request or a relevant sub-task.
# You MUST choose one of the available agent tools.
# """

#     def __init__(self, sub_agents_list: List[Any], **data: Any):
#         super().__init__(**data) 
        
#         _tools_for_orchestrator = []
#         for agent_instance in sub_agents_list:
#             if not hasattr(agent_instance, 'name') or not hasattr(agent_instance, 'description') or not hasattr(agent_instance, 'run') or not hasattr(agent_instance, 'as_tool_for_orchestrator'):
#                 logger.warning(f"Agent instance {type(agent_instance)} does not have required attributes/methods (name, description, run, as_tool_for_orchestrator). Skipping.")
#                 continue
            
#             self.sub_agents[agent_instance.name] = agent_instance
#             agent_tool = agent_instance.as_tool_for_orchestrator()
#             _tools_for_orchestrator.append(agent_tool)
#             logger.info(f"Registered sub-agent: {agent_instance.name} as tool {agent_tool.name}")

#         self.available_tools = ToolCollection(*_tools_for_orchestrator) # Orchestrator的工具是调用子Agent
#         self.tool_choices = "required" # Orchestrator必须选择一个子Agent（工具）来执行

#         # 更新系统提示以包含动态生成的Agent描述
#         self.system_prompt = self.ORCHESTRATOR_SYSTEM_PROMPT.format(
#             available_agents_description="\n".join([f"- {tool.name}: {tool.description}" for tool in _tools_for_orchestrator])
#         )
#         logger.debug(f"Orchestrator System Prompt:\n{self.system_prompt}")


#     async def _select_agent_and_prepare_task(self, request: str) -> Optional[ToolCall]:
#         """
#         Uses LLM to select the appropriate sub-agent (as a tool) and prepares the task.
#         This is part of the Orchestrator's "think" phase.
#         """
#         self.messages.append(Message.user_message(request))

#         # LLM选择要调用的子Agent（作为工具）
#         llm_response = await self.llm.ask_tools(
#             messages=self.messages, # 包含当前请求的对话历史
#             system_msgs=[Message.system_message(self.system_prompt)],
#             tools=self.available_tools.to_params(), # 子Agent被表示为工具
#             tool_choice=self.tool_choices # 强制LLM选择一个工具
#         )

#         if llm_response.tool_calls and llm_response.tool_calls[0]:
#             selected_tool_call = llm_response.tool_calls[0]
#             self.messages.append(Message.from_tool_calls(content=llm_response.content, tool_calls=[selected_tool_call]))
#             return selected_tool_call
#         else:
#             logger.warning("Orchestrator LLM did not select any agent tool.")
#             # 可以选择返回一个错误信息或尝试默认行为
#             self.messages.append(Message.assistant_message("I was unable to determine which agent to use for your request."))
#             return None

#     async def _delegate_to_agent(self, tool_call: ToolCall) -> str:
#         """
#         Delegates the task to the selected sub-agent.
#         This is part of the Orchestrator's "act" phase.
#         """
#         chosen_agent_tool_name = tool_call.function.name # e.g., "call_uml_agent"
        
     
#         target_agent_name = None
#         for name, agent_instance in self.sub_agents.items():
#             if agent_instance.as_tool_for_orchestrator().name == chosen_agent_tool_name:
#                 target_agent_name = name
#                 break
        
#         if not target_agent_name or target_agent_name not in self.sub_agents:
#             error_msg = f"Error: LLM selected an unknown agent tool: {chosen_agent_tool_name}"
#             logger.error(error_msg)
#             self.messages.append(Message.tool_message(content=error_msg, tool_call_id=tool_call.id, name=chosen_agent_tool_name))
#             return error_msg

#         selected_agent = self.sub_agents[target_agent_name]
        
#         try:
#             import json
#             tool_args = json.loads(tool_call.function.arguments)
#             task_for_sub_agent = tool_args.get("user_request", "") 
#             if not task_for_sub_agent: 
             
#                 original_user_request = ""
#                 for msg in reversed(self.messages):
#                     if msg.role == "user":
#                         original_user_request = msg.content
#                         break
#                 task_for_sub_agent = original_user_request

#             logger.info(f"Orchestrator delegating task to {selected_agent.name}: '{task_for_sub_agent}'")
            
#             result = await selected_agent.run(request=task_for_sub_agent)
            
#             self.messages.append(Message.tool_message(content=result, tool_call_id=tool_call.id, name=chosen_agent_tool_name))
#             return result
#         except Exception as e:
#             error_msg = f"Error occurred while {selected_agent.name} was processing the request: {e}"
#             logger.error(error_msg, exc_info=True)
#             self.messages.append(Message.tool_message(content=error_msg, tool_call_id=tool_call.id, name=chosen_agent_tool_name))
#             return error_msg



#     async def think(self) -> bool:
#         latest_user_message = next((m.content for m in reversed(self.messages) if m.role == "user"), None)
#         if not latest_user_message:
#             logger.warning("Orchestrator think: No user message found to process.")
#             return False # No action to take
        
#         selected_tool_call = await self._select_agent_and_prepare_task(latest_user_message)
#         if selected_tool_call:
#             self.tool_calls = [selected_tool_call] # Store for act()
#             return True # Indicates a tool call is pending
#         return False

#     async def act(self) -> str:
#         if not self.tool_calls:
#             return "No action to perform."
        
#         # 仅处理最新/第一个tool_call
#         current_tool_call = self.tool_calls.pop(0) 
#         result = await self._delegate_to_agent(current_tool_call)
#         return result
# >>>>>>> 643b88faf2a7175e3731a0918885e8cdbd0512a6
