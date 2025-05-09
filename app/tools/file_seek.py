import os
import aiofiles

from tools.base import BaseTool


class FileSeeker(BaseTool):
    """
    在本地文件或目录中的文件内递归搜索指定内容。报告匹配的文件路径和行号。
    """
    name: str = "file_seeker"

    description: str = """Search for specific content within a local file or recursively within files in a directory.
        Use this tool when you need to find where a certain string of text or code appears
        within one or more files on the local filesystem.
        The tool accepts a path (to a file or directory) and the content to search for.
        If the path is a directory, it will traverse all files within it.
        It returns a list of files where the content was found, along with the line numbers
        of the occurrences within those files.
        """
    parameters: dict = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "(required) The file path or directory path to search within.",
            },
            "content": {
                "type": "string",
                "description": "(required) The specific content string to search for.",
            },
        },
        "required": ["path", "content"],
    }

    async def _search_file(self, file_path: str, search_content: str) -> list[tuple[str, int]]:
        """
        异步搜索单个文件中的指定内容。

        Args:
            file_path (str): 要搜索的文件路径。
            search_content (str): 要搜索的内容。

        Returns:
            list[tuple[str, int]]: 匹配的列表，每个元组包含 (行内容, 行号)。
        """
        matches = []
        # 跳过目录、不存在的路径或特殊文件
        if not os.path.isfile(file_path):
            return matches

        # 通过文件名约定跳过常见的隐藏文件/目录和潜在的二进制文件
        # 对于不同的用例可能需要更健壮的检查
        filename = os.path.basename(file_path)
        if filename.startswith('.') or '~' in filename or '#' in filename:
            return matches  # 基本跳过隐藏文件/临时文件/备份文件

        try:
            async with aiofiles.open(file_path, mode="r", encoding="utf-8", errors="ignore") as file:
                line_number = 0
                async for line in file:
                    line_number += 1
                    if search_content in line:
                        matches.append((line.strip(), line_number))  # 存储去除空白的行内容和行号
        except Exception as e:
            # 捕获文件读取期间的错误（例如，权限错误，解码问题）
            # print(f"无法读取或搜索文件 {file_path}: {e}") # 可选：记录错误
            pass  # 在遍历期间静默跳过导致错误的文件

        return matches

    async def execute(self, path: str, content: str) -> str:
        """
        根据提供的路径和内容执行文件搜索。

        Args:
            path (str): 要搜索的文件或目录路径。
            content (str): 要搜索的内容字符串。

        Returns:
            str: 格式化字符串，列出找到内容的 文件和行号，或指示没有匹配或发生错误的消息。
        """
        search_content = content  # 在内部使用不同的变量名
        results = {}  # 存储结果的字典：{文件路径: [(行内容, 行号), ...]}
        output_lines = []  # 用于构建最终输出字符串的列表

        try:
            if not os.path.exists(path):
                return f"错误：未找到路径：{path}"

            if os.path.isfile(path):
                # 搜索单个文件
                matches = await self._search_file(path, search_content)
                if matches:
                    results[path] = matches

            elif os.path.isdir(path):
                # 遍历目录并搜索文件
                # os.walk 不是异步的，但其中的文件读取是异步的。
                # 对于真正的异步遍历，您需要使用不同的方法，例如 aiofiles.os.listdir 并手动管理递归，或使用库。
                # 这里使用 os.walk 是为了简化，因为文件 I/O 通常是主要瓶颈。
                for dirpath, dirnames, filenames in os.walk(path):
                    # 原地修改 dirnames 以跳过以 '.' 开头的子目录
                    dirnames[:] = [d for d in dirnames if not d.startswith('.')]

                    for filename in filenames:
                        full_file_path = os.path.join(dirpath, filename)
                        # _search_file 函数已经处理了按名称跳过隐藏文件

                        matches = await self._search_file(full_file_path, search_content)
                        if matches:
                            results[full_file_path] = matches
            else:
                return f"错误：路径既不是有效的文件也不是目录：{path}"

        except Exception as e:
            # 捕获 os.walk 或初始路径检查期间的意外错误
            return f"搜索期间发生意外错误：{str(e)}"

        # 将结果格式化为可读字符串
        if not results:
            return f"在指定路径中未找到内容 '{search_content}'。"
        else:
            output_lines.append(f"在路径 '{path}' 中搜索 '{search_content}' 的结果：\n")
            for file_path, matches in results.items():
                output_lines.append(f"文件：{file_path}")
                for line_content, line_number in matches:
                    # 缩进匹配行以便清晰显示
                    output_lines.append(f"  第 {line_number} 行: {line_content}")
                output_lines.append("")  # 在文件之间添加空行以便提高可读性

            # 将所有行连接成一个字符串
            return "\n".join(output_lines).strip()  # .strip() 移除末尾的换行符