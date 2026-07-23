"""Entry point for the call-me-maybe function calling system."""

import argparse
from src.loader import load_functions, load_prompts
from src.pipeline import run_pipeline


def main() -> None:
    """Parse CLI args and run the function calling pipeline."""
    parser = argparse.ArgumentParser(description='LLM function calling system')
    parser.add_argument(
        '--functions_definition',
        default='data/input/functions_definition.json',
    )
    parser.add_argument('--input', default='data/input/function_calling_tests.json')
    parser.add_argument('--output', default='data/output/function_calls.json')
    args = parser.parse_args()

    functions = load_functions(args.functions_definition)
    prompts = load_prompts(args.input)

    if not functions:
        print("Error: no functions loaded, exiting.")
        return
    if not prompts:
        print("Error: no prompts loaded, exiting.")
        return

    run_pipeline(functions, [p.prompt for p in prompts], args.output)


if __name__ == "__main__":
    main()
