# tools/ensure_init_py.py (或者您希望放置此工具的文件名)
import os
import asyncio
from typing import List # 确保导入 List

# 假设 tools.base 存在于您的 Python 路径中
# 如果 base.py 与此文件在同一目录，您可能使用 from .base import BaseTool
from tools.base import BaseTool

class EnsureInitPyTool(BaseTool):
   
    name: str = "ensure_init_py"
    description: str = """扫描指定根目录下的所有Python包（即包含至少一个.py文件的文件夹），
如果某个Python包内缺少 __init__.py 文件，则自动在该包内创建一个空的 __init__.py 文件。
该工具会递归地检查所有子目录。
成功时，返回已创建 __init__.py 文件的目录列表；如果无需创建或操作完成但未创建任何文件，则返回相应信息。
失败时，返回包含错误详情的字符串。
"""
    parameters: dict = {
        "type": "object",
        "properties": {
            "root_dir_path": {
                "type": "string",
                "description": "(必填) 需要扫描并确保 __init__.py 文件存在的根目录的绝对或相对路径。",
            },
        },
        "required": ["root_dir_path"],
    }

    def __init__(self, **kwargs):
        """
        初始化 EnsureInitPyTool 工具。

        Args:
            **kwargs: 传递给 BaseTool 基类的额外参数。
        """
        super().__init__(**kwargs)
        # 此工具目前不需要像 GitHubRepoCloner 那样有在初始化时必须配置的特定路径属性
        # 如果需要，可以在这里添加，例如：
        # self.default_comment_in_init_py: str = "# Automatically created"
        # super().__init__(default_comment_in_init_py=self.default_comment_in_init_py, **kwargs)


    def _ensure_init_py_sync(self, path_to_scan: str) -> List[str]:
        """
        同步执行 __init__.py 文件的检查和创建。
        此方法将在一个单独的线程中运行，以避免阻塞 asyncio 事件循环。
        """
        created_init_files: List[str] = []
        # 需要完全跳过检查的目录名称（不进入这些目录进行扫描）
        # 这些通常是环境目录、版本控制目录或构建产物目录
        skip_these_entirely_dirs = {
            ".git", "__pycache__", "venv", "env", ".env", "node_modules",
            "build", "dist", ".vscode", ".idea", "target", "out",
            # 根据需要添加更多，例如常见的测试数据或日志目录
            "test_data", "logs", "docs", ".pytest_cache", ".mypy_cache"
        }

        for dirpath, dirnames, filenames in os.walk(path_to_scan, topdown=True):
            # 修改 dirnames 列表以阻止 os.walk 进入我们想要跳过的目录
            dirnames[:] = [d for d in dirnames if d not in skip_these_entirely_dirs]

            is_python_package = False
            for f_name in filenames:
                if f_name.endswith(".py"):
                    is_python_package = True
                    break

            if is_python_package:
                init_py_path = os.path.join(dirpath, "__init__.py")
                if not os.path.exists(init_py_path):
                    # 再次确认 __init__.py 不是一个目录 (虽然不太可能)
                    if os.path.isdir(init_py_path):
                        print(f"警告：路径 '{init_py_path}' 已作为目录存在，无法创建 __init__.py 文件。")
                        continue
                    try:
                        with open(init_py_path, "w", encoding="utf-8") as f:
                            f.write("# Automatically created by EnsureInitPyTool\n")
                        created_init_files.append(os.path.abspath(init_py_path))
                        print(f"信息：已在 '{dirpath}' 创建 __init__.py")
                    except OSError as e:
                        # 处理文件创建时可能发生的错误 (例如权限问题)
                        print(f"警告：无法在 '{dirpath}' 创建 __init__.py 文件: {e}")
        return created_init_files

    async def execute(self, root_dir_path: str) -> str:
        """
        执行 __init__.py 文件的检查和创建过程。

        Args:
            root_dir_path (str): 需要扫描的根目录路径。

        Returns:
            str: 操作结果的描述。成功时列出已创建的 __init__.py 文件路径，
                 或说明无需创建；失败时返回错误信息。
        """
        abs_root_dir_path = os.path.abspath(root_dir_path)
        if not os.path.isdir(abs_root_dir_path):
            return f"错误：提供的路径 '{root_dir_path}' (解析为 '{abs_root_dir_path}') 不是一个有效的目录或不存在。"

        try:
            print(f"信息：开始扫描目录 '{abs_root_dir_path}' 以确保 __init__.py 文件存在...")
            # 在单独的线程中运行同步的文件I/O密集型操作
            created_files_list = await asyncio.to_thread(self._ensure_init_py_sync, abs_root_dir_path)

            if not created_files_list:
                return (f"在 '{abs_root_dir_path}' 中没有找到需要创建 __init__.py 的 Python 包目录，"
                        "或者所有相关的 Python 包都已包含 __init__.py 文件。")
            else:
                paths_str = "\n".join(f"- {f_path}" for f_path in created_files_list)
                return (f"成功在以下 {len(created_files_list)} 个目录中创建了 __init__.py 文件:\n"
                        f"{paths_str}")

        except Exception as e:
            # 捕获 _ensure_init_py_sync 中未处理的意外错误或 asyncio.to_thread 本身的错误
            return f"错误：执行 __init__.py 检查和创建时发生意外：{str(e)}"

# --- 以下为使用示例 (可选，用于测试工具) ---
async def main_test():
    # 创建一些测试目录和文件结构
    test_base_dir = "temp_test_ensure_init_py"
    if os.path.exists(test_base_dir):
        import shutil
        shutil.rmtree(test_base_dir)
    os.makedirs(test_base_dir, exist_ok=True)

    # 包1: 需要 __init__.py
    pkg1_path = os.path.join(test_base_dir, "package1")
    os.makedirs(pkg1_path, exist_ok=True)
    with open(os.path.join(pkg1_path, "module_a.py"), "w") as f:
        f.write("# module_a\n")

    # 包2: 已有 __init__.py
    pkg2_path = os.path.join(test_base_dir, "package2")
    os.makedirs(pkg2_path, exist_ok=True)
    with open(os.path.join(pkg2_path, "module_b.py"), "w") as f:
        f.write("# module_b\n")
    with open(os.path.join(pkg2_path, "__init__.py"), "w") as f:
        f.write("# package2 init\n")

    # 目录3: 非包 (无.py文件)
    non_pkg_path = os.path.join(test_base_dir, "non_package_dir")
    os.makedirs(non_pkg_path, exist_ok=True)
    with open(os.path.join(non_pkg_path, "data.txt"), "w") as f:
        f.write("some data\n")
        
    # 包3: 嵌套包，子包需要 __init__.py
    pkg3_path = os.path.join(test_base_dir, "package3")
    pkg3_sub_path = os.path.join(pkg3_path, "subpackage")
    os.makedirs(pkg3_sub_path, exist_ok=True)
    with open(os.path.join(pkg3_path, "outer_module.py"), "w") as f: # 使 package3 成为包
        f.write("# outer_module.py\n")
    with open(os.path.join(pkg3_sub_path, "inner_module.py"), "w") as f:
        f.write("# inner_module.py\n")
        
    # 跳过的目录
    venv_path = os.path.join(test_base_dir, "my_venv")
    os.makedirs(venv_path, exist_ok=True)
    with open(os.path.join(venv_path, "some_script.py"), "w") as f:
        f.write("# should be skipped\n")

    tool = EnsureInitPyTool()
    result = await tool.execute(root_dir_path=test_base_dir)
    print("\n--- 工具执行结果 ---")
    print(result)

    # 验证
    print("\n--- 验证文件系统 ---")
    print(f"package1/__init__.py exists: {os.path.exists(os.path.join(pkg1_path, '__init__.py'))}")
    print(f"package2/__init__.py still exists: {os.path.exists(os.path.join(pkg2_path, '__init__.py'))}")
    print(f"package3/subpackage/__init__.py exists: {os.path.exists(os.path.join(pkg3_sub_path, '__init__.py'))}")
    print(f"package3/__init__.py exists (should be created if outer_module.py makes it a package): {os.path.exists(os.path.join(pkg3_path, '__init__.py'))}")
    print(f"my_venv/__init__.py exists (should be False): {os.path.exists(os.path.join(venv_path, '__init__.py'))}")

    # 清理测试目录
    # import shutil
    # shutil.rmtree(test_base_dir)
    # print(f"\n清理完毕: 已删除 '{test_base_dir}'")

if __name__ == "__main__":
    # 要运行上面的测试主函数，您需要一个 asyncio 事件循环
    # asyncio.run(main_test())
    # 如果您在Jupyter Notebook或已有事件循环的环境中，可以直接 await main_test()
    # 为了简单起见，您可以将测试代码移到一个单独的测试文件中，并使用 pytest-asyncio
    print("EnsureInitPyTool 定义完毕。取消注释 asyncio.run(main_test()) 以进行测试。")
    # 例如:
    # loop = asyncio.get_event_loop()
    # if loop.is_running():
    #     # 在Jupyter Notebook等环境中处理
    #     task = loop.create_task(main_test())
    # else:
    #     asyncio.run(main_test())