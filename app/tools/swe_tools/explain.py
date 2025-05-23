import os
from typing import Optional, List, Dict, Any
from tools.base import BaseTool, ToolResult, ToolFailure # 假设的导入路径
from utils.logger import logger # 假设的导入路径
import aiofiles
import asyncio
from openai import (
    APIError,
    AsyncOpenAI,
    AuthenticationError,
    OpenAIError,
    RateLimitError,
)

from config.llm_config import LLMSettings
class CodeAnalyzer(BaseTool):
    name: str = "code_analyzer"
    description: str = """使用LLM分析一个或多个代码文件。
此工具会读取每个指定文件的内容，将其发送给LLM进行分析，
然后将所有分析结果汇总成一份报告。
适用于理解代码库、生成文档摘要等场景。
"""
    parameters: dict = {
        "type": "object",
        "properties": {
            "file_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "(required) 需要分析的代码文件的绝对路径列表。例如：['/path/to/file1.py', '/path/to/project/module/file2.js']",
            }
        },
        "required": ["file_paths"],
    }
    
    client:AsyncOpenAI = None
    history:List = []
    
    async def _ask_llm(self,content) -> str:
        if self.client is None:
            self.client = AsyncOpenAI(api_key=LLMSettings.api_key,base_url=LLMSettings.base_url)
            
        prompt = f"帮我分析以下代码：{content}"
        self.history.append({"role":"user","content":prompt})
        
        response = await self.client.chat.completions.create(
                    model=LLMSettings.model,
                    messages=self.history,
                    max_tokens=LLMSettings.max_tokens,
                    temperature=LLMSettings.temperature,
                    stream=False,
                )
        
        if not response.choices or not response.choices[0].message:
            raise ValueError("LLM 没有返回任何信息")
        self.history.append({"role":"assistant","content":response.choices[0].message.content})
        return response.choices[0].message.content
        

    async def _analyze_single_file(self, file_path: str) -> str:
        """
        异步读取单个文件，并调用LLM获取其分析结果。
        每个文件的分析被视为一个独立的任务。

        Args:
            file_path (str): 要分析的文件的完整路径。

        Returns:
            str: 针对该文件的格式化分析结果。
        """
        try:
            async with aiofiles.open(file_path, mode="r", encoding="utf-8") as file:
                content = await file.read()
            
            if not content.strip(): # 检查文件是否为空或只包含空白符
                analysis_result = "文件为空或只包含空白字符，无实质内容可分析。"
            else:
                # **重要**: 在此处调用您实际的LLM分析函数
                # 例如: analysis_result = await actual_llm_client.analyze_code(content, file_path=file_path)
                analysis_result = await self._ask_llm(content)
            
            return f"对于 {file_path} 文件，大致内容为：{analysis_result}"
        except FileNotFoundError:
            return f"对于 {file_path} 文件，分析错误：文件未找到。"
        except Exception as e:
            # 对于其他潜在错误，例如权限问题或编码问题
            return f"对于 {file_path} 文件，分析时发生错误：{str(e)}"

    async def execute(self, file_paths: List[str]) -> str:
        """
        接收一个文件路径列表，对每个文件进行代码分析，并返回汇总的分析结果。

        Args:
            file_paths (List[str]): 需要进行分析的代码文件的路径列表。

        Returns:
            str: 包含所有文件分析结果的汇总字符串。
                 每个文件的分析结果格式为："对于 xxx文件，大致内容为：yyy（llm response）"。
                 不同文件的分析结果之间用两个换行符分隔。
        """
        if not file_paths:
            return "错误：未提供文件路径列表。请提供一个包含一个或多个文件路径的列表。"
        
        # 为每个文件路径创建一个分析任务
        # asyncio.gather 并发执行所有这些独立的分析任务
        analysis_tasks = [self._analyze_single_file(fp) for fp in file_paths]
        results = await asyncio.gather(*analysis_tasks)
        
        # 将所有任务的返回结果（每个都是一个格式化字符串）用换行符连接起来
        return "\n\n".join(results)