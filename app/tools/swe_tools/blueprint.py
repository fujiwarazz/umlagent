import os
from typing import Optional, List, Dict, Any
from tools.base import BaseTool, ToolResult, ToolFailure # 假设的导入路径
from utils.logger import logger # 假设的导入路径

class BlueprintTool(BaseTool):
    name: str = "project_blueprint"
    description: str = """获取项目代码的结构和概览信息。
    用于快速了解项目的组织方式和主要入口点。
    命令 'get_project_structure'：需要 'project_path' 参数，可选 'max_depth' 参数，用于获取项目的文件和目录结构树。
    命令 'get_readme_content'：需要 'project_path' 参数，可选 'readme_filename' 参数，用于获取项目 README 文件的内容。"""
    strict: bool = True
    parameters: dict = {
        "type": "object",
        "properties": {
            "command": {
                "description": "要执行的命令。可用命令: `get_project_structure`, `get_readme_content`。",
                "enum": ["get_project_structure", "get_readme_content"],
                "type": "string"
            },
            "project_path": {
                "description": "目标项目的根路径。",
                "type": "string"
            },
            "max_depth": {
                "description": "（可选）对于 'get_project_structure'，限制目录树的显示深度。默认无限深。",
                "type": "integer",
                "minimum": 1
            },
            "readme_filename": {
                "description": "（可选）对于 'get_readme_content'，指定 README 文件的名称（例如 'README.md', 'README.rst'）。默认为 'README.md'。",
                "type": "string"
            }
        },
        "additionalProperties": False,
        "required": ["command", "project_path"]
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _generate_directory_tree(self, startpath: str, max_depth: Optional[int] = None) -> str:
        """生成目录树的字符串表示。"""
        tree_lines = []
        ignore_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', '.vscode', '.idea'} # 常见忽略目录

        def _generate_level(current_path: str, prefix: str = "", level: int = 0):
            if max_depth is not None and level >= max_depth:
                return

            try:
                entries = sorted(os.listdir(current_path))
            except OSError:
                tree_lines.append(f"{prefix}└── [无法访问的目录: {os.path.basename(current_path)}]")
                return

            pointers = ['├── '] * (len(entries) - 1) + ['└── ']

            for pointer, entry_name in zip(pointers, entries):
                full_entry_path = os.path.join(current_path, entry_name)
                is_dir = os.path.isdir(full_entry_path)

                if is_dir and entry_name in ignore_dirs:
                    continue # 跳过忽略的目录

                tree_lines.append(f"{prefix}{pointer}{entry_name}{'/' if is_dir else ''}")

                if is_dir:
                    extension = '│   ' if pointer == '├── ' else '    '
                    _generate_level(full_entry_path, prefix + extension, level + 1)

        tree_lines.append(f"{os.path.basename(os.path.abspath(startpath))}/")
        _generate_level(startpath, level=0)
        return "\n".join(tree_lines)

    async def get_project_structure(self, project_path: str, max_depth: Optional[int] = None) -> ToolResult | ToolFailure:
        logger.info(f"BlueprintTool: 'get_project_structure' for path: {project_path}, max_depth: {max_depth}")
        if not os.path.isdir(project_path):
            return ToolFailure(f"提供的项目路径 '{project_path}' 不是一个有效的目录或不存在。")
        try:
            structure = self._generate_directory_tree(project_path, max_depth)
            return ToolResult(content=f"项目 '{project_path}' 的文件结构:\n{structure}", success=True)
        except Exception as e:
            logger.error(f"BlueprintTool get_project_structure 异常: {e}", exc_info=True)
            return ToolFailure(error_message=f"获取项目结构时发生错误: {e}", error_details=str(e))

    async def get_readme_content(self, project_path: str, readme_filename: Optional[str] = None) -> ToolResult | ToolFailure:
        logger.info(f"BlueprintTool: 'get_readme_content' for path: {project_path}, readme_filename: {readme_filename}")
        if not os.path.isdir(project_path):
            return ToolFailure(f"提供的项目路径 '{project_path}' 不是一个有效的目录或不存在。")

        possible_readme_names = [readme_filename] if readme_filename else ['README.md', 'README.rst', 'README.txt', 'readme.md']
        readme_file_path = None

        for name in possible_readme_names:
            path_to_check = os.path.join(project_path, name)
            if os.path.isfile(path_to_check):
                readme_file_path = path_to_check
                break
        
        if not readme_file_path:
            return ToolResult(content=f"在项目 '{project_path}' 中未找到 README 文件 (尝试了: {', '.join(possible_readme_names)})。", success=True) # 成功但未找到

        try:
            with open(readme_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return ToolResult(content=f"项目 '{project_path}' 中 '{os.path.basename(readme_file_path)}' 的内容:\n{content}", success=True)
        except Exception as e:
            logger.error(f"BlueprintTool get_readme_content 异常: {e}", exc_info=True)
            return ToolFailure(error_message=f"读取 README 文件 '{readme_file_path}' 时发生错误: {e}", error_details=str(e))

    async def execute(self, command: str, project_path: str, max_depth: Optional[int] = None, readme_filename: Optional[str] = None) -> ToolResult | ToolFailure:
        logger.info(f"BlueprintTool executing command: {command} for project_path: {project_path}")
        if command == 'get_project_structure':
            return await self.get_project_structure(project_path=project_path, max_depth=max_depth)
        elif command == 'get_readme_content':
            return await self.get_readme_content(project_path=project_path, readme_filename=readme_filename)
        else:
            return ToolFailure(f"未知命令 '{command}'。可用命令: 'get_project_structure', 'get_readme_content'。")