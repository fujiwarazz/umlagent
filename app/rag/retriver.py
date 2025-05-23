from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.schema import BaseRetriever
from utils.logger import logger
import os
import asyncio
from pydantic import BaseModel, Field
from typing import Any
from config.app_config import VECTORDB_PATH
from langchain.schema.document import Document
from typing import List
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
        return self.retriever.get_relevant_documents(query, **kwargs)
        

from langchain.embeddings import DashScopeEmbeddings

class VectorStore:
    def __init__(self):
        """ 初始化向量数据库 """
        try:
            self.embedding = DashScopeEmbeddings(
                model = 'text-embedding-v3',
                dashscope_api_key =  os.environ.get("DASHSCOPE_API_KEY")
            )
        except Exception as e:
            logger.error(f"加载embedding模型失败:{e}")
            raise
        self.db_lock = asyncio.Lock()
        
    async def add_chunks(self,chunks):
        chunks = self._handle_indexer_chunks(chunks)
        index_path = os.path.join(VECTORDB_PATH,"index.faiss")
        if os.path.exists(index_path):
            try:
                async with self.db_lock:
                    vec_store = FAISS.load_local(
                            VECTORDB_PATH,
                            embeddings=self.embedding
                        )
                    vec_store.add_documents(chunks)
            except Exception as e:
                async with self.db_lock:
                    vec_store = await self._create_vector_store(chunks)
        else:
            async with self.db_lock:
                vec_store = await self._create_vector_store(chunks)
        
        return True if vec_store else False
    
    async def get_async_retriever(self,chunks_origin=None):
        try:
            os.mkdir(VECTORDB_PATH,exist_ok = True)
            index_path = os.path.join(VECTORDB_PATH,"index.faiss")
            if os.path.exists(index_path):
                try:
                    async with self.db_lock:
                        vec_store = FAISS.load_local(
                            VECTORDB_PATH,
                            embeddings=self.embedding
                        )
                    logger.info("加载本地向量数据库成功")
                except Exception as e:
                    logger.error(f"加载本地向量数据库失败:{e}, 将创建新的向量数据库")
                    async with self.db_lock:
                        vec_store = await self._create_vector_store(chunks_origin)
            else:
                async with self.db_lock:
                    vec_store = await self._create_vector_store(chunks_origin)
            
            base_retriever = vec_store.as_retriever(
                search_type="mmr",
                search_kwargs= {"k": 5, "fetch_k": 20, "lambda_mult": 0.5},
            )
            return AsyncVectorStoreRetriever(base_retriever)
            
        except Exception as e:
           logger.error(f"创建或加载向量存储失败:{e}",exc_info = True)
           raise
    
    def _handle_indexer_chunks(self,chunks) -> List[Document]:
        documents_for_faiss: List[Document] = []
            
        for file_info in chunks:
            file_path = file_info["file"]
            for chunk_text in file_info["chunks"]:
                documents_for_faiss.append(
                    Document(page_content=chunk_text, metadata={"source": file_path})
                )
        
        return documents_for_faiss
    async def _create_vector_store(self,chunks):
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
            documents_for_faiss = self._handle_indexer_chunks(chunks)
                    
            vec_store = await asyncio.to_thread(FAISS.from_documents,
                                                documents_for_faiss,
                                                self.embedding)
            vec_store.save_local(os.path.join(VECTORDB_PATH,"code_base.faiss"))   
            logger.info(f"向量数据库创建成功，已保存")
            return vec_store 
        
        except Exception as e:
            logger.error(f"向量数据库创建失败，错误信息：{e}",exc_info = True)
            raise
    

        