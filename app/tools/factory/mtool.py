import inspect
import re
import asyncio
from functools import wraps
from typing import Any, Dict, List, Annotated, get_origin, get_args
from pathlib import Path
import sys

root_path = str(Path(__file__).parent.parent.parent)
sys.path.append(root_path)

from tools import ToolCollection
from tools.base import BaseTool, ToolResult

from pydantic import Field, BaseModel, create_model

class IsRequired:
    pass
def _map_type_to_json_schema(py_type: Any) -> str:
    if py_type == str: return "string"
    if py_type == int: return "integer"
    return "string"
def _parse_docstring_for_args(doc: str) -> Dict[str, str]:
    if not doc: return {}
    match = re.search(r'Args:\s*\n((?:\s+.*\n?)*)', doc, re.MULTILINE)
    if not match: return {}
    args_section = match.group(1)
    descriptions = {}
    pattern = re.compile(r'^\s*(\w+)\s*:\s*(.*)', re.MULTILINE)
    for name, desc in pattern.findall(args_section):
        descriptions[name.strip()] = desc.strip()
    return descriptions



def mtool(name: str, description: str, strict: bool = True):
    def decorator(func: callable):
        sig = inspect.signature(func)
        docstring = inspect.getdoc(func)
        arg_descriptions = _parse_docstring_for_args(docstring)
        tool_properties, required_list, runtime_args_names = {}, [], []
        for param_name, parameter in sig.parameters.items():
            annotation = parameter.annotation
            if get_origin(annotation) is Annotated:
                type_args = get_args(annotation)
                actual_type, metadata = type_args[0], type_args[1:]
                if IsRequired in metadata: required_list.append(param_name)
                tool_properties[param_name] = {"description": arg_descriptions.get(param_name, ""), "type": _map_type_to_json_schema(actual_type)}
            elif parameter.kind not in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.VAR_POSITIONAL):
                runtime_args_names.append(param_name)
        dynamic_fields: Dict[str, Any] = {
            'name': (str, ...), 'description': (str, ...), 'strict': (bool, True), 'parameters': (Dict[str, Any], {}),
        }
        for arg_name in runtime_args_names:
            dynamic_fields[arg_name] = (Any, Field(None, exclude=True))
        DynamicDataModel = create_model(f'Dynamic{func.__name__}DataModel', __base__=BaseModel, **dynamic_fields)
        
        class ToolWrapper:
            def __init__(self, **kwargs):
                self._original_func = func
                self._runtime_kwargs = kwargs
                self.model_instance = DynamicDataModel(
                    name=name, description=description, strict=strict,
                    parameters={"type": "object", "properties": tool_properties, "required": required_list},
                    **kwargs
                )
            async def execute(self, **llm_provided_kwargs: Any) -> ToolResult:
                all_args = {**self._runtime_kwargs, **llm_provided_kwargs}
                result = await self._original_func(**all_args)
                if isinstance(result, ToolResult):
                    return result
                return ToolResult(output=result)
            def to_param(self) -> Dict:
                return {
                    "type": "function",
                    "function": {
                        "name": self.model_instance.name,
                        "description": self.model_instance.description,
                        "parameters": self.model_instance.parameters,
                    },
                }
            async def __call__(self, **llm_provided_kwargs: Any) -> ToolResult:
                return await self.execute(**llm_provided_kwargs)
            def __getattr__(self, item):
                return getattr(self.model_instance, item)

        # 【关键修改】根据有无运行时参数，决定返回实例还是工厂
        if not runtime_args_names:
          
            return ToolWrapper()
        else:
          
            @wraps(func)
            def tool_factory(**kwargs) -> ToolWrapper:
                return ToolWrapper(**kwargs)
            return tool_factory
    return decorator



async def main():
    from tools import PlanningTool, FinalResponse, BaiduSearch
    
    tools = ToolCollection(PlanningTool(),
                           FinalResponse(),
                           BaiduSearch(),
                          )
    
    print(tools.to_params())

if __name__ == "__main__":
    asyncio.run(main())
   