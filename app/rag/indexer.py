import asyncio
import os
from pathlib import Path
from typing import List, Dict
import aiofiles
from langchain.text_splitter import RecursiveCharacterTextSplitter
class CodeProjectIndexer:
    def __init__(self, 
                 project_path: str,
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200):
        self.project_path = Path(project_path)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )
        
        # File extensions to process
        self.target_extensions = {
            '.py', '.js', '.java', '.cpp', '.h', '.hpp', '.c',
            '.txt', '.md', '.rst', '.yaml', '.yml',
            'README', 'requirements.txt', 'Dockerfile'
        }

    async def read_file_async(self, file_path: Path) -> str:
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                return content
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return ""

    def should_process_file(self, file_path: Path) -> bool:
        """Check if the file should be processed based on extension and name."""
        return (file_path.suffix in self.target_extensions or
                file_path.name in self.target_extensions)

    async def get_all_files(self) -> List[Path]:
        """Get all relevant files in the project directory."""
        files = []
        for root, _, filenames in os.walk(self.project_path):
            for filename in filenames:
                file_path = Path(root) / filename
                if self.should_process_file(file_path):
                    files.append(file_path)
        return files

    async def process_file(self, file_path: Path) -> Dict[str, List[str]]:
        content = await self.read_file_async(file_path)
        if not content:
            print(f"Skipping empty or error file: {file_path}") # 增加此行
            return {"file": str(file_path), "chunks": []}

        print(f"Processing file: {file_path}") # 增加此行

        chunks = self.text_splitter.split_text(content)

        return {
            "file": str(file_path),
            "chunks": chunks
        }
    async def index_project(self) -> List[Dict[str, List[str]]]:
        """Index the entire project asynchronously."""
        files = await self.get_all_files()
        tasks = [self.process_file(file) for file in files]
        results = await asyncio.gather(*tasks)
        return [result for result in results if result["chunks"]]

