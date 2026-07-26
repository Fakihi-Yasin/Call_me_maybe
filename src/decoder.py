"""Constrained JSON decoder using token-level logit masking."""

# This is the core file of the project.
# It handles two things:
#   1. Selecting the right function for a given prompt (_select_function)
#   2. Extracting the parameter values token by token (_gen_string, _gen_number, _gen_boolean)
#
# The key idea: instead of letting the model generate freely, we restrict
# which tokens it can pick at each step (constrained decoding).

import json
import re
from typing import Any, Dict, List, Optional, Tuple
from llm_sdk import Small_LLM_Model  # type: ignore


NUMBER_RE = re.compile(r'^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$')


def build_vocab_index(
    model: Small_LLM_Model,
) -> Tuple[Dict[str, int], Dict[int, str]]:
    """Load vocab and build both directions of the mapping.

    Returns:
        vocab: token string → token ID  (e.g. "hello" → 1234)
        id_to_token: token ID → token string  (e.g. 1234 → "hello")
    """
    with open(model.get_path_to_vocab_file()) as f:
        vocab: Dict[str, int] = json.load(f)
    # reverse the vocab dict to get ID → token
    id_to_token = {v: k for k, v in vocab.items()}
    return vocab, id_to_token


def _tok(token_id: int, id_to_token: Dict[int, str]) -> str:
    """Convert a token ID to a plain string.

    Qwen's tokenizer uses special unicode characters:
    - Ġ (\\u0120) represents a leading space
    - \\u010a represents a newline
    We replace them with normal characters.
    """
    return id_to_token.get(token_id, '').replace('\u0120', ' ').replace('\u010a', '\n')


def _best(
    model: Small_LLM_Model,
    input_ids: List[int],
    valid_ids: List[int],
) -> int:
    """Return the highest-scoring token ID from a restricted set.

    Instead of picking the globally best next token, we only consider
    tokens in valid_ids — this is the constrained decoding mechanism.
    """
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
    """Generate a JSON string value token by token.

    Constraints:
    - Only tokens that don't contain quotes, newlines, or carriage returns are allowed
    - Stops when the model picks a closing quote token
    - Stops early if a repeating pattern is detected (to avoid infinite loops)

    The opening quote is assumed to already be appended to input_ids before calling.
    """
    quote_id = vocab['"']
    bad = {'"', '\n', '\r'}

    # build the list of allowed token IDs (no quotes or newlines, except the closing quote)
    valid_ids = [
        tid for s, tid in vocab.items()
        if not any(c in s for c in bad) or s == '"'
    ]

    result = ''
    ids = list(input_ids)
    seen: List[int] = []  # track recent tokens to detect repetition

    for _ in range(max_tokens):
        next_id = _best(model, ids, valid_ids)

        # stop if model chose the closing quote
        if next_id == quote_id:
            break

        # stop on repetition: detect repeated patterns of length 1-4
        # e.g. if the model keeps generating "cat$cat$cat$..." we stop early
        seen.append(next_id)
        for pat_len in range(1, 5):
            if len(seen) >= pat_len * 2 and seen[-pat_len:] == seen[-pat_len * 2:-pat_len]:
                return result.strip()

        result += _tok(next_id, id_to_token)
        ids.append(next_id)

    return result.strip()


def _gen_number(
    model: Small_LLM_Model,
    vocab: Dict[str, int],
    id_to_token: Dict[int, str],
    input_ids: List[int],
    max_tokens: int = 16,
) -> float:
    """Generate a JSON number value token by token.

    Constraints:
    - Only tokens made of digit/dot/sign characters are allowed
    - Stops when a terminator token (`,`, `}`, `]`) is picked
    - Validates the growing number string with a regex at each step
    """
    num_chars = set('0123456789.-+eE')

    # terminator tokens: these signal the end of the number in JSON
    term = {vocab[t] for t in (',', '}', ']') if t in vocab}

    # allowed tokens: only those whose characters are all valid number chars
    valid_ids = [
        tid for s, tid in vocab.items()
        if all(c in num_chars for c in s.lstrip('\u0120')) and s.lstrip('\u0120')
    ] + list(term)

    result = ''
    ids = list(input_ids)
    has_dot = False

    for _ in range(max_tokens):
        next_id = _best(model, ids, valid_ids)
        tok = _tok(next_id, id_to_token).strip()

        # stop if we hit a JSON terminator
        if next_id in term:
            break

        if tok == '.':
            if has_dot:
                break  # can't have two dots in a number
            has_dot = True
        elif has_dot and tok.isdigit():
            break  # stop before decimal digits — keep integer part only

        # validate the candidate number string before accepting the token
        candidate = result + tok
        if not re.match(r'^-?[0-9]*\.?[0-9]*([eE][+-]?[0-9]*)?$', candidate):
            break

        result += tok
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
    """Generate a JSON boolean value.

    Constrains the model to only pick between 'true' and 'false' tokens.
    """
    true_ids = [tid for s, tid in vocab.items() if s.lstrip('\u0120') == 'true']
    false_ids = [tid for s, tid in vocab.items() if s.lstrip('\u0120') == 'false']
    next_id = _best(model, input_ids, true_ids + false_ids)
    return next_id in true_ids


