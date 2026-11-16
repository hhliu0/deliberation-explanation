"""Terminal token-usage formatting and dialogue summaries."""

from typing import Any, Callable, Dict, Tuple

from .usage import delivery_bound, is_integer, normalize


def usage_text(usage: Dict[str, Any]) -> str:
    """Format one response's token usage for local display."""
    usage = normalize(usage)

    def count(value: Any) -> str:
        """Format a valid token count, or mark it as unknown."""
        return str(value) if is_integer(value) else "unknown"

    reasoning = usage.get("completion_tokens_details", {}).get("reasoning_tokens")
    text = (
        "Usage (local): input="
        + count(usage.get("prompt_tokens"))
        + ", output="
        + count(usage.get("completion_tokens"))
        + ", thinking="
        + count(reasoning)
        + ", total="
        + count(usage.get("total_tokens"))
    )
    for key, label in (
        ("prompt_cache_hit_tokens", "cache hit"),
        ("prompt_cache_miss_tokens", "cache miss"),
    ):
        if key in usage:
            text += ", " + label + "=" + count(usage[key])
    bound = delivery_bound(usage)
    if bound is not None:
        text += ", non-reasoning bound=" + str(bound)
    return text


def summary(
    state: Dict[str, Any],
    emit: Callable[[str], None],
    agents: Tuple[str, ...],
    agent_labels: Dict[str, str],
) -> None:
    """Display token totals per agent and across all attempts, noting missing counts."""
    fields = (
        "prompt_tokens",
        "completion_tokens",
        "reasoning_tokens",
        "total_tokens",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
    )
    for agent in (*agents, "all"):
        attempts = [
            a for a in state["attempts"] if agent == "all" or a["agent"] == agent
        ]
        labels = ("input", "output", "thinking", "total", "cache hit", "cache miss")
        chunks = []
        for field, label in zip(fields, labels):
            known = []
            for attempt in attempts:
                usage = normalize(attempt.get("response", {}).get("usage"))
                value = (
                    usage.get("completion_tokens_details", {}).get(field)
                    if field == "reasoning_tokens"
                    else usage.get(field)
                )
                if is_integer(value):
                    known.append(value)
            missing = len(attempts) - len(known)
            value_text = str(sum(known)) if known or not attempts else "unknown"
            if missing and known:
                value_text += " (+ " + str(missing) + " unknown requests)"
            chunks.append(label + "=" + value_text)
        label = "Whole history" if agent == "all" else agent_labels[agent]
        emit(
            label
            + " totals (local, "
            + str(len(attempts))
            + " requests): "
            + ", ".join(chunks)
        )
