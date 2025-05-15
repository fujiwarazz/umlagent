import json
from typing import Any, List, Literal

from pydantic import Field

from agents.react import ReActAgent
from utils.logger import logger
from prompts.umlagent import NEXT_STEP_PROMPT, PLANNING_SYSTEM_PROMPT
from utils.entity import AgentState, Message, ToolCall
# from tools import CreateChatCompletion, Terminate, ToolCollection, CodeExcute, Bash, FileSaver,FileSeeker,Github,UML,REASK
from tools import Terminate, ToolCollection
class ToolCallAgent(ReActAgent):
    """
    Args:
        ReActAgent (_type_): _description_
    """
    
    name: str = "toolcall"
    description: str = "an agent that can execute tool calls."

    system_prompt: str = PLANNING_SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT

    available_tools: ToolCollection = ToolCollection(
         Terminate() )
    
    tool_choice:Literal['none','auto','required'] =  "required"
    
    special_tool_names: List[str] = Field(default_factory=lambda: [Terminate().name])

    tool_calls: List[ToolCall] = Field(default_factory=list)

    max_steps: int = 30
    
    async def think(self) -> bool:
        """让llm基于现在的情况进行决定是否采取下一步措施"""
        if self.next_step_prompt:
            user_msg = Message.user_message(self.next_step_prompt)
            self.messages += [user_msg]
        
        response = await self.llm.ask_tools(
            messages=self.messages, # history
            system_msgs=[Message.system_message(self.system_prompt)] # system msg
            if self.system_prompt
            else None,
            tools=self.available_tools.to_params(),
            tool_choice=self.tool_choice,
        )
        if response.tool_calls is None:
            return False
        
        self.tool_calls = response.tool_calls

                
        # todo 返回给前端
        logger.info(f"✨ {self.name} 的想法为: {response.content}")
        await self.websocket.send_text(f"✨ {self.name} 的想法为: {response.content}")
        logger.info(
            f"🛠️ {self.name} 选择了 {len(response.tool_calls) if response.tool_calls else 0} 个工具"
        )
        await self.websocket.send_text(f"🛠️ {self.name} 选择了 {len(response.tool_calls) if response.tool_calls else 0} 个工具")
        if self.tool_calls:
            logger.info(
                f"🧰 选择的工具信息: {[call.function.name for call in  self.tool_calls]}"
            )
            function_name_map = {
                "code_to_uml_generator_multilang" : "UML绘图工具",
                "github_repo_cloner_ssh" : "GITHUB克隆工具",
                "create_chat_completion" : "回答格式化工具",
                "planning" : "任务规划工具",
                "python_execute" : "python执行工具",
                "re_ask" : "重问工具",
                "final_response" : "总结工具",
                "terminate" : "结束回答",
                "baidu_search" : "百度搜索"
            }
            await self.websocket.send_text( f"🧰 选择的工具信息: {[function_name_map[call.function.name] for call in  self.tool_calls]}")
            logger.info(
                f"🧰 工具的参数是: {[call.function.arguments for call in  self.tool_calls]}"
            )
        
        try:
            if self.tool_choice == "none":
                if response.content:
                    self.memory.add_message(Message.assistant_message(response.content))
                    return True
                return False
            
            else:
                assistant_msg = (
                    Message.from_tool_calls(
                        content="Using tools response: " + response.content, tool_calls=self.tool_calls
                    )
                    if self.tool_calls is not None
                    else Message.assistant_message(response.content)
                )
                self.memory.add_message(assistant_msg)
                if self.tool_choice == 'auto' and not response.tool_calls:
                    return bool(response.content)
                
                if self.tool_choice == 'required' and not response.tool_calls:
                    return True
                
                return True

        except Exception as e:
            logger.error(f"🚨 出错啦! The {self.name} 在思考时出现了错误，错误信息如下: {e}")
            #await self.websocket.send(f"🚨 出错啦! The {self.name} 在思考时出现了错误，错误信息如下: {e}")
            self.memory.add_message(
                Message.assistant_message(
                    f"Error encountered while processing: {str(e)}"
                )
            )
            return False
        
    
    async def act(self) -> str:
        """执行think阶段选择的工具"""
        if not self.tool_calls:
            if self.tool_choice == "required":
                raise ValueError(f'🚨 出错啦! {self.name} 没有工具能用!')

            # 重新返回最后一条assistant message
            last_message = self.messages[-1] or "No content or commands to execute"
            new_message = '这一步执行没有选择工具，重新执行上一步，上一步信息为：' + last_message 
            return new_message 

        tool_excute_results = []
        for tool_call in self.tool_calls:
            result = await self.execute_tool(tool_call)
            logger.info(
                f"🎯 工具 '{tool_call.function.name}' 完成了它的任务! 其执行结果为: {result}"   
            )
            # Add tool response to memory
            tool_msg = Message.tool_message(
                content=result, tool_call_id=tool_call.id, name=tool_call.function.name
            )
            
            self.memory.add_message(tool_msg)
            tool_excute_results.append(result)
            
            if tool_call.function.name == 'terminate':
                await self.websocket.send_text("<<<END_OF_RESPONSE>>>")
                
        #await self.websocket.send_text("\n\n".join(tool_excute_results))
        return "\n\n".join(tool_excute_results)
        
    async def execute_tool(self, command: ToolCall) -> str:
        
        if not command or not command.function or not command.function.name:
            return "执行的工具参数错误"

        name = command.function.name
        if name not in self.available_tools.tool_map:
            return f"{name} 是未知工具，或者无法被{self.name}使用'"
        
        try:
            args = command.function.arguments
            args = json.loads(args) if args else {}
            result = await self.available_tools.execute(name=name, tool_input=args)
            
            # Format result for display
            observation = (
                f" `工具:{name}`的观测结果输出为 :\n{str(result)}"
                if result
                else f"`{name}` 执行结束，但没有输出结果"
            )
            await self._handle_special_tool(name=name, result=result)
            
            return observation

        except Exception as e:
            error_msg = f"⚠️ 工具 '{name}' 执行出现错误: {str(e)}"
            logger.error(error_msg)
            return f"错误: {error_msg}"
        
        
    async def _handle_special_tool(self, name: str, result: Any, **kwargs):
        if not self._is_special_tool(name):
            return

        if self._should_finish_execution(name=name, result=result, **kwargs):
            logger.info(f"🏁 Special tool '{name}' has completed the task!")
            self.state = AgentState.FINISHED

    @staticmethod
    def _should_finish_execution(**kwargs) -> bool:
        return True

    def _is_special_tool(self, name: str) -> bool:
        return name.lower() in [n.lower() for n in self.special_tool_names]
        
 