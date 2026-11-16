"""Strict rating validation and provider-backed token accounting."""

import json
import re
from typing import Any, Dict, List, Tuple

from .api import ensure_no_secret

LIKERT_RESPONSES = (
    "strongly disagree",
    "disagree",
    "neutral",
    "agree",
    "strongly agree",
)

COUNT_FIELDS = (
    "input_tokens",
    "message_output_tokens",
    "thinking_tokens",
    "safety_tokens",
    "completion_tokens",
    "total_tokens",
)


def empty_counts() -> Dict[str, Any]:
    return dict.fromkeys(COUNT_FIELDS)


def _integer(value: Any) -> bool:
    return type(value) is int and value >= 0


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("Non-JSON numeric constant")


def parse_json(value):
    return json.loads(value, object_pairs_hook=_object, parse_constant=_constant)


def capture_raw(raw: bytes, key: str) -> Dict[str, Any]:
    """Retain exact text or bytes, blocking literal and JSON-escaped secrets."""
    ensure_no_secret(raw, key)
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        return {"raw_response_bytes": raw}
    # Inspect JSON string tokens even if the outer document has duplicate keys
    # or is incomplete; escaped credentials must not evade the persistence guard.
    for match in re.finditer(r'"(?:[^"\\]|\\.)*"', text):
        try:
            value = json.loads(match.group())
        except ValueError:
            continue
        ensure_no_secret(value, key)
    return {"raw_response_text": text}


def _counts(usage: Any, thinking: str, budget: int) -> Tuple[Dict[str, Any], bool]:
    counts = empty_counts()
    if not isinstance(usage, dict):
        return counts, False
    for field, provider in (
        ("input_tokens", "prompt_tokens"),
        ("completion_tokens", "completion_tokens"),
        ("total_tokens", "total_tokens"),
    ):
        if _integer(usage.get(provider)):
            counts[field] = usage[provider]
    details = usage.get("completion_tokens_details", {})
    if not isinstance(details, dict):
        return counts, False
    reasoning = details.get("reasoning_tokens")
    if thinking == "disabled" and "reasoning_tokens" not in details:
        reasoning = 0  # Explicitly requested non-thinking mode.
    safety = details.get("safety_tokens", 0)  # No optional safety review requested.
    if _integer(reasoning):
        counts["thinking_tokens"] = reasoning
    if _integer(safety):
        counts["safety_tokens"] = safety
    prompt, completion, total = (
        counts[name] for name in ("input_tokens", "completion_tokens", "total_tokens")
    )
    if not all(
        _integer(value) for value in (prompt, completion, total, reasoning, safety)
    ):
        return counts, False
    if (
        total != prompt + completion
        or reasoning + safety > completion
        or completion > budget
        or (thinking == "disabled" and reasoning != 0)
    ):
        return counts, False
    counts["message_output_tokens"] = completion - reasoning - safety
    return counts, True


def evaluate(
    raw: bytes, statements: List[Dict[str, str]], thinking: str, budget: int, key: str
) -> Dict[str, Any]:
    result = {
        **capture_raw(raw, key),
        "content": None,
        "reasoning_content": None,
        "usage": None,
        "token_counts": empty_counts(),
        "accounting_valid": False,
        "ratings": None,
        "issues": [],
    }
    issues = result["issues"]
    try:
        response = parse_json(raw)
    except (ValueError, UnicodeError, RecursionError):
        issues.append("invalid_api_json")
        return result
    ensure_no_secret(response, key)
    if not isinstance(response, dict):
        issues.append("invalid_api_response")
        return result
    result["raw_response"] = response
    result["usage"] = response.get("usage")
    result["token_counts"], result["accounting_valid"] = _counts(
        result["usage"], thinking, budget
    )
    if not result["accounting_valid"]:
        issues.append("missing_or_inconsistent_token_usage")
    elif result["token_counts"]["message_output_tokens"] > 512:
        issues.append("message_exceeds_512_tokens")
    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        issues.append("invalid_choices")
        return result
    choice = choices[0]
    if not isinstance(choice, dict) or not isinstance(choice.get("message"), dict):
        issues.append("invalid_message")
        return result
    message = choice["message"]
    result["finish_reason"] = choice.get("finish_reason")
    result["content"] = message.get("content")
    result["reasoning_content"] = message.get("reasoning_content")
    if choice.get("finish_reason") != "stop":
        issues.append("incomplete_response")
    if message.get("role") != "assistant" or message.get("tool_calls"):
        issues.append("unexpected_role_or_tools")
    if message.get("reasoning_content") is not None and not isinstance(
        message["reasoning_content"], str
    ):
        issues.append("invalid_reasoning_content")
    if thinking == "disabled" and message.get("reasoning_content"):
        issues.append("unexpected_reasoning_content")
    if not isinstance(result["content"], str) or not result["content"].strip():
        issues.append("empty_or_invalid_content")
        return result
    try:
        answer = parse_json(result["content"])
    except (ValueError, RecursionError):
        issues.append("invalid_rating_json")
        return result
    ensure_no_secret(answer, key)
    if not isinstance(answer, dict) or set(answer) != {"ratings"}:
        issues.append("invalid_rating_schema")
        return result
    ratings = answer["ratings"]
    expected = {item["id"] for item in statements}
    seen = set()
    if not isinstance(ratings, list) or len(ratings) != len(statements):
        issues.append("incorrect_rating_count")
        return result
    for rating in ratings:
        if (
            not isinstance(rating, dict)
            or set(rating) != {"id", "score"}
            or not isinstance(rating["id"], str)
            or rating["id"] not in expected
            or rating["id"] in seen
            or not isinstance(rating["score"], str)
            or rating["score"] not in LIKERT_RESPONSES
        ):
            issues.append("invalid_statement_id_or_score")
            return result
        seen.add(rating["id"])
    by_id = {item["id"]: item for item in ratings}
    result["ratings"] = [by_id[item["id"]] for item in statements]
    return result


def aggregate(attempts: List[Dict[str, Any]]) -> Dict[str, Any]:
    totals = {}
    for field in COUNT_FIELDS:
        values = [attempt.get("token_counts", {}).get(field) for attempt in attempts]
        totals[field] = (
            sum(values) if all(_integer(value) for value in values) else None
        )
    totals["accounting_complete"] = bool(attempts) and all(
        attempt.get("accounting_valid", False) for attempt in attempts
    )
    return totals
