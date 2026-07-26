"""Entry point for the call-me-maybe function calling system."""

# This is the file that runs when you do `python -m src` or `make run`.
# It parses CLI arguments, loads the input files, and kicks off the pipeline.
#
# Default paths (can be overridden via CLI args):
#   --functions_definition  data/input/functions_definition.json
#   --input                 data/input/function_calling_tests.json
#   --output                data/output/function_calling_results.json

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
    parser.add_argument('--output', default='data/output/function_calling_results.json')
    args = parser.parse_args()

    # load and validate both input files
    functions = load_functions(args.functions_definition)
    prompts = load_prompts(args.input)

    # exit early if either file failed to load
    if not functions:
        print("Error: no functions loaded, exiting.")
        return
    if not prompts:
        print("Error: no prompts loaded, exiting.")
        return

    # run the pipeline: select functions + extract parameters for each prompt
    run_pipeline(functions, [p.prompt for p in prompts], args.output)


if __name__ == "__main__":
    main()
