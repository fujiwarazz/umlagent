import gradio as gr
import asyncio
import re
from agents.umlagent import UMLAgent
from tools import ToolCollection, Terminate, PlanningTool, BaiduSearch, GitHubRepoCloner, FileSaver, FileSeeker, ReAsk, CreateChatCompletion, CodeToUMLTool, FinalResponse

# 创建UMLAgent实例
agent = UMLAgent(available_tools=ToolCollection(
    PlanningTool(), 
    FinalResponse(), 
    BaiduSearch(), 
    ReAsk(), 
    CodeToUMLTool(), 
    Terminate(), 
    CreateChatCompletion(), 
    GitHubRepoCloner(local_clone_base_dir="D:\deep_learning\codes\workspace"), 
    FileSeeker(), 
    FileSaver()
))

def format_message(message, is_user):
    """格式化消息以显示为元组格式 (user_message, bot_message)"""
    if is_user:
        return (message, None)  # 用户消息在右侧显示
    else:
        # 处理带特殊标记的消息
        processed = message
        
        # 分割不同级别的日志
        processed = re.sub(r'(\\u250c|\\u2514|\\u251c)', ' ', processed)
        
        # 标记特殊部分
        processed = re.sub(r'(✨ .*? 的想法为:)', r'\\n**\1**\\n', processed)
        processed = re.sub(r'(🛠️ .*? 选择了 \d+ 个工具)', r'\\n**\1**\\n', processed)
        processed = re.sub(r'(🧰 工具的参数是:)', r'\\n**\1**\\n', processed)
        processed = re.sub(r'(🎯 工具 '\.*?' 完成了它的任务! 其执行结果为:)', r'\\n**\1**\\n', processed)
        processed = re.sub(r'(🏁 Special tool '\.*?' has completed the task!)', r'\\n**\1**\\n', processed)
        processed = re.sub(r'(🚨 出错啦! .*? 在思考时出现了错误)', r'\\n**\1**\\n', processed)
        
        # 添加缩进
        processed = re.sub(r'(Step \d+ updated in plan)', r'\\n\1', processed)
        
        return (None, processed)

async def process_query(query):
    """处理用户查询的异步函数"""
    result = await agent.run(query)
    return result

def run_agent(query, chat_history):
    """运行UMLAgent处理用户查询"""
    # 如果chat_history为空，初始化它
    if chat_history is None:
        chat_history = []
    
    # 添加用户输入到聊天历史
    if query:
        formatted_query = format_message(query, is_user=True)
        chat_history.append(formatted_query)
    
    # 运行Agent
    result = asyncio.run(process_query(query))
    
    # 添加LLM响应到聊天历史
    formatted_result = format_message(result, is_user=False)
    chat_history.append(formatted_result)
    
    # Gradio期望返回更新后的chat_history和一个空字符串（用于清除输入框）
    return chat_history, ""

# 创建Gradio界面
demo = gr.ChatInterface(
    fn=run_agent,
    chatbot=gr.Chatbot(
        bubble_full_width=False,
        height=600,
        sanitize_html=False  # 禁用HTML清理以保留Markdown格式
    ),
    examples=[
        ["Analyze the project structure and generate a UML diagram"],
        ["Explain the class relationships in the project"]
    ],
    additional_inputs_accordion=gr.Accordion(label="Chat Controls", open=False)
)

if __name__ == "__main__":
    demo.launch()