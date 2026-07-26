"""Pipeline: load model, process all prompts, write output."""

# This file ties everything together.
# It loads the model, loops over all prompts, calls generate_constrained_call
# for each one, and writes the results to the output JSON file.

import json
import os
from typing import List
from llm_sdk import Small_LLM_Model  # type: ignore
from src.models import FunctionDefinition, FunctionCall
from src.decoder import build_vocab_index, generate_constrained_call


def run_pipeline(
    functions: List[FunctionDefinition],
    prompts_data: List[str],
    output_path: str,
) -> None:
    """Run the full function-calling pipeline.

    Args:
        functions: Validated function definitions loaded from JSON.
        prompts_data: List of natural language prompt strings.
        output_path: Path to write the output JSON file.
    """
    # load the LLM model (Qwen 0.6B by default, auto-selects cuda/mps/cpu)
    print("Loading model...")
    model = Small_LLM_Model()

    # build vocab index once and reuse for all prompts
    vocab, id_to_token = build_vocab_index(model)
    print(f"Vocabulary loaded: {len(vocab)} tokens")

    results: List[FunctionCall] = []

    for i, prompt in enumerate(prompts_data):
        print(f"[{i + 1}/{len(prompts_data)}] {prompt}")
        try:
            # for each prompt: select the right function and extract its arguments
            call = generate_constrained_call(
                model, prompt, functions, vocab, id_to_token
            )
            result = FunctionCall(
                prompt=prompt,
                name=call['name'],
                parameters=call['parameters'],
            )
            results.append(result)
            print(f"  → {result.name}({result.parameters})")
        except Exception as e:
            print(f"  Error processing prompt: {e}")

    # write all results to the output JSON file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump([r.model_dump() for r in results], f, indent=2)
    print(f"\nOutput written to {output_path}")