def _score_tokens(
    model: Small_LLM_Model,
    prefix_ids: List[int],
    target_ids: List[int],
) -> float:
    """Return the mean log-probability of target_ids given prefix_ids as context.

    Used to score how likely a sequence of tokens is to follow a given prefix.
    We normalize by length to avoid penalizing longer sequences.
    """
    score = 0.0
    ids = list(prefix_ids)
    for token_id in target_ids:
        logits = model.get_logits_from_input_ids(ids)
        score += logits[token_id]
        ids.append(token_id)
    return score / len(target_ids)


def _select_function(
    model: Small_LLM_Model,
    prompt: str,
    functions: List[Any],
) -> str:
    """Select the best matching function for a given prompt.

    Strategy: for each candidate function, compute two scores:
    - desc_score: how likely is the function's description to follow "What to do: ..."
    - name_score: how likely is the function's name to follow "Function name: ..."

    The function with the highest combined score wins.
    We use descriptions (natural language) because the model understands them
    better than arbitrary function names like "fn_substitute_string_with_regex".
    """
    best_name: Optional[str] = None
    best_score = float('-inf')

    for fn in functions:
        # score the description: does this function's purpose match the request?
        desc_score = _score_tokens(
            model,
            model.encode(f'Task: "{prompt}"\nWhat to do: ')[0].tolist(),
            model.encode(fn.description)[0].tolist(),
        )
        # score the name: does this function name follow the prompt?
        name_score = _score_tokens(
            model,
            model.encode(f'Task: "{prompt}"\nFunction name: ')[0].tolist(),
            model.encode(fn.name)[0].tolist(),
        )
        score = desc_score + name_score
        if score > best_score:
            best_score = score
            best_name = fn.name

    return best_name if best_name is not None else functions[0].name


def generate_constrained_call(
    model: Small_LLM_Model,
    prompt: str,
    functions: List[Any],
    vocab: Dict[str, int],
    id_to_token: Dict[int, str],
) -> Dict[str, Any]:
    """Generate a validated function call using constrained decoding.

    Two steps:
    1. Select the right function using _select_function
    2. For each parameter of that function, extract its value from the prompt
       using the appropriate generator (_gen_string, _gen_number, _gen_boolean)

    Args:
        model: The LLM model instance.
        prompt: Natural language prompt.
        functions: List of FunctionDefinition objects.
        vocab: Token string to ID mapping.
        id_to_token: Token ID to string mapping.

    Returns:
        Dict with 'name' and 'parameters' keys.
    """
    # Step 1: select function name
    fn_name = _select_function(model, prompt, functions)

    # Step 2: extract arguments for the chosen function
    chosen = next(fn for fn in functions if fn.name == fn_name)
    parameters: Dict[str, Any] = {}

    param_items = list(chosen.parameters.items())
    for i, (param_name, param_def) in enumerate(param_items):
        # build a prompt that gives the model enough context to extract the right value
        arg_ids = model.encode(
            f'Function: {chosen.name}\n'
            f'Description: {chosen.description}\n'
            f'User request: "{prompt}"\n'
            f'Extract only the value of "{param_name}" from the user request above.\n'
            f'"{param_name}": '
        )[0].tolist()

        # generate the value using the appropriate constrained generator
        if param_def.type in ('number', 'integer', 'float'):
            parameters[param_name] = _gen_number(
                model, vocab, id_to_token, arg_ids
            )
        elif param_def.type == 'boolean':
            parameters[param_name] = _gen_boolean(model, vocab, arg_ids)
        else:
            # for strings, append the opening quote before generating
            quote_id = vocab['"']
            parameters[param_name] = _gen_string(
                model, vocab, id_to_token, arg_ids + [quote_id]
            )

    return {'name': fn_name, 'parameters': parameters}
