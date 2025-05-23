import os
from typing import Optional, List, Dict, Any
from tools.base import BaseTool, ToolResult, ToolFailure # 假设的导入路径
from utils.logger import logger # 假设的导入路径

import os
import shutil # 用于递归删除目录
from typing import Optional, List, Dict, Any
from tools.base import BaseTool, ToolResult, ToolFailure # 假设的导入路径d
from utils.logger import logger # 假设的导入路径

class FileOperatorTool(BaseTool):
    name: str = "file_operator"
    description: str = """对文件系统进行操作，如读取、写入、创建或删除文件和目录。
    用于深入查看特定文件内容、修改代码或管理项目文件。
    命令 'read_file'：读取文件内容。参数: 'path', 可选 'start_line', 'end_line', 'encoding'。
    命令 'write_file'：向文件写入内容（覆盖或追加）。参数: 'path', 'content', 可选 'mode' ('w'或'a'), 'encoding'。
    命令 'list_directory'：列出目录内容。参数: 'path', 可选 'recursive', 'max_depth'。
    命令 'create_file'：创建新文件，可选择写入初始内容。参数: 'path', 可选 'content', 'encoding'。
    命令 'create_directory'：创建新目录。参数: 'path', 可选 'parents' (布尔值，类似 mkdir -p)。
    命令 'delete_file'：删除文件。参数: 'path'。
    命令 'delete_directory'：删除目录。参数: 'path', 可选 'recursive' (布尔值，如果目录非空则需为True)。"""
    strict: bool = True
    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {
                "description": "要执行的文件操作命令。",
                "enum": ["read_file", "write_file", "list_directory", "create_file", "create_directory", "delete_file", "delete_directory"],
                "type": "string"
            },
            "path": {
                "description": "目标文件或目录的绝对或相对路径。",
                "type": "string"
            },
            "content": {
                "description": "（可选）用于 'write_file' 或 'create_file' 的文件内容。",
                "type": "string"
            },
            "start_line": {
                "description": "（可选）用于 'read_file'，读取的起始行号 (从1开始)。",
                "type": "integer",
                "minimum": 1
            },
            "end_line": {
                "description": "（可选）用于 'read_file'，读取的结束行号 (包含此行)。",
                "type": "integer",
                "minimum": 1
            },
            "encoding": {
                "description": "（可选）用于文件读写操作的编码格式，默认为 'utf-8'。",
                "type": "string"
            },
            "mode": {
                "description": "（可选）用于 'write_file'，写入模式：'w' (覆盖，默认) 或 'a' (追加)。",
                "enum": ["w", "a"],
                "type": "string"
            },
            "recursive": {
                "description": "（可选）用于 'list_directory' 或 'delete_directory'，是否递归操作。",
                "type": "boolean"
            },
            "max_depth": {
                "description": "（可选）用于 'list_directory' 且 recursive=True 时，限制递归列出的深度。",
                "type": "integer",
                "minimum": 1
            },
            "parents": {
                "description": "（可选）用于 'create_directory'，如果为True，则创建所有必需的父目录 (类似 mkdir -p)。",
                "type": "boolean"
            }
        },
        "additionalProperties": False,
        "required": ["command", "path"]
    }

    def __init__(self, workspace_root: str, **kwargs): # Agent的工作区根目录，用于安全和路径解析
        super().__init__(**kwargs)
        self.workspace_root = os.path.abspath(workspace_root)
        logger.info(f"FileOperatorTool initialized with workspace_root: {self.workspace_root}")

    def _resolve_path(self, path: str) -> str | None:
        """将用户提供的路径解析为工作区内的绝对路径，并进行安全检查。"""
        abs_path = os.path.abspath(os.path.join(self.workspace_root, path))
        if not abs_path.startswith(self.workspace_root):
            logger.warning(f"Path traversal attempt blocked: '{path}' resolved to '{abs_path}' which is outside workspace '{self.workspace_root}'")
            return None
        return abs_path

    async def read_file(self, path: str, start_line: Optional[int] = None, end_line: Optional[int] = None, encoding: str = 'utf-8') -> ToolResult | ToolFailure:
        logger.info(f"FileOperatorTool: 'read_file' for path: {path}, lines: {start_line}-{end_line}, encoding: {encoding}")
        safe_path = self._resolve_path(path)
        if not safe_path:
            return ToolFailure(f"路径 '{path}' 无效或位于允许的工作区之外。")
        if not os.path.isfile(safe_path):
            return ToolFailure(f"文件 '{safe_path}' 不存在或不是一个文件。")
        try:
            with open(safe_path, 'r', encoding=encoding) as f:
                if start_line is not None and end_line is not None:
                    if start_line <= 0 or end_line < start_line:
                        return ToolFailure("无效的起止行号。")
                    lines = f.readlines()
                    content_lines = lines[start_line-1:end_line]
                    content = "".join(content_lines)
                elif start_line is not None: # 只指定了起始行
                    if start_line <= 0: return ToolFailure("无效的起始行号。")
                    lines = f.readlines()
                    content_lines = lines[start_line-1:]
                    content = "".join(content_lines)
                else: # 读取整个文件
                    content = f.read()
            return ToolResult(content=f"文件 '{path}' 的内容 (共 {len(content.splitlines()) if content else 0} 行):\n{content}", success=True)
        except Exception as e:
            logger.error(f"FileOperatorTool read_file 异常: {e}", exc_info=True)
            return ToolFailure(error_message=f"读取文件 '{path}' 时发生错误: {e}", error_details=str(e))

    async def write_file(self, path: str, content: str, mode: str = 'w', encoding: str = 'utf-8') -> ToolResult | ToolFailure:
        logger.info(f"FileOperatorTool: 'write_file' to path: {path}, mode: {mode}, encoding: {encoding}")
        safe_path = self._resolve_path(path)
        if not safe_path:
            return ToolFailure(f"路径 '{path}' 无效或位于允许的工作区之外。")
        
        parent_dir = os.path.dirname(safe_path)
        if not os.path.isdir(parent_dir):
             return ToolFailure(f"父目录 '{parent_dir}' 不存在。请先使用 'create_directory' 创建。")

        if mode not in ['w', 'a']:
            return ToolFailure(f"无效的写入模式 '{mode}'。仅支持 'w' (覆盖) 或 'a' (追加)。")
        try:
            with open(safe_path, mode, encoding=encoding) as f:
                f.write(content)
            action = "覆盖写入" if mode == 'w' else "追加写入"
            return ToolResult(content=f"成功将内容 {action} 到文件 '{path}'。", success=True)
        except Exception as e:
            logger.error(f"FileOperatorTool write_file 异常: {e}", exc_info=True)
            return ToolFailure(error_message=f"写入文件 '{path}' 时发生错误: {e}", error_details=str(e))

    def _list_dir_recursive(self, dir_path: str, current_depth: int, max_depth: Optional[int], prefix: str = "") -> List[str]:
        """辅助函数：递归列出目录内容并格式化"""
        entries = []
        if max_depth is not None and current_depth >= max_depth:
            return entries
        
        try:
            for item in sorted(os.listdir(dir_path)):
                item_path = os.path.join(dir_path, item)
                is_dir = os.path.isdir(item_path)
                entries.append(f"{prefix}{item}{'/' if is_dir else ''}")
                if is_dir:
                    entries.extend(self._list_dir_recursive(item_path, current_depth + 1, max_depth, prefix + "  "))
        except OSError as e:
            entries.append(f"{prefix}[无法访问: {os.path.basename(dir_path)} - {e.strerror}]")
        return entries

    async def list_directory(self, path: str, recursive: bool = False, max_depth: Optional[int] = None) -> ToolResult | ToolFailure:
        logger.info(f"FileOperatorTool: 'list_directory' for path: {path}, recursive: {recursive}, max_depth: {max_depth}")
        safe_path = self._resolve_path(path)
        if not safe_path:
            return ToolFailure(f"路径 '{path}' 无效或位于允许的工作区之外。")
        if not os.path.isdir(safe_path):
            return ToolFailure(f"路径 '{safe_path}' 不是一个有效的目录。")
        try:
            if recursive:
                contents = self._list_dir_recursive(safe_path, 0, max_depth)
            else:
                contents = [f"{item}{'/' if os.path.isdir(os.path.join(safe_path, item)) else ''}" for item in sorted(os.listdir(safe_path))]
            
            if not contents:
                return ToolResult(content=f"目录 '{path}' 为空。", success=True)
            return ToolResult(content=f"目录 '{path}' 的内容:\n" + "\n".join(contents), success=True)
        except Exception as e:
            logger.error(f"FileOperatorTool list_directory 异常: {e}", exc_info=True)
            return ToolFailure(error_message=f"列出目录 '{path}' 内容时发生错误: {e}", error_details=str(e))

    async def create_file(self, path: str, content: Optional[str] = None, encoding: str = 'utf-8') -> ToolResult | ToolFailure:
        logger.info(f"FileOperatorTool: 'create_file' at path: {path}")
        safe_path = self._resolve_path(path)
        if not safe_path:
            return ToolFailure(f"路径 '{path}' 无效或位于允许的工作区之外。")
        
        parent_dir = os.path.dirname(safe_path)
        if not os.path.isdir(parent_dir):
             return ToolFailure(f"父目录 '{parent_dir}' 不存在。请先使用 'create_directory' 创建。")

        if os.path.exists(safe_path):
            return ToolFailure(f"文件 '{path}' 已存在。")
        try:
            with open(safe_path, 'w', encoding=encoding) as f:
                if content:
                    f.write(content)
            return ToolResult(content=f"成功创建文件 '{path}'。" + (f" 并写入了 {len(content)} 字节内容。" if content else ""), success=True)
        except Exception as e:
            logger.error(f"FileOperatorTool create_file 异常: {e}", exc_info=True)
            return ToolFailure(error_message=f"创建文件 '{path}' 时发生错误: {e}", error_details=str(e))

    async def create_directory(self, path: str, parents: bool = False) -> ToolResult | ToolFailure:
        logger.info(f"FileOperatorTool: 'create_directory' at path: {path}, parents: {parents}")
        safe_path = self._resolve_path(path)
        if not safe_path:
            return ToolFailure(f"路径 '{path}' 无效或位于允许的工作区之外。")
        if os.path.isdir(safe_path):
            return ToolFailure(f"目录 '{path}' 已存在。")
        if os.path.isfile(safe_path):
             return ToolFailure(f"路径 '{path}' 已存在并且是一个文件，无法创建同名目录。")
        try:
            if parents:
                os.makedirs(safe_path, exist_ok=True) # exist_ok=True 使得如果目录已存在（虽然前面检查过，但并发情况下可能有帮助）不会报错
            else:
                parent_dir = os.path.dirname(safe_path)
                if not os.path.isdir(parent_dir):
                    return ToolFailure(f"父目录 '{parent_dir}' 不存在。如果需要创建父目录，请设置 'parents' 参数为 true。")
                os.mkdir(safe_path)
            return ToolResult(content=f"成功创建目录 '{path}'。", success=True)
        except Exception as e:
            logger.error(f"FileOperatorTool create_directory 异常: {e}", exc_info=True)
            return ToolFailure(error_message=f"创建目录 '{path}' 时发生错误: {e}", error_details=str(e))

    async def delete_file(self, path: str) -> ToolResult | ToolFailure:
        logger.info(f"FileOperatorTool: 'delete_file' at path: {path}")
        safe_path = self._resolve_path(path)
        if not safe_path:
            return ToolFailure(f"路径 '{path}' 无效或位于允许的工作区之外。")
        if not os.path.isfile(safe_path):
            return ToolFailure(f"文件 '{path}' 不存在或不是一个文件。")
        try:
            os.remove(safe_path)
            return ToolResult(content=f"成功删除文件 '{path}'。", success=True)
        except Exception as e:
            logger.error(f"FileOperatorTool delete_file 异常: {e}", exc_info=True)
            return ToolFailure(error_message=f"删除文件 '{path}' 时发生错误: {e}", error_details=str(e))

    async def delete_directory(self, path: str, recursive: bool = False) -> ToolResult | ToolFailure:
        logger.info(f"FileOperatorTool: 'delete_directory' at path: {path}, recursive: {recursive}")
        safe_path = self._resolve_path(path)
        if not safe_path:
            return ToolFailure(f"路径 '{path}' 无效或位于允许的工作区之外。")
        if not os.path.isdir(safe_path):
            return ToolFailure(f"目录 '{path}' 不存在或不是一个目录。")
        try:
            if recursive:
                shutil.rmtree(safe_path)
                return ToolResult(content=f"成功递归删除目录 '{path}' 及其所有内容。", success=True)
            else:
                if os.listdir(safe_path): # 检查目录是否为空
                    return ToolFailure(f"目录 '{path}' 非空。请使用 'recursive: true' 参数进行删除，或先清空目录。")
                os.rmdir(safe_path)
                return ToolResult(content=f"成功删除空目录 '{path}'。", success=True)
        except Exception as e:
            logger.error(f"FileOperatorTool delete_directory 异常: {e}", exc_info=True)
            return ToolFailure(error_message=f"删除目录 '{path}' 时发生错误: {e}", error_details=str(e))


    async def execute(self, command: str, path: str, **kwargs: Any) -> ToolResult | ToolFailure:
        logger.info(f"FileOperatorTool executing command: {command} for path: {path} with kwargs: {kwargs}")
        
        # 提取参数，同时处理不存在的键，给予默认值
        content = kwargs.get("content")
        start_line = kwargs.get("start_line")
        end_line = kwargs.get("end_line")
        encoding = kwargs.get("encoding", 'utf-8') # 默认值
        mode = kwargs.get("mode", 'w') # 默认值
        recursive_param = kwargs.get("recursive", False) # 默认值，避免与方法内的 recursive 混淆
        max_depth = kwargs.get("max_depth")
        parents = kwargs.get("parents", False) # 默认值

        if command == 'read_file':
            return await self.read_file(path=path, start_line=start_line, end_line=end_line, encoding=encoding)
        elif command == 'write_file':
            if content is None: return ToolFailure("命令 'write_file' 需要 'content' 参数。")
            return await self.write_file(path=path, content=content, mode=mode, encoding=encoding)
        elif command == 'list_directory':
            return await self.list_directory(path=path, recursive=recursive_param, max_depth=max_depth)
        elif command == 'create_file':
            return await self.create_file(path=path, content=content, encoding=encoding)
        elif command == 'create_directory':
            return await self.create_directory(path=path, parents=parents)
        elif command == 'delete_file':
            return await self.delete_file(path=path)
        elif command == 'delete_directory':
            return await self.delete_directory(path=path, recursive=recursive_param)
        else:
            return ToolFailure(f"未知命令 '{command}'。")