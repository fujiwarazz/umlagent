import os
import subprocess
# 假设 tools.base 存在并包含 BaseTool 类
# from tools.base import BaseTool

# 如果您的项目结构中 'tools' 是一个包，并且 'base.py' 在其中，
# 或者 'tools' 本身在 PYTHONPATH 下且 base.py 在其中。
# 根据您之前的讨论，您可能需要调整此导入以适应您的项目结构，例如：
# from .base import BaseTool # 如果 base.py 在同一目录
from tools.base import BaseTool # 沿用您示例中的导入方式，假设它能正确工作
import asyncio # 导入 asyncio 以使用 asyncio.to_thread

class GitHubRepoCloner(BaseTool):
    """
    一个用于使用 git clone 命令（通过SSH）克隆 GitHub 仓库到本地指定目录并返回本地路径的工具。
    确保您的机器已配置好 SSH 密钥并已添加到 GitHub 账户，以便通过 SSH 进行克隆。
    """
    name: str = "github_repo_cloner_ssh" # 可以稍微修改名称以区分，或保持原样
    description: str = """通过 SSH 克隆 GitHub 仓库到本地文件系统上的指定目录，并返回克隆后仓库的本地完整路径。
                        该工具接受 GitHub 仓库的名称（格式为 '所有者/仓库名'，例如 'shareAI-lab/open-Manus'）。
                        它将使用 'git clone' 命令（SSH方式）将仓库克隆到工具初始化时配置的本地基础目录的子目录中。
                        成功时，返回仓库在本地的完整文件路径；失败时，返回包含错误详情的字符串。如果出现了失败，可以重复使用这个工具来尝试克隆同一个仓库。
                        """
    parameters: dict = {
        "type": "object",
        "properties": {
            "repo_name": {
                "type": "string",
                "description": "(必填) GitHub 仓库的名称，格式为 '所有者/仓库名' (例如，'shareAI-lab/open-Manus')。",
            },
        },
        "required": ["repo_name"],
    }
    local_clone_base_dir: str

    def __init__(self, local_clone_base_dir: str, **kwargs):
        """
        初始化 GitHubRepoCloner 工具。

        Args:
            local_clone_base_dir (str): 所有仓库将被克隆到此目录下的基础路径。
            **kwargs: 传递给 BaseTool 基类的额外参数。
        """
        # 在 super().__init__ 之前设置实例属性，以便基类如果需要也可以访问
        super().__init__(local_clone_base_dir=local_clone_base_dir, **kwargs)
        
        
        try:
            os.makedirs(self.local_clone_base_dir, exist_ok=True)
        except OSError as e:
            print(f"警告：创建基础克隆目录 '{self.local_clone_base_dir}' 时发生错误: {e}")
        


    async def execute(self, repo_name: str) -> str:
        """
        执行 git clone 命令（通过SSH）克隆指定的 GitHub 仓库。

        Args:
            repo_name (str): GitHub 仓库的名称，格式为 '所有者/仓库名'。

        Returns:
            str: 成功时返回仓库在本地的完整文件路径字符串；
                 失败时返回包含错误详情的字符串（通常以“错误：”开头）。
        """
        try:
            os.makedirs(self.local_clone_base_dir, exist_ok=True)
        except OSError as e:
            print(f"警告：创建基础克隆目录 '{self.local_clone_base_dir}' 时发生错误: {e}")
            
        
        if '/' not in repo_name or repo_name.count('/') != 1:
            return f"错误：仓库名称格式无效。请使用 '所有者/仓库名' 格式 (例如，'shareAI-lab/open-Manus')。"

        repo_parts = repo_name.split('/')
        repo_short_name = repo_parts[-1]
        if not repo_short_name:
            return f"错误：仓库名称格式无效，仓库短名称为空。请使用 '所有者/仓库名' 格式。"

        target_dir = os.path.join(self.local_clone_base_dir, repo_short_name)

        if os.path.exists(target_dir) and os.path.isdir(target_dir) and os.listdir(target_dir):
            # 修改返回信息，提示可以使用已存在的目录路径
            abs_target_dir = os.path.abspath(target_dir)
            print(f"信息：目标目录 '{abs_target_dir}' 已存在且非空。将直接使用此路径。")
            return abs_target_dir
            # 或者，如果您坚持要求目录必须是新克隆的，则返回错误：
            # return f"错误：目标目录 '{target_dir}' 已存在且非空，可能仓库已被克隆。请先手动处理该目录。"


        # 构建 SSH Git 克隆 URL
        # HTTPS 格式: https://github.com/所有者/仓库名.git
        # SSH 格式:   git@github.com:所有者/仓库名.git
        repo_url_name = f"git@github.com:{repo_name}.git" # <--- 主要修改点在这里
        repo_url_name_https = f"https://github.com/{repo_name}.git"
        command = ["git", "clone", "--depth", "1", repo_url_name_https, target_dir]

        try:
            print(f"正在执行命令 (SSH): {' '.join(command)}")
            result = await asyncio.to_thread(
                subprocess.run,
                command,
                capture_output=True,
                text=True,
                check=False, # 我们将手动检查 returncode
                # shell=False # 默认即为 False，更安全
            )

            if result.returncode == 0:
                abs_target_dir = os.path.abspath(target_dir)
                print(f"仓库 '{repo_name}' 已成功通过 SSH 克隆到 '{abs_target_dir}'")
                return abs_target_dir
            else:
                # 记录更详细的错误日志，除了返回给用户
                error_message = (f"错误：通过 SSH 克隆仓库 '{repo_name}' 失败。\n"
                                 f"命令退出码: {result.returncode}\n"
                                 f"Git 标准错误输出:\n{result.stderr.strip()}\n"
                                 f"Git 标准输出:\n{result.stdout.strip()}")
                print(error_message) # 打印到控制台或日志文件
                return error_message

        except FileNotFoundError:
            return f"错误：未找到 'git' 命令。请确保 Git 已安装并配置在系统的 PATH 中。"
        except Exception as e:
            return f"错误：执行 Git 克隆时发生意外错误：{str(e)}"