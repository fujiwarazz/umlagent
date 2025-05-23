from tools.base import BaseTool, ToolResult, ToolFailure 
from utils.logger import logger # 假设您有一个名为 logger 的日志记录器
import asyncio 
from utils.exceptions import ToolError
from typing import Optional
from utils.logger import logger
from rag.indexer import CodeProjectIndexer
from rag.retriver import VectorStore
import os
from typing import List
from langchain.schema.document import Document



class RAG(BaseTool):
    name: str = "rag"
    description: str = """一个RAG工具，可以通过这个工具将文本内容embedding化并存入向量数据库，或从数据库中查询相似内容。
    用于代码库索引化和查询相关代码片段。
    命令 'add_rag'：需要 'code_path' 参数，用于索引代码库并将其添加到向量数据库。
    命令 'query_rag'：需要 'query' 参数，用于从已索引的数据库中检索相关代码片段。"""
    strict: bool = True # As per your definition
    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {
                "description": "要执行的命令。可用命令: `query_rag`, `add_rag`。使用 `query_rag` 从RAG获取相关块。使用 `add_rag` 生成向量数据库并将块添加到其中，或仅将块添加到其中。",
                "enum": [
                    "query_rag",
                    "add_rag"
                ],
                "type": "string"
            },
            "query": {
                "description": "您对向量数据库的查询，您可以获得一些与您的查询相关的块。",
                "type": "string"
            },
            "code_path": {
                "description": "将被嵌入并放入向量数据库的代码的路径。",
                "type": "string" # Corrected from missing type in prompt
            }
        },
        "additionalProperties": False, # Corrected from 'addtionalProperties'
        "required": ["command"]
    }
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # VectorStore will be instantiated per command to ensure it loads/creates based on current disk state
        # and handles its own async lock for file operations.

    async def add_rag(self, code_path: str) -> ToolResult | ToolFailure:
        logger.info(f"RAG Tool: 'add_rag' command received for code_path: {code_path}")
        if not os.path.isdir(code_path):
            return ToolFailure(f"提供的代码路径 '{code_path}' 不是一个有效的目录或不存在。")
        
        try:
            indexer = CodeProjectIndexer()
            indexed_data = await indexer.index_project(project_path=code_path) # Returns List[Dict[str, List[str]]]
            
            if not indexed_data:
                logger.warning(f"在路径 '{code_path}' 中没有找到可索引的内容。")
                return ToolResult(content=f"在路径 '{code_path}' 中没有找到可索引的内容或没有可处理的文件。", success=True)

            vector_store_manager = VectorStore()
            success = await vector_store_manager.add_chunks(chunks=indexed_data)
            
            if success:
                return ToolResult(content=f"成功将 '{code_path}' 的内容索引并添加到RAG数据库。共处理 {len(indexed_data)} 个文件数据条目。", success=True)
            else:
                # This case might not be hit if add_documents raises on critical failure
                return ToolFailure(f"尝试将 '{code_path}' 的内容添加到RAG数据库时发生未知错误。")

        except ValueError as ve: # Catch specific errors like invalid path for CodeProjectIndexer
            logger.error(f"RAG _add_rag ValueError: {ve}", exc_info=True)
            return ToolFailure(error_message=f"处理 'add_rag' 命令时发生值错误: {ve}")
        except Exception as e:
            logger.error(f"RAG _add_rag 异常: {e}", exc_info=True)
            return ToolFailure(error_message=f"处理 'add_rag' 命令时发生意外错误: {e}", error_details=str(e))

    async def query_rag(self, query: str) -> ToolResult | ToolFailure:
        logger.info(f"RAG Tool: 'query_rag' command received with query: '{query}'")
        try:
            vector_store_manager = VectorStore()
            # For querying, we don't provide initial_indexer_output,
            # so get_retriever will fail if DB doesn't exist.
            retriever = await vector_store_manager.get_async_retriever() 
            
            documents: List[Document] = await retriever._aget_relevant_documents(query) # Using the async method
            
            if not documents:
                return ToolResult(content=f"未能找到与查询 '{query}' 相关的文档。", success=True) # Success=True, but no results

            # Format results for output
            formatted_results = [
                {
                    "content": doc.page_content,
                    "source": doc.metadata.get("source", "unknown")
                } for doc in documents
            ]
            return ToolResult(output=formatted_results, success=True)

        except FileNotFoundError as fnfe: # Specifically catch if DB not found and no init data
            logger.error(f"RAG _query_rag FileNotFoundError: {fnfe}", exc_info=True)
            return ToolFailure(error_message=f"查询RAG数据库失败: {fnfe}. 请先使用 'add_rag' 命令添加数据。")
        except ValueError as ve: # Catch other ValueErrors from get_retriever
             logger.error(f"RAG _query_rag ValueError: {ve}", exc_info=True)
             return ToolFailure(error_message=f"查询RAG数据库时发生值错误: {ve}")
        except Exception as e:
            logger.error(f"RAG _query_rag 异常: {e}", exc_info=True)
            return ToolFailure(error_message=f"查询RAG数据库时发生意外错误: {e}", error_details=str(e))

    async def execute(self, command: str, query: Optional[str] = None, code_path: Optional[str] = None) -> ToolResult | ToolFailure:
        logger.info(f"RAG Tool executing command: {command}")
        # Parameter validation as per schema 'required' for command
        if command == 'query_rag':
            if not query:
                return ToolFailure("命令 'query_rag' 需要 'query' 参数。")
            # Ensure code_path is not mistakenly passed or used
            if code_path is not None:
                logger.warning("为 'query_rag' 命令传递了 'code_path' 参数，该参数将被忽略。")
            return await self.query_rag(query=query)
        elif command == "add_rag":
            if not code_path:
                return ToolFailure("命令 'add_rag' 需要 'code_path' 参数。")
            # Ensure query is not mistakenly passed or used
            if query is not None:
                logger.warning("为 'add_rag' 命令传递了 'query' 参数，该参数将被忽略。")
            return await self.add_rag(code_path=code_path)
        else:
            # This case should ideally be caught by schema validation before execute is called
            # if the calling mechanism uses the tool's parameters schema.
            return ToolFailure(f"未知命令 '{command}'。可用命令: 'query_rag', 'add_rag'。")
        
