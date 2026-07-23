"""Pydantic models for input validation and output structure."""

from typing import Dict, Any
from pydantic import BaseModel


class ParameterType(BaseModel):
    """A single parameter's type definition."""

    type: str


class FunctionDefinition(BaseModel):
    """A callable function with its name, description, and parameters."""

    name: str
    description: str
    parameters: Dict[str, ParameterType]
    returns: ParameterType


class Prompt(BaseModel):
    """A single natural language prompt from the input file."""

    prompt: str


class FunctionCall(BaseModel):
    """The output: which function to call and with what arguments."""

    prompt: str
    name: str
    parameters: Dict[str, Any]
