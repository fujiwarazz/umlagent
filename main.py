import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from agents.umlagent import UMLAgent
from utils.entity import Message as AgentMessage

app = FastAPI()

# 存储正在进行的对话
conversations: Dict[str, UMLAgent] = {}

class QueryRequest(BaseModel):
    query: str

class ConversationStartResponse(BaseModel):
    conversationId: str
    message: str

class StreamResponse(BaseModel):
    type: str  # llm_thought, tool_call, tool_result, final_response, error
    content: str

@app.post("/api/start-conversation", response_model=ConversationStartResponse)
async def start_conversation(request: QueryRequest):
    """初始化一个新的对话并返回conversationId"""
    try:
        # 创建新的UMLAgent实例
        agent = UMLAgent()
        
        # 获取唯一的conversation ID
        conversation_id = f"conv_{len(conversations)}_{int(asyncio.get_event_loop().time())}"
        
        # 将用户查询添加到代理的记忆中
        agent.update_memory("user", request.query)
        
        # 将代理存储在全局字典中
        conversations[conversation_id] = agent
        
        return ConversationStartResponse(
            conversationId=conversation_id,
            message="Conversation started successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start conversation: {str(e)}")

@app.get("/api/stream")
async def stream(conversationId: str):
    """为指定的对话生成流式响应"""
    if conversationId not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    async def event_generator():
        try:
            # 获取对应的代理
            agent = conversations[conversationId]
            
            # 运行代理并获取结果
            result = await agent.run()
            
            # 解析结果并发送事件
            lines = result.split('\n')
            current_section = None
            
            for line in lines:
                if not line.strip():
                    continue
                
                # LLM思考部分
                if re.match(r'✨ .* 的想法为:', line):
                    yield {"event": "message", "data": f"{{\"type\": \"llm_thought\", \"content\": \"{line}\"}}"}
                # 工具调用部分
                elif re.match(r'🛠️ .* 选择了 \d+ 个工具', line):
                    yield {"event": "message", "data": f"{{\"type\": \"tool_call\", \"content\": \"{line}\"}}"}
                # 工具参数部分
                elif re.match(r'🧰 工具的参数是:', line):
                    yield {"event": "message", "data": f"{{\"type\": \"tool_call\", \"content\": \"{line}\"}}"}
                # 工具执行结果
                elif re.match(r'🎯 工具 .* 完成了它的任务! 其执行结果为:', line):
                    yield {"event": "message", "data": f"{{\"type\": \"tool_result\", \"content\": \"{line}\"}}"}
                # 特殊工具完成
                elif re.match(r'🏁 Special tool .* has completed the task!', line):
                    yield {"event": "message", "data": f"{{\"type\": \"tool_result\", \"content\": \"{line}\"}}"}
                # 错误信息
                elif re.match(r'🚨 ', line):
                    yield {"event": "message", "data": f"{{\"type\": \"error\", \"content\": \"{line}\"}}"}
                # 最终响应
                else:
                    yield {"event": "message", "data": f"{{\"type\": \"final_response\", \"content\": \"{line}\"}}"}
                
                # 检查是否应该终止
                if any(marker in line.lower() for marker in ['terminate', 'completed', 'finished']):
                    break
                
                # 等待一段时间以模拟流式传输
                await asyncio.sleep(0.1)
            
            # 删除已完成的对话
            del conversations[conversationId]
            
        except Exception as e:
            yield {"event": "message", "data": f"{{\"type\": \"error\", \"content\": \"❌ 后端错误: {str(e)}\"}}"}
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)