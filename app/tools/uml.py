# Try to import language-specific parsers
from tools.base import BaseTool,ToolResult
from utils.exceptions import ToolError
from pathlib import Path
import ast
import os
from pathlib import Path
from typing import Dict, List, Literal, Optional, Any, Set, Tuple
try:
    import javalang
except ImportError:
    javalang = None # Will be checked later

try:
    from clang import cindex
    # You might need to specify the libclang path if it's not found automatically
    # try:
    #     cindex.Config.set_library_file('/usr/lib/x86_64-linux-gnu/libclang-10.so') # Example path
    # except cindex.LibclangError:
    #     print("Warning: libclang path not set or found. C++ parsing might fail.")
    #     cindex = None
except ImportError:
    cindex = None

from fastapi import WebSocket
_CODE_TO_UML_TOOL_DESCRIPTION = """
A tool to analyze a local code repository containing Python, Java, or C++ code
and generate a unified UML class diagram.
The diagram visualizes classes, interfaces, structs, their attributes, methods,
and inheritance/implementation relationships.
The output is saved as a PNG image file.
You MUST ensure Graphviz is installed and in the system PATH.
For Java analysis, the 'javalang' Python library is required.
For C++ analysis, the 'libclang' Python library and Clang system libraries are required.
"""

LANGUAGE_EXTENSIONS = {
    "python": {".py"},
    "java": {".java"},
    "cpp": {".cpp", ".hpp", ".h", ".cxx", ".hxx", ".cc", ".hh"},
}

class CodeToUMLTool(BaseTool):
    name: str = "code_to_uml_generator_multilang"
    description: str = _CODE_TO_UML_TOOL_DESCRIPTION
    parameters: dict = {
        "type": "object",
        "properties": {
            "repo_path": {
                "description": "The absolute or relative path to the local code repository to analyze.",
                "type": "string",
            },
            "output_png_path": {
                "description": "The full path (including filename, e.g., 'diagram.png') where the generated UML PNG image will be saved.",
                "type": "string",
            },
            "target_languages": {
                "description": "Optional. A list of languages to specifically parse (e.g., ['python', 'java']). If empty or not provided, the tool will attempt to auto-detect and parse all supported languages found.",
                "type": "array",
                "items": {"type": "string", "enum": ["python", "java", "cpp"]},
                "default": [], # Auto-detect all
            },
            "cpp_include_paths": {
                "description": "Optional. A list of include paths for C++ parsing. E.g. ['/usr/include', 'libs/mycustomlib/include']",
                "type": "array",
                "items": {"type": "string"},
                "default": [],
            },
            "cpp_compiler_args": {
                "description": "Optional. A list of additional compiler arguments for C++ parsing. E.g. ['-std=c++17', '-DMY_MACRO']",
                "type": "array",
                "items": {"type": "string"},
                "default": ["-std=c++11"], # A basic default
            },
            "exclude_folders": {
                "description": "A list of folder names to exclude from parsing (e.g., ['venv', '.git', '__pycache__']).",
                "type": "array",
                "items": {"type": "string"},
                "default": ["venv", ".git", "__pycache__", "docs", "tests", "test", "build", "target", "out"],
            },
            "exclude_files": {
                "description": "A list of file names to exclude from parsing (e.g., ['setup.py', 'conftest.py']).",
                "type": "array",
                "items": {"type": "string"},
                "default": ["setup.py", "conftest.py"],
            },
            "include_attributes": {
                "description": "Whether to include class attributes/fields in the diagram.",
                "type": "boolean",
                "default": True,
            },
            "include_methods": {
                "description": "Whether to include class methods (and their parameters) in the diagram.",
                "type": "boolean",
                "default": True,
            },
             "max_depth": {
                "description": "Maximum depth of subdirectories to scan. 0 means only the root directory, -1 means unlimited.",
                "type": "integer",
                "default": -1,
            }
        },
        "required": ["repo_path", "output_png_path"],
        "additionalProperties": False,
    }
    
    websocket: WebSocket = None


    def __init__(self,websocket:WebSocket,**kwargs):
        super().__init__(websocket = websocket,**kwargs)
        
        self._parsed_elements: Dict[str, Dict[str, Any]] = {} # Unified storage
        self._ensure_dependencies()

    def _ensure_dependencies(self):
        # Graphviz Python library is assumed to be a core dependency if this tool is loaded.
        # System-level Graphviz 'dot' is checked during diagram generation.
        # Checks for javalang and libclang are done before their respective parsing calls.
        pass

    def escape_dot_field_text(text: str) -> str:
        """Escapes characters in text to be safely used in a DOT plain string label field."""
        if not text:
            return ""
        # 转义顺序很重要，先转义反斜杠本身
        text = text.replace('\\', '\\\\')
        text = text.replace('{', '\\{')
        text = text.replace('}', '\\}')
        text = text.replace('<', '\\<')
        text = text.replace('>', '\\>')
        text = text.replace('|', '\\|')
        text = text.replace('[', '\\[') # 对于类型提示中的方括号
        text = text.replace(']', '\\]') # 对于类型提示中的方括号
        text = text.replace('"', '\\"') # 如果标签是用双引号括起来的
        # \n 和 \l 是 DOT 的换行符，它们应该以 "\\n" 和 "\\l" 的形式存在于Python字符串中，
        # 以便DOT引擎能正确解析它们。此函数不应转义它们（即不应将 \n 转为 \\n）。
        # text.replace('\n', '\\n') # 这是不需要的，因为我们是用 "\\n" 来构造字符串的
        return text


    def _detect_languages_and_files(
        self,
        repo_path: Path,
        exclude_folders: List[str],
        exclude_files: List[str],
        max_depth: int
    ) -> Dict[str, List[Path]]:
        detected_files_by_lang: Dict[str, List[Path]] = {"python": [], "java": [], "cpp": []}
        
        for root_str, dirs, files in os.walk(str(repo_path), topdown=True):
            root = Path(root_str)
            current_depth = len(root.relative_to(repo_path).parts)
            if max_depth != -1 and current_depth > max_depth:
                dirs[:] = []
                continue

            dirs[:] = [d for d in dirs if d not in exclude_folders and not d.startswith('.')]
            
            for file_name in files:
                if file_name in exclude_files or file_name.startswith('.'):
                    continue
                
                file_path = root / file_name
                ext = file_path.suffix.lower()
                
                for lang, exts in LANGUAGE_EXTENSIONS.items():
                    if ext in exts:
                        detected_files_by_lang[lang].append(file_path)
                        break
        return detected_files_by_lang

    # --- Python Parsing (largely similar to previous, simplified here for brevity) ---
    def _parse_python_method_args(self, method_node: ast.FunctionDef) -> str:
        # (Implementation from previous response)
        args = []
        for arg in method_node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                try: arg_str += f": {ast.unparse(arg.annotation).strip()}"
                except AttributeError: arg_str += f": {ast.dump(arg.annotation)}" # Fallback
            args.append(arg_str)
        if method_node.args.vararg: args.append("*" + method_node.args.vararg.arg)
        if method_node.args.kwarg: args.append("**" + method_node.args.kwarg.arg)
        return ", ".join(args)


    def _parse_python_file(self, file_path: Path):
        try:
            source_code = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source_code, filename=str(file_path))
        except Exception: # Broad except for parsing errors
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_name = node.name
                if class_name not in self._parsed_elements:
                    self._parsed_elements[class_name] = {
                        "attributes": set(), "methods": set(), "bases": [],
                        "implements": [], "stereotype": "<<class>>",
                        "module": file_path.stem, "language": "python"
                    }
                
                for base_node in node.bases:
                    try: self._parsed_elements[class_name]["bases"].append(ast.unparse(base_node).strip())
                    except AttributeError: self._parsed_elements[class_name]["bases"].append(ast.dump(base_node))


                for item in node.body:
                    # Attribute parsing (ast.Assign, ast.AnnAssign)
                    if isinstance(item, (ast.Assign, ast.AnnAssign)):
                        targets = item.targets if isinstance(item, ast.Assign) else [item.target]
                        for target in targets:
                            if isinstance(target, ast.Name):
                                attr_name = target.id
                                type_hint = ""
                                if isinstance(item, ast.AnnAssign) and item.annotation:
                                    try: type_hint = f": {ast.unparse(item.annotation).strip()}"
                                    except AttributeError: type_hint = f": {ast.dump(item.annotation)}"
                                self._parsed_elements[class_name]["attributes"].add(f"{attr_name}{type_hint}")
                    # Method parsing (ast.FunctionDef)
                    elif isinstance(item, ast.FunctionDef):
                        method_name = item.name
                        params = self._parse_python_method_args(item)
                        return_annotation = ""
                        if item.returns:
                            try: return_annotation = f" -> {ast.unparse(item.returns).strip()}"
                            except AttributeError: return_annotation = f" -> {ast.dump(item.returns)}"
                        self._parsed_elements[class_name]["methods"].add(f"{method_name}({params}){return_annotation}")
                        # Basic self.attr in __init__
                        if method_name == "__init__":
                            for stmt in item.body:
                                if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                                    assign_targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                                    for assign_target in assign_targets:
                                        if isinstance(assign_target, ast.Attribute) and \
                                           isinstance(assign_target.value, ast.Name) and \
                                           assign_target.value.id == 'self':
                                            attr_name = assign_target.attr
                                            type_h = ""
                                            if isinstance(stmt, ast.AnnAssign) and stmt.annotation:
                                                try: type_h = f": {ast.unparse(stmt.annotation).strip()}"
                                                except AttributeError: type_h = f": {ast.dump(stmt.annotation)}"
                                            self._parsed_elements[class_name]["attributes"].add(f"{assign_target.attr}{type_h}")
    def _format_java_type(self, type_node) -> str:
        if not type_node: return ""
        name = type_node.name
        sub_type = f"<{self._format_java_type(type_node.sub_type)}>" if type_node.sub_type else ""
        dimensions = "[]" * len(type_node.dimensions) if type_node.dimensions else ""
        return f"{name}{sub_type}{dimensions}"

    def _parse_java_file(self, file_path: Path):
        if not javalang:
            # print("Warning: javalang library not available. Skipping Java parsing.")
            return
        try:
            source_code = file_path.read_text(encoding="utf-8")
            tree = javalang.parse.parse(source_code)
        except Exception as e:
            # print(f"Warning: Could not parse Java file {file_path}: {e}")
            return

        for path, node in tree: # tree itself is a CompilationUnit
            element_name = None
            stereotype = ""
            bases = []
            implements = []

            if isinstance(node, javalang.tree.ClassDeclaration):
                element_name = node.name
                stereotype = "<<class>>"
                if node.extends:
                    bases.append(self._format_java_type(node.extends))
                if node.implements:
                    for impl in node.implements:
                        implements.append(self._format_java_type(impl))
            elif isinstance(node, javalang.tree.InterfaceDeclaration):
                element_name = node.name
                stereotype = "<<interface>>"
                if node.extends: # Interfaces can extend other interfaces
                    for ext in node.extends:
                        implements.append(self._format_java_type(ext)) # Represent as "implements" for diagram
            
            if element_name:
                if element_name not in self._parsed_elements:
                    self._parsed_elements[element_name] = {
                        "attributes": set(), "methods": set(), "bases": bases,
                        "implements": implements, "stereotype": stereotype,
                        "module": file_path.stem, "language": "java"
                    }
                else: # Merge if already exists (e.g. partial class, though not standard Java)
                    self._parsed_elements[element_name]["bases"].extend(b for b in bases if b not in self._parsed_elements[element_name]["bases"])
                    self._parsed_elements[element_name]["implements"].extend(i for i in implements if i not in self._parsed_elements[element_name]["implements"])


                # Fields (Attributes) and Methods
                for member in node.body:
                    if isinstance(member, javalang.tree.FieldDeclaration):
                        field_type = self._format_java_type(member.type)
                        for declarator in member.declarators:
                            self._parsed_elements[element_name]["attributes"].add(f"{declarator.name}: {field_type}")
                    elif isinstance(member, (javalang.tree.MethodDeclaration, javalang.tree.ConstructorDeclaration)):
                        method_name = member.name if isinstance(member, javalang.tree.MethodDeclaration) else element_name # Constructor name
                        params = []
                        if member.parameters:
                            for param in member.parameters:
                                param_type = self._format_java_type(param.type)
                                params.append(f"{param.name}: {param_type}")
                        param_str = ", ".join(params)
                        return_type = ""
                        if isinstance(member, javalang.tree.MethodDeclaration) and member.return_type:
                            return_type = f" -> {self._format_java_type(member.return_type)}"
                        
                        self._parsed_elements[element_name]["methods"].add(f"{method_name}({param_str}){return_type}")

    # --- C++ Parsing ---
    def _get_clang_type_name(self, ctype) -> str:
        # This can be complex for templates, auto, etc. Simplified.
        return ctype.spelling

    def _parse_cpp_file(self, file_path: Path, clang_idx, compiler_args: List[str]):
        if not cindex:
            # print("Warning: libclang library not available. Skipping C++ parsing.")
            return
        try:
            # Add file's directory to include paths for local includes, if not already covered by user
            current_compiler_args = compiler_args + [f"-I{file_path.parent.resolve()}"]
            tu = clang_idx.parse(str(file_path), args=current_compiler_args) # Translation Unit
            if not tu:
                # print(f"Warning: Clang could not parse C++ file: {file_path}")
                return
            
            # Log diagnostics
            # for diag in tu.diagnostics:
            #     if diag.severity >= cindex.Diagnostic.Warning:
            #         print(f"Clang diag ({file_path.name}): {diag.spelling}")


        except Exception as e:
            # print(f"Warning: Could not parse C++ file {file_path} with Clang: {e}")
            return

        for node in tu.cursor.walk_preorder():
            element_name = None
            stereotype = ""
            bases = [] # For C++, inheritance is primary

            if node.kind == cindex.CursorKind.CLASS_DECL:
                element_name = node.spelling
                stereotype = "<<class>>"
            elif node.kind == cindex.CursorKind.STRUCT_DECL:
                element_name = node.spelling
                stereotype = "<<struct>>"
            # Note: C++ doesn't have 'interface' keyword like Java. Abstract classes serve similar role.
            
            if element_name and node.is_definition(): # Only process definitions
                # Clang often finds declarations and definitions. We want the one with body.
                # Or, if it's a class from an included header, it might not be a "definition" in *this* TU
                # but we still want to capture it. This logic might need refinement.
                # For now, take the first encountered name.
                
                # Qualified name can be useful for namespaces: element_name = node.displayname
                # For simplicity, using node.spelling.

                if element_name not in self._parsed_elements: # Or if current is definition and previous was not
                    self._parsed_elements[element_name] = {
                        "attributes": set(), "methods": set(), "bases": [],
                        "implements": [], "stereotype": stereotype, # C++ uses inheritance for "implements"
                        "module": file_path.stem, "language": "cpp"
                    }
                
                current_el = self._parsed_elements[element_name]

                # Get base classes
                for child in node.get_children():
                    if child.kind == cindex.CursorKind.CXX_BASE_SPECIFIER:
                        base_name = self._get_clang_type_name(child.type)
                        if base_name not in current_el["bases"]:
                             current_el["bases"].append(base_name)
                
                # Fields (Attributes) and Methods
                for member in node.get_children(): # Iterate direct children for members
                    if member.kind == cindex.CursorKind.FIELD_DECL:
                        attr_name = member.spelling
                        attr_type = self._get_clang_type_name(member.type)
                        current_el["attributes"].add(f"{attr_name}: {attr_type}")
                    elif member.kind in [cindex.CursorKind.CXX_METHOD, cindex.CursorKind.CONSTRUCTOR, cindex.CursorKind.DESTRUCTOR]:
                        method_name = member.spelling
                        params = []
                        for arg_node in member.get_arguments(): # member.get_arguments() only on FunctionDecl based kinds
                             params.append(f"{arg_node.spelling}: {self._get_clang_type_name(arg_node.type)}")
                        param_str = ", ".join(params)
                        
                        return_type = ""
                        if member.kind != cindex.CursorKind.CONSTRUCTOR and member.kind != cindex.CursorKind.DESTRUCTOR:
                            return_type = f" -> {self._get_clang_type_name(member.result_type)}"
                        
                        # Distinguish const methods, static, etc. (simplifying for now)
                        # if member.is_static_method(): method_name = f"{method_name} {{static}}"
                        # if member.is_const_method(): method_name = f"{method_name} {{const}}"
                        current_el["methods"].add(f"{method_name}({param_str}){return_type}")

    def _generate_textual_description(self, include_attributes: bool, include_methods: bool) -> str:
        """根据解析出的元素生成UML图的文本描述 (Markdown格式)"""
        if not self._parsed_elements:
            return "未找到可描述的元素。\n"

        description_parts = ["# UML 图表文本描述\n\n"] # Markdown 主标题

        # 按元素名称排序以确保输出一致性
        sorted_element_names = sorted(self._parsed_elements.keys())

        for el_name in sorted_element_names:
            details = self._parsed_elements[el_name]
            # 清理原型字符串，使其更友好
            stereotype_text = details.get('stereotype', '元素') # 默认为'元素'
            if stereotype_text.startswith("<<") and stereotype_text.endswith(">>"):
                stereotype_text = stereotype_text[2:-2].capitalize() # 例如 "Class", "Interface"
            else:
                stereotype_text = stereotype_text.capitalize()

            description_parts.append(f"## {stereotype_text}: `{el_name}`\n\n") # 二级标题：原型: `元素名`
            description_parts.append(f"- **语言 (Language):** {details.get('language', 'N/A')}\n")
            description_parts.append(f"- **模块/文件 (Module/File):** `{details.get('module', 'N/A')}`\n")

            bases = details.get('bases', [])
            if bases:
                description_parts.append(f"\n### 继承关系 (Inheritance)\n")
                description_parts.append(f"- 继承自 (Inherits from): {', '.join(f'`{b}`' for b in bases)}\n")

            implements = details.get('implements', [])
            if implements:
                description_parts.append(f"\n### 实现关系 (Implements)\n")
                description_parts.append(f"- 实现接口 (Implements): {', '.join(f'`{i}`' for i in implements)}\n")

            # 属性列表 (self._parsed_elements[el_name]["attributes"] 应已排序)
            attributes = details.get("attributes", [])
            if include_attributes and attributes:
                description_parts.append(f"\n### 属性 (Attributes)\n")
                for attr in attributes: # 假设这里的 attributes 已经是排序好的列表
                    description_parts.append(f"- `{attr}`\n")
            
            # 方法列表 (self._parsed_elements[el_name]["methods"] 应已排序)
            methods = details.get("methods", [])
            if include_methods and methods:
                description_parts.append(f"\n### 方法 (Methods)\n")
                for method in methods: # 假设这里的 methods 已经是排序好的列表
                    description_parts.append(f"- `{method}`\n")
            
            description_parts.append("\n---\n\n") # 每个元素后的分隔符

        return "".join(description_parts)
    # --- Diagram Generation (Updated) ---
    def _generate_uml_diagram(self, output_png_path: Path, include_attributes: bool, include_methods: bool) -> str:
        try:
            import graphviz
        except ImportError:
            # ToolError 应该在您的项目中定义
            raise ToolError("Graphviz Python library not found. Please run 'pip install graphviz'.")

        dot = graphviz.Digraph(comment='Multi-lang Class Diagram', format='png')
        dot.attr('node', shape='record', fontname='Helvetica', fontsize='10')
        dot.attr('edge', fontname='Helvetica', fontsize='9')
        dot.attr(rankdir='TB')

        language_colors = {
            "python": "lightblue",
            "java": "lightcoral",
            "cpp": "lightgreen",
            "default": "lightgrey"  # Fallback color
        }

        def escape_dot_field_text(text: str) -> str:
            """Escapes characters in text to be safely used in a DOT plain string label field."""
            if not text:
                return ""
            # 转义顺序：先转义反斜杠本身，再转义其他特殊字符
            text = text.replace('\\', '\\\\')
            text = text.replace('{', '\\{')
            text = text.replace('}', '\\}')
            text = text.replace('<', '\\<')
            text = text.replace('>', '\\>')
            text = text.replace('|', '\\|')
            text = text.replace('[', '\\[')
            text = text.replace(']', '\\]')
            text = text.replace('"', '\\"') # 如果标签是用双引号括起来的
            # 注意: \n 和 \l 是 DOT 用于换行的控制序列。
            # 它们在 Python 字符串中应表示为 "\\n" 和 "\\l"，
            # 这样它们在写入 DOT 文件时就是 \n 和 \l。
            # 此函数不应修改已经正确用于 DOT 的 \n 或 \l。
            return text

        for el_name, details in self._parsed_elements.items():
            # 1. 准备各个部分的内容 (并进行转义)
            stereotype_display = escape_dot_field_text(details.get('stereotype', ''))
            # el_name 用于节点ID和端口名时，通常不应包含需要转义的特殊字符。
            # 但用于显示在标签内的文本时，如果可能包含特殊字符，则需要转义。
            el_name_for_text_display = escape_dot_field_text(el_name)

            # 第一个隔间的内容：原型和类名
            title_compartment_text_content = el_name_for_text_display
            if stereotype_display: # 只有当原型存在时才添加
                title_compartment_text_content = f"{stereotype_display}\\n{el_name_for_text_display}"
            
            # 第一个隔间完整定义 (包含端口名 <el_name>)
            # 端口名 <el_name> 中的尖括号是结构性的，不应被 escape_dot_field_text 转义
            compartment1_full_text = f"<{el_name}> {title_compartment_text_content}"

            # 第二个隔间：属性
            attributes_list_escaped = []
            if include_attributes and details.get("attributes"):
                for attr in sorted(list(details["attributes"])):
                    attributes_list_escaped.append(escape_dot_field_text(f"+ {attr}"))
            
            compartment2_text_content = "\\l".join(attributes_list_escaped)
            if attributes_list_escaped: # 只有当有属性时才添加末尾的左对齐换行符
                compartment2_text_content += "\\l"

            # 第三个隔间：方法
            methods_list_escaped = []
            if include_methods and details.get("methods"):
                for method in sorted(list(details["methods"])):
                    methods_list_escaped.append(escape_dot_field_text(f"+ {method}"))

            compartment3_text_content = "\\l".join(methods_list_escaped)
            if methods_list_escaped: # 只有当有方法时才添加末尾的左对齐换行符
                compartment3_text_content += "\\l"

            # 2. 根据包含选项构建最终的标签字符串
            # 记录类型的标签结构为 "{ field1 | field2 | field3 }"
            # 即使 field2 或 field3 为空，也需要保留分隔符 | 以维持结构
            
            current_label_fields = [compartment1_full_text] # 第一个字段（标题和端口）总是存在

            if include_attributes:
                current_label_fields.append(compartment2_text_content)
            elif include_methods: 
                # 如果不包含属性但包含方法，我们需要一个空字符串作为属性字段的占位符
                current_label_fields.append("") 
            
            if include_methods:
                current_label_fields.append(compartment3_text_content)
            
            # 只有当多于一个字段时才用 " | " 连接，否则直接使用大括号包围单个字段
            if len(current_label_fields) == 1:
                label = f"{{ {current_label_fields[0]} }}"
            else:
                label = "{ " + " | ".join(current_label_fields) + " }"
            
            node_color = language_colors.get(details.get("language", "default"), language_colors["default"])
            dot.node(el_name, label=label, style="filled", fillcolor=node_color)

            # 3. 添加关系 (边)
            # 继承关系
            for base_name in details.get("bases", []):
                if base_name != el_name and base_name in self._parsed_elements: # 避免自引用和指向未解析的元素
                     dot.edge(base_name, el_name, arrowhead='empty', style='solid')
            
            # 实现关系 (例如Java接口)
            for impl_name in details.get("implements", []):
                if impl_name != el_name and impl_name in self._parsed_elements:
                    # 检查被实现的元素是否为接口，以决定线的样式
                    is_interface_impl = self._parsed_elements.get(impl_name, {}).get("stereotype", "").lower().replace("<<", "").replace(">>","") == "interface"
                    line_style = "dashed" if is_interface_impl else "solid" # 如果实现的是类（不常见），则用实线
                    dot.edge(impl_name, el_name, arrowhead='empty', style=line_style)

        # 4. 渲染并保存图像
        try:
            # 确保输出目录存在
            output_png_path.parent.mkdir(parents=True, exist_ok=True)
            
            # graphviz库的render方法会生成 directory/filename.format
            # 例如 "path/to/diagram.png" (如果stem是"diagram", parent是"path/to")
            rendered_file = dot.render(filename=output_png_path.stem, directory=output_png_path.parent, cleanup=True)
            
            # dot.render 可能返回添加了 .png 的路径，或原始路径。
            # 构建期望的最终路径进行确认。
            final_path = output_png_path.parent / (output_png_path.stem + ".png")
            if not final_path.exists() and Path(rendered_file).exists(): # 如果期望路径不存在但render返回的路径存在
                final_path = Path(rendered_file)
            elif not final_path.exists() and output_png_path.exists(): # 如果期望路径不存在但原始output_png_path存在
                 final_path = output_png_path


            return str(final_path.resolve())
        except graphviz.backend.execute.ExecutableNotFound:
            raise ToolError(
                "Graphviz 'dot' executable not found. Please install Graphviz (from graphviz.org/download/) "
                "and ensure it is in your system's PATH."
            )
        except Exception as e:
            raise ToolError(f"Failed to generate or save UML diagram: {e}")


    async def execute(
        self,
        *,
        repo_path: str,
        output_png_path: str,
        target_languages: Optional[List[str]] = None,
        cpp_include_paths: Optional[List[str]] = None,
        cpp_compiler_args: Optional[List[str]] = None,
        exclude_folders: Optional[List[str]] = None,
        exclude_files: Optional[List[str]] = None,
        include_attributes: bool = True, # 参数传递给描述和图表生成
        include_methods: bool = True,    # 参数传递给描述和图表生成
        max_depth: int = -1,
        **kwargs,
    ) -> ToolResult:
        self._parsed_elements = {} # 重置

        # ... (参数默认值设置和路径验证逻辑，与之前版本相同) ...
        schema_props = self.parameters["properties"]
        if target_languages is None or not target_languages: target_languages = schema_props["target_languages"]["default"]
        if cpp_include_paths is None: cpp_include_paths = schema_props["cpp_include_paths"]["default"]
        if cpp_compiler_args is None: cpp_compiler_args = schema_props["cpp_compiler_args"]["default"]
        if exclude_folders is None: exclude_folders = schema_props["exclude_folders"]["default"]
        if exclude_files is None: exclude_files = schema_props["exclude_files"]["default"]

        repo_p = Path(repo_path)
        output_p = Path(output_png_path)

        if not repo_p.exists() or not repo_p.is_dir():
            raise ToolError(f"仓库路径 '{repo_path}' 不存在或不是一个目录。")
        if not output_p.name.lower().endswith(".png"):
            raise ToolError(f"输出路径 '{output_png_path}' 必须是一个 .png 文件。")
        # ... (语言文件检测逻辑 _detect_languages_and_files 调用，与之前版本相同) ...
        detected_files_by_lang = self._detect_languages_and_files(repo_p, exclude_folders, exclude_files, max_depth)
        
        processed_langs = []
        langs_to_parse = target_languages
        if not langs_to_parse: 
            langs_to_parse = [lang for lang, files in detected_files_by_lang.items() if files]
        
        scanned_files_count = 0

        # ... (各语言文件的解析循环，调用 _parse_python_file, _parse_java_file, _parse_cpp_file) ...
        # 例如 Python部分:
        if "python" in langs_to_parse and detected_files_by_lang["python"]:
            for py_file in detected_files_by_lang["python"]:
                self._parse_python_file(py_file) # 此方法填充 self._parsed_elements
                scanned_files_count +=1
            processed_langs.append(f"Python ({len(detected_files_by_lang['python'])} 文件)")
        # Java 和 C++ 解析部分也类似...
        if "java" in langs_to_parse and detected_files_by_lang["java"]:
            if not javalang: # javalang 在 __init__ 或类级别检查
                return ToolResult(error="Java 解析请求，但 'javalang' 库未安装。请安装它。")
            for java_file in detected_files_by_lang["java"]:
                self._parse_java_file(java_file)
                scanned_files_count +=1
            processed_langs.append(f"Java ({len(detected_files_by_lang['java'])} 文件)")

        if "cpp" in langs_to_parse and detected_files_by_lang["cpp"]:
            if not cindex: # cindex 在 __init__ 或类级别检查
                return ToolResult(error="C++ 解析请求，但 'libclang' 库不可用或未配置。请安装它和 Clang 系统库。")
            clang_idx = cindex.Index.create()
            final_cpp_compiler_args = cpp_compiler_args[:] # 复制列表
            for path_str in cpp_include_paths:
                final_cpp_compiler_args.append(f"-I{path_str}")
            for cpp_file in detected_files_by_lang["cpp"]:
                self._parse_cpp_file(cpp_file, clang_idx, final_cpp_compiler_args)
                scanned_files_count +=1
            processed_langs.append(f"C++ ({len(detected_files_by_lang['cpp'])} 文件)")


        if not self._parsed_elements:
            return ToolResult(output=f"在 '{repo_path}' 中未找到目标语言 ({', '.join(langs_to_parse)}) 的受支持的类元素。共扫描 {scanned_files_count} 个相关文件。")

        # 在生成图表和描述之前，将属性和方法从集合转换为排序列表
        for el_name in self._parsed_elements:
            if isinstance(self._parsed_elements[el_name].get("attributes"), set):
                self._parsed_elements[el_name]["attributes"] = sorted(list(self._parsed_elements[el_name]["attributes"]))
            if isinstance(self._parsed_elements[el_name].get("methods"), set):
                self._parsed_elements[el_name]["methods"] = sorted(list(self._parsed_elements[el_name]["methods"]))
        
        try:
            # 1. 生成 PNG 图表 (这部分逻辑不变)
            generated_png_path_str = self._generate_uml_diagram(Path(output_png_path), include_attributes, include_methods)
            # 确保 generated_png_path 是 Path 对象
            generated_png_path = Path(generated_png_path_str) if generated_png_path_str else Path(output_png_path)


            # 2. 生成文本描述 (这部分逻辑不变)
            text_description = self._generate_textual_description(include_attributes, include_methods)
            
            # 3. 组合结果到 ToolResult 的 output 字符串中 (这部分逻辑不变)
            summary_message = f"UML 图表和文本描述已成功生成。\n"
            # ... (添加更多摘要信息) ...
            summary_message += f"PNG 图像保存路径: '{generated_png_path.resolve() if generated_png_path.exists() else '未找到或未生成'}'\n\n"
            summary_message += "---\nUML 图表文本描述内容:\n---\n"
            summary_message += text_description
            from utils.logger import logger
            # --- 新增：通过 WebSocket 发送图片 ---
            if self.websocket and generated_png_path.exists():
                logger.info(f"准备通过 WebSocket 发送 UML 图片 '{generated_png_path.name}'。")
                try:
                    # **方案 A: 发送原始字节**
                    # 首先，发送一个文本消息(JSON格式)作为信号，告诉前端接下来是图片数据
                    await self.websocket.send_json({
                        "type": "uml_diagram_bytes_start", # 自定义消息类型
                        "filename": generated_png_path.name,
                        "content_type": "image/png" 
                        # 可以添加更多元数据，比如与哪个请求相关联的ID等
                    })

                    # 然后，发送图片文件的字节流
                    with open(generated_png_path, "rb") as f_img:
                        image_bytes = f_img.read()
                    await self.websocket.send_bytes(image_bytes)
                    logger.info(f"UML 图片 '{generated_png_path.name}' 已通过 WebSocket 发送 ({len(image_bytes)} 字节)。")
                    summary_message += f"\n[信息] UML 图表 '{generated_png_path.name}' 也已通过 WebSocket 直接发送。"

                except Exception as ws_send_error:
                    logger.error(f"通过 WebSocket 发送 UML 图片失败: {ws_send_error}")
                    summary_message += f"\n[警告] 通过 WebSocket 发送 UML 图片失败: {ws_send_error}"
            
            elif not self.websocket:
                logger.warning("CodeToUMLTool 未配置 WebSocket 对象, 无法直接发送图片。")
                summary_message += "\n[信息] CodeToUMLTool 未关联 WebSocket, 图片未直接发送。"
            elif not generated_png_path.exists():
                logger.error(f"生成的 UML 图片路径 '{generated_png_path}' 不存在, 无法发送图片。")
                summary_message += f"\n[错误] 生成的 UML 图片 '{generated_png_path}' 未找到, 图片未发送。"
            # --- 发送图片逻辑结束 ---
                
            return ToolResult(output=summary_message)

        except ToolError as e:
            raise e # 将工具定义的错误直接抛出
        except Exception as e:
            logger.error(f"在CodeToUMLTool.execute中发生意外错误: {e}", exc_info=True)
            raise ToolError(f"在UML生成过程中发生意外错误: {str(e)}")
