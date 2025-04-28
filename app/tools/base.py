from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

"""
{
    "type": "function",
    "function": {
        "name": "your_function_name",  # The name of the function to be called
        "description": "A clear description of what this function does, used by the model to decide when to call it.",
        "parameters": {
            "type": "object",  # Must be 'object' for function parameters
            "properties": {
                "parameter_name_1": {
                    "type": "string",  # JSON Schema type (string, integer, number, boolean, array, object)
                    "description": "Description of parameter_name_1, e.g., 'The city name'",
                },
                "parameter_name_2": {
                    "type": "integer",
                    "description": "Description of parameter_name_2, e.g., 'The number of days'",
                },
                # Add more parameters as needed
            },
            "required": ["parameter_name_1"],  # A list of parameter names that are mandatory
        },
    },
}

"""

class BaseTool(ABC, BaseModel):
    name: str
    description: str
    parameters: Optional[dict] = None

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, **kwargs) -> Any:
        return await self.execute(**kwargs)

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Execute the tool with given parameters."""

    def to_param(self) -> Dict:
        """Convert tool to function call format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolResult(BaseModel):
    """Represents the result of a tool execution."""

    error: Optional[str] = Field(default=None)
    output: Any = Field(default=None)
    system: Optional[str] = Field(default=None)

    class Config:
        arbitrary_types_allowed = True

    def __bool__(self):
        return any(getattr(self, field) for field in self.__fields__)

    def __add__(self, other: "ToolResult"):
        def combine_fields(
            field: Optional[str], other_field: Optional[str], concatenate: bool = True
        ):
            if field and other_field:
                if concatenate:
                    return field + other_field
                raise ValueError("Cannot combine tool results")
            return field or other_field

        return ToolResult(
            output=combine_fields(self.output, other.output),
            error=combine_fields(self.error, other.error),
            system=combine_fields(self.system, other.system),
        )

    def __str__(self):
        return f"Error: {self.error}" if self.error else self.output

    def replace(self, **kwargs):
        """Returns a new ToolResult with the given fields replaced."""
        # return self.copy(update=kwargs)
        return type(self)(**{**self.dict(), **kwargs})


class CLIResult(ToolResult):
    """A ToolResult that can be rendered as a CLI output."""


class ToolFailure(ToolResult):
    """A ToolResult that represents a failure."""



