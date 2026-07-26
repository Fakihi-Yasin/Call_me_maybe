"""Pydantic models for input validation and output structure."""

# This file defines the data structures used across the project.
# Pydantic automatically validates that the JSON data matches the expected types.

from typing import Dict, Any
from pydantic import BaseModel


class ParameterType(BaseModel):
    """A single parameter's type definition (e.g. 'string', 'number', 'boolean')."""

    type: str


class FunctionDefinition(BaseModel):
    """Represents one callable function loaded from functions_definition.json.

    Example:
        name: "fn_add_numbers"
        description: "Add two numbers together and return their sum."
        parameters: {"a": ParameterType(type="number"), "b": ParameterType(type="number")}
        returns: ParameterType(type="number")
    """

    name: str
    description: str
    parameters: Dict[str, ParameterType]  # param name → its type
    returns: ParameterType


class Prompt(BaseModel):
    """A single natural language prompt from function_calling_tests.json.

    Example:
        prompt: "What is the sum of 2 and 3?"
    """

    prompt: str


class FunctionCall(BaseModel):
    """The final output: which function was selected and with what arguments.

    This is what gets written to the output JSON file.

    Example:
        prompt: "What is the sum of 2 and 3?"
        name: "fn_add_numbers"
        parameters: {"a": 2.0, "b": 3.0}
    """

    prompt: str
    name: str
    parameters: Dict[str, Any]  # param name → extracted value
