"""Shared token-accounting validation for dialogue delivery and reporting."""

from typing import Any, Dict, Optional

from .inputs import GENERATION


def is_integer(value: Any) -> bool:
    """Check for a nonnegative integer, excluding booleans."""
    return type(value) is int and value >= 0


def normalize(raw: Any) -> Dict[str, Any]:
    """Keep only known numeric accounting fields, entirely outside prompts."""
    if not isinstance(raw, dict):
        return {}
    result = {}
    for key in (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
    ):
        if is_integer(raw.get(key)):
            result[key] = raw[key]
    for group, fields in (
        ("completion_tokens_details", ("reasoning_tokens", "safety_tokens")),
        ("prompt_tokens_details", ("cached_tokens",)),
    ):
        details = raw.get(group)
        if isinstance(details, dict):
            result[group] = {
                field: details[field]
                for field in fields
                if is_integer(details.get(field))
            }
    return result


def delivery_bound(
    usage: Dict[str, Any], generation: Optional[Dict[str, Any]] = None
) -> Optional[int]:
    """Return the non-reasoning token bound, or None for invalid usage."""
    generation = GENERATION if generation is None else generation
    usage = normalize(usage)
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    total = usage.get("total_tokens")
    details = usage.get("completion_tokens_details", {})
    reasoning = details.get("reasoning_tokens") if isinstance(details, dict) else None
    disabled = generation["thinking"]["type"] == "disabled"
    if reasoning is None and disabled:
        reasoning = 0
    if not all(is_integer(n) for n in (prompt, completion, total, reasoning)):
        return None
    if disabled and reasoning != 0:
        return None
    if reasoning > completion or completion > generation["max_tokens"]:
        return None
    if total != prompt + completion:
        return None
    return completion - reasoning
