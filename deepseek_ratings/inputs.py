"""Load five plain-text rating inputs with strict model and statement validation."""

import copy
from pathlib import Path
from typing import Any, Dict, List

from .api import RatingError
from .response import parse_json

AGENTS = {"agent_a": "Agent A", "agent_b": "Agent B"}
FILES = {
    "model_config": "model-config.txt",
    "persona": "persona.txt",
    "memory": "memory.txt",
    "statements": "statements.txt",
    "starting_prompt": "starting-prompt.txt",
}
GENERATION = {
    "thinking": {"type": "enabled"},
    "reasoning_effort": "high",
    "max_tokens": 8192,
}
GENERATION_DISABLED = {"thinking": {"type": "disabled"}, "max_tokens": 512}


def _text(value: Any) -> bool:
    """Check for nonblank text that can be encoded as UTF-8."""
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        value.encode("utf-8")
    except UnicodeError:
        return False
    return True


def model_config(text: str, thinking: str) -> Dict[str, Any]:
    """Validate JSON model settings and apply the selected thinking profile."""
    try:
        config = parse_json(text)
        if not isinstance(config, dict) or not _text(config.get("model")):
            raise ValueError()
        generation = {key: value for key, value in config.items() if key != "model"}
        if type(config.get("max_tokens")) is not int or generation not in (
            GENERATION,
            GENERATION_DISABLED,
        ):
            raise ValueError()
        if thinking not in ("enabled", "disabled"):
            raise ValueError()
        effective = GENERATION if thinking == "enabled" else GENERATION_DISABLED
        return {"model": config["model"], **copy.deepcopy(effective)}
    except (ValueError, TypeError, RecursionError):
        raise RatingError(
            "Invalid model-config.txt: use a model name and either thinking enabled, "
            "reasoning_effort high, max_tokens 8192; or thinking disabled, max_tokens 512."
        ) from None


def parse_statements(text: str) -> List[Dict[str, str]]:
    """Read statement IDs and text from JSON, rejecting duplicates and extra fields."""
    try:
        data = parse_json(text)
    except (ValueError, TypeError, RecursionError):
        raise RatingError("statements.txt must contain valid JSON.") from None
    if not isinstance(data, dict) or set(data) != {"statements"}:
        raise RatingError(
            "statements.txt needs only a statements list of id/text pairs."
        )
    statements = data["statements"]
    if not isinstance(statements, list) or not statements:
        raise RatingError("statements must be a nonempty list of id/text pairs.")
    identifiers = set()
    for item in statements:
        if (
            not isinstance(item, dict)
            or set(item) != {"id", "text"}
            or not all(_text(value) for value in item.values())
            or item["id"] in identifiers
        ):
            raise RatingError(
                "Each statement needs a unique nonempty string id and text."
            )
        identifiers.add(item["id"])
    return statements


def load_agent(directory: Path, thinking: str) -> Dict[str, Any]:
    """Read one agent's five files and validate its model settings and statements."""
    parts = {}
    for part, filename in FILES.items():
        try:
            text = (directory / filename).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            raise RatingError(
                "Cannot read " + filename + " in the selected agent directory as UTF-8."
            ) from None
        if part != "memory" and not _text(text):
            raise RatingError("Only memory.txt may be blank.")
        parts[part] = text
    return {
        "inputs": parts,
        "model_config": model_config(parts["model_config"], thinking),
        "statements": parse_statements(parts["statements"]),
    }
