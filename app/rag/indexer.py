import asyncio
import os
from pathlib import Path
from typing import List, Dict
import aiofiles
from langchain.text_splitter import RecursiveCharacterTextSplitter
class CodeProjectIndexer:
    def __init__(self, 
                 chunk_size: int = 1000,
                 chunk_overlap: int = 200):
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

    async def _read_file_async(self, file_path: Path) -> str:
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                return content
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return ""

    def _should_process_file(self, file_path: Path) -> bool:
        """Check if the file should be processed based on extension and name."""
        return (file_path.suffix in self.target_extensions or
                file_path.name in self.target_extensions)

    # async def _get_all_files(self) -> List[Path]:
    #     """Get all relevant files in the project directory."""
    #     files = []
    #     for root, _, filenames in os.walk(self.project_path):
    #         for filename in filenames:
    #             file_path = Path(root) / filename
    #             if self._should_process_file(file_path):
    #                 files.append(file_path)
    #     return files
    
    async def _get_all_files(self) -> List[Path]:
        """Get all relevant files in the project directory recursively."""
        async def _recursive_get_files(directory: Path) -> List[Path]:
            files = []
            try:
                for item in directory.iterdir():
                    if item.is_file() and self._should_process_file(item):
                        files.append(item)
                    elif item.is_dir():
                        # Skip hidden directories and common excludes
                        if not item.name.startswith('.') and item.name not in {'__pycache__', 'log', 'temp', 'node_modules', 'venv', 'env'}:
                            files.extend(await _recursive_get_files(item))
            except PermissionError:
                print(f"Permission denied accessing {directory}")
            return files

        return await _recursive_get_files(self.project_path)


    async def _process_file(self, file_path: Path) -> Dict[str, List[str]]:
        content = await self._read_file_async(file_path)
        if not content:
            return {"file": str(file_path), "chunks": []}
        chunks = await asyncio.to_thread(self.text_splitter.split_text, content)
        return {
            "file": str(file_path),
            "chunks": chunks
        }
    async def index_project(self,project_path) -> List[Dict[str, List[str]]]:
        self.project_path = Path(project_path)

        files = await self._get_all_files()
        tasks = [self._process_file(file) for file in files]
        results = await asyncio.gather(*tasks)
        return [result for result in results if result["chunks"]]

