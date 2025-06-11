from retriver import AsyncVectorStoreRetriever,VectorStore
from indexer import CodeProjectIndexer
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
async def test_rag():
    """
    测试RAG功能
    """
    # 初始化索引器
     # 初始化向量存储
    indexer = CodeProjectIndexer()
    vector = VectorStore()
    chunks = await indexer.index_project(project_path="D:\\deep_learning\\codes\\umlagent\\app\\workspace\\tmp_codes\\LLaVA-NeXT")
    retriever = await vector.get_async_retriever()
    res = await retriever.aget_relevant_documents("这个项目的dpo训练过程是什么?")
    print(res)
    
if __name__ == "__main__":
    import asyncio
    asyncio.run(test_rag())