"""Functions to load and validate input JSON files."""

import json
from typing import List
from src.models import FunctionDefinition, Prompt


def load_functions(path: str) -> List[FunctionDefinition]:
    """Load and validate function definitions from a JSON file.

    Args:
        path: Path to the functions_definition.json file.

    Returns:
        List of validated FunctionDefinition objects.
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

    Args:
        path: Path to the function_calling_tests.json file.

    Returns:
        List of validated Prompt objects.
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
