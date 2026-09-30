"""Pure helpers for the workflow context (a plain dict passed from node to node)."""
import re
from datetime import datetime, timezone

# Keys injected by the engine that must never be persisted to the DB logs.
INTERNAL_CTX_KEYS = {"__db__", "__execution__", "__user_id__"}


def utcnow():
    return datetime.now(timezone.utc)


def ms(start, end) -> float:
    return (end - start).total_seconds() * 1000


def diff(before: dict, after: dict) -> dict:
    """Keys that are new or changed in `after` (stored as the node's context_diff)."""
    return {k: v for k, v in after.items() if k not in before or before[k] != v}


def clean_ctx(ctx: dict) -> dict:
    return {k: v for k, v in ctx.items() if k not in INTERNAL_CTX_KEYS}


def interpolate_context(value, ctx: dict):
    """Replace {{a.b.c}} placeholders in strings (recursing into dicts/lists).
    Unresolvable placeholders are left untouched."""
    if isinstance(value, str):
        def replacer(match):
            result = ctx
            for part in match.group(1).strip().split("."):
                if not isinstance(result, dict):
                    return match.group(0)
                result = result.get(part)
            return str(result) if result is not None else match.group(0)
        return re.sub(r"\{\{([^}]+)\}\}", replacer, value)
    if isinstance(value, dict):
        return {k: interpolate_context(v, ctx) for k, v in value.items()}
    if isinstance(value, list):
        return [interpolate_context(i, ctx) for i in value]
    return value


def set_nested(ctx: dict, dotted_key: str, value) -> dict:
    """Return a copy of ctx with ctx['a']['b']['c'] = value for 'a.b.c' (any depth).
    Dicts along the path are copied so earlier snapshots are never mutated."""
    new_ctx = ctx.copy()
    node, parts = new_ctx, dotted_key.split(".")
    for part in parts[:-1]:
        child = node.get(part)
        node[part] = node = dict(child) if isinstance(child, dict) else {}
    node[parts[-1]] = value
    return new_ctx


# operator name -> (actual, expected, expected2) -> bool. Numeric ops raise on bad input.
_OPERATORS = {
    "equals":       lambda a, e, e2: a == e,
    "not_equals":   lambda a, e, e2: a != e,
    "contains":     lambda a, e, e2: e in a,
    "starts_with":  lambda a, e, e2: a.startswith(e),
    "ends_with":    lambda a, e, e2: a.endswith(e),
    "greater_than": lambda a, e, e2: float(a) > float(e),
    "less_than":    lambda a, e, e2: float(a) < float(e),
    "between":      lambda a, e, e2: float(e) <= float(a) <= float(e2),
    "is_empty":     lambda a, e, e2: a.strip() == "",
    "is_not_empty": lambda a, e, e2: a.strip() != "",
}


def evaluate_condition(actual: str, operator: str, expected: str, expected2: str = "") -> bool:
    fn = _OPERATORS.get(operator)
    try:
        return bool(fn(actual, expected, expected2)) if fn else False
    except (ValueError, TypeError):
        return False
