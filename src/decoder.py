"""Constrained JSON decoder using token-level logit masking."""

import json
import re
from typing import Any, Dict, List, Optional, Tuple
from llm_sdk import Small_LLM_Model  # type: ignore


NUMBER_RE = re.compile(r'^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$')


def build_vocab_index(
    model: Small_LLM_Model,
) -> Tuple[Dict[str, int], Dict[int, str]]:
    """Load vocab and build both directions of the mapping."""
    with open(model.get_path_to_vocab_file()) as f:
        vocab: Dict[str, int] = json.load(f)
    id_to_token = {v: k for k, v in vocab.items()}
    return vocab, id_to_token


def _tok(token_id: int, id_to_token: Dict[int, str]) -> str:
    """Convert token ID to plain string (strip Ġ space prefix)."""
    return id_to_token.get(token_id, '').replace('\u0120', ' ').replace('\u010a', '\n')


def _best(
    model: Small_LLM_Model,
    input_ids: List[int],
    valid_ids: List[int],
) -> int:
    """Return the highest-scoring token ID from valid_ids."""
    logits = model.get_logits_from_input_ids(input_ids)
    valid_set = set(valid_ids)
    return max(valid_set, key=lambda i: logits[i])


def _gen_string(
    model: Small_LLM_Model,
    vocab: Dict[str, int],
    id_to_token: Dict[int, str],
    input_ids: List[int],
    max_tokens: int = 64,
) -> str:
    """Generate a JSON string value (opening quote already in prompt)."""
    quote_id = vocab['"']
    bad = {'"', '\n', '\r'}
    valid_ids = [
        tid for s, tid in vocab.items()
        if not any(c in s for c in bad) or s == '"'
    ]
    result = ''
    ids = list(input_ids)
    for _ in range(max_tokens):
        next_id = _best(model, ids, valid_ids)
        if next_id == quote_id:
            break
        result += _tok(next_id, id_to_token)
        ids.append(next_id)
    return result


def _gen_number(
    model: Small_LLM_Model,
    vocab: Dict[str, int],
    id_to_token: Dict[int, str],
    input_ids: List[int],
    max_tokens: int = 16,
) -> float:
    """Generate a JSON number value."""
    num_chars = set('0123456789.-+eE')
    term = {vocab[t] for t in (',', '}', ']') if t in vocab}
    valid_ids = [
        tid for s, tid in vocab.items()
        if all(c in num_chars for c in s.lstrip('\u0120')) and s.lstrip('\u0120')
    ] + list(term)

    result = ''
    ids = list(input_ids)
    for _ in range(max_tokens):
        next_id = _best(model, ids, valid_ids)
        if next_id in term:
            break
        result += _tok(next_id, id_to_token).strip()
        ids.append(next_id)
    try:
        return float(result) if result else 0.0
    except ValueError:
        return 0.0


def _gen_boolean(
    model: Small_LLM_Model,
    vocab: Dict[str, int],
    input_ids: List[int],
) -> bool:
    """Generate a JSON boolean value."""
    true_ids = [tid for s, tid in vocab.items() if s.lstrip('\u0120') == 'true']
    false_ids = [tid for s, tid in vocab.items() if s.lstrip('\u0120') == 'false']
    next_id = _best(model, input_ids, true_ids + false_ids)
    return next_id in true_ids


def _select_function(
    model: Small_LLM_Model,
    input_ids: List[int],
    fn_names: List[str],
) -> str:
    """Score each function name by summing token log-probs; return best."""
    best_name: Optional[str] = None
    best_score = float('-inf')
    for fn_name in fn_names:
        fn_ids = model.encode(fn_name)[0].tolist()
        score = 0.0
        ids = list(input_ids)
        for token_id in fn_ids:
            logits = model.get_logits_from_input_ids(ids)
            score += logits[token_id]
            ids.append(token_id)
        if score > best_score:
            best_score = score
            best_name = fn_name
    return best_name if best_name is not None else fn_names[0]


def generate_constrained_call(
    model: Small_LLM_Model,
    prompt: str,
    functions: List[Any],
    vocab: Dict[str, int],
    id_to_token: Dict[int, str],
) -> Dict[str, Any]:
    """Generate a validated function call using constrained decoding.

    Args:
        model: The LLM model instance.
        prompt: Natural language prompt.
        functions: List of FunctionDefinition objects.
        vocab: Token string to ID mapping.
        id_to_token: Token ID to string mapping.

    Returns:
        Dict with 'name' and 'parameters' keys.
    """
    fn_descriptions = '\n'.join(
        f'- {fn.name}: {fn.description} '
        f'(params: {", ".join(f"{k}:{v.type}" for k, v in fn.parameters.items())})'
        for fn in functions
    )
    base_prompt = (
        f'Available functions:\n{fn_descriptions}\n\n'
        f'User request: {prompt}\n\n'
    )

    # Step 1: select function name
    select_ids = model.encode(
        base_prompt
        + 'Choose the single most appropriate function name from the list above'
        + ' that best matches the user request. Answer with only the function name: '
    )[0].tolist()
    fn_name = _select_function(model, select_ids, [fn.name for fn in functions])

    # Step 2: extract arguments
    chosen = next(fn for fn in functions if fn.name == fn_name)
    parameters: Dict[str, Any] = {}

    for param_name, param_def in chosen.parameters.items():
        arg_prompt = (
            base_prompt
            + f'Function to call: {fn_name}\n'
            + f'Value for "{param_name}" ({param_def.type}): '
        )
        arg_ids = model.encode(arg_prompt)[0].tolist()

        if param_def.type in ('number', 'integer', 'float'):
            parameters[param_name] = _gen_number(
                model, vocab, id_to_token, arg_ids
            )
        elif param_def.type == 'boolean':
            parameters[param_name] = _gen_boolean(model, vocab, arg_ids)
        else:
            quote_id = vocab['"']
            parameters[param_name] = _gen_string(
                model, vocab, id_to_token, arg_ids + [quote_id]
            )

    return {'name': fn_name, 'parameters': parameters}
