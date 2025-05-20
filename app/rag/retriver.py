from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import FAISS
# BaseRetriever是检索器的基类,提供了检索文档的基本接口
from langchain.schema import BaseRetriever
from utils.logger import logger
import os
import asyncio
# BaseModel 是一个抽象基类，用于数据验证，Field用于字段定义
from pydantic import BaseModel, Field
from typing import Any
from config.app_config import VECTORDB_PATH
class AsyncVectorStoreRetriever(BaseRetriever):
    retriever:Any = Field(description= "原始向量存储检索器")
    
    class config:
        arbitary_types_allowed = True
    
    def __init__(self,retriever,**kwargs) -> None:
        super.__init__(retriever = retriever,**kwargs)
        
    async def _aget_relevant_documents(self,query,**kwargs):
        """
        在单独的线程中调用原始向量存储检索器的相关文档
        Args:
            query (_type_): 询问

        Returns:
            chunks: 知识库中的相关知识
        """
        return await asyncio.to_thread(
            self.retriever.get_relevant_documents,
            query,
            **kwargs
        )
    def _get_relevant_documents(self,query,**kwargs):
        # 同步调用, 调用原始检索器的get_relevant_documents方法
        return query | self.retriever
        

class VectorStore:
    def __init__(self):
        """ 初始化向量数据库 """
        try:
            # self.embedding = OllamaEmbeddings(
            #     model = settings.OLLAMA_MODEL,
            # )
            # logger.info(f"已加载embedding模型:{settings.OLLAMA_MODEL}")
        except Exception as e:
            logger.error(f"加载embedding模型失败:{e}")
            raise
        
    async def get_vectorstore(self,docs):
        """创建或者加载FAISS数据库"""
        try:
            os.mkdir(settings.VECTOR_DB_PATH,exist_ok = True)
            
            index_path = os.path.join(settings.VECTOR_DB_PATH,settings.VECTOR_DB_NAME)
            
            if os.path.exists(index_path):
                try:
                    vec_store = FAISS.load_local(
                        settings.VECTOR_DB_PATH,
                        self.embedding
                    )
                    logger.info("加载本地向量数据库成功")
                except Exception as e:
                    logger.error(f"加载本地向量数据库失败:{e}, 将创建新的向量数据库")
                    vec_store = await self._create_vector_store(docs)
                    
            else:
                vec_store = await self._create_vector_store(docs)
            
           # 创建基础检索器，用于从FAISS中检索最匹配的文本片段
            base_retriever = vec_store.as_retriever(
                search_kwargs={"k": settings.TOP_K},
                search_type="similarity",
            )
            # 创建异步向量存储检索器，用于异步检索最匹配的文本片段
            return AsyncVectorStoreRetriever(base_retriever)
            
        except Exception as e:
           logger.error(f"创建或加载向量存储失败:{e}",exc_info = True)
           raise
       
    async def _create_vector_store(self,docs):
        try:
            """
            创建向量存储
            步骤：
                1. 使用embedding模型将chunks变为embedding
                2. 创建FAISS存储embedding过后的chunks
                3. 创建文档和向量的mapping
            Args:
                docs (_type_): 文档
            """
            vec_store = await asyncio.to_thread(FAISS.from_documents,
                                                docs,
                                                self.embedding)
            vec_store.save_local(settings.VECTOR_DB_PATH)   
            logger.info(f"向量数据库创建成功，已保存")
            return vec_store 
        
        except Exception as e:
            logger.error(f"向量数据库创建失败，错误信息：{e}",exc_info = True)
            raise
    

        