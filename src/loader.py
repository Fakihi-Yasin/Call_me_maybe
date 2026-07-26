"""Functions to load and validate input JSON files."""

# This file is responsible for reading the two input JSON files:
# - functions_definition.json: the list of available functions the model can call
# - function_calling_tests.json: the list of prompts to process

import json
from typing import List
from src.models import FunctionDefinition, Prompt


def load_functions(path: str) -> List[FunctionDefinition]:
    """Load and validate function definitions from a JSON file.

    Reads the JSON file at `path`, and converts each entry into a
    FunctionDefinition object (pydantic validates the structure automatically).

    Args:
        path: Path to the functions_definition.json file.

    Returns:
        List of validated FunctionDefinition objects, or empty list on error.
    """
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return [FunctionDefinition(**item) for item in data]
    except FileNotFoundError:
        print(f"Error: file not found: {path}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in {path}: {e}")
        return []
    except Exception as e:
        print(f"Error: could not load functions: {e}")
        return []


def load_prompts(path: str) -> List[Prompt]:
    """Load and validate prompts from a JSON file.

    Reads the JSON file at `path`, and converts each entry into a
    Prompt object.

    Args:
        path: Path to the function_calling_tests.json file.

    Returns:
        List of validated Prompt objects, or empty list on error.
    """
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return [Prompt(**item) for item in data]
    except FileNotFoundError:
        print(f"Error: file not found: {path}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in {path}: {e}")
        return []
    except Exception as e:
        print(f"Error: could not load prompts: {e}")
        return []
