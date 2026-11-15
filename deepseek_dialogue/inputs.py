"""Load the five plain-text inputs for one dialogue participant."""

import copy
import json
from pathlib import Path
from typing import Any, Dict, Optional

from .api import DialogueError

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


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate configuration key.")
        result[key] = value
    return result


def model_config(text: str, thinking: Optional[str] = None) -> Dict[str, Any]:
    """Parse API parameters, never executable code or arbitrary payload overrides."""
    try:
        config = json.loads(text, object_pairs_hook=_unique_pairs)
        if not isinstance(config, dict):
            raise ValueError()
        model = config.get("model")
        if not isinstance(model, str) or not model.strip():
            raise ValueError()
        generation = {key: value for key, value in config.items() if key != "model"}
        # Retain the two established generation profiles and delivery limit.
        if type(config.get("max_tokens")) is not int or generation not in (
            GENERATION,
            GENERATION_DISABLED,
        ):
            raise ValueError()
        if thinking is not None:
            if thinking not in ("enabled", "disabled"):
                raise ValueError()
            generation = GENERATION if thinking == "enabled" else GENERATION_DISABLED
        return {"model": model, **copy.deepcopy(generation)}
    except (ValueError, TypeError):
        raise DialogueError(
            "Invalid model-config.txt: use a model name and either thinking enabled, "
            "reasoning_effort high, max_tokens 8192; or thinking disabled, max_tokens 512."
        ) from None


def validate_parts(parts: Any) -> None:
    if not isinstance(parts, dict) or set(parts) != set(FILES):
        raise DialogueError("Each agent needs exactly five input parts.")
    for part, text in parts.items():
        if not isinstance(text, str) or (part != "memory" and not text.strip()):
            raise DialogueError("Only the starting memory may be empty.")


def load_agent(directory: Path, thinking: Optional[str] = None) -> Dict[str, Any]:
    parts = {}
    for part, filename in FILES.items():
        try:
            parts[part] = (directory / filename).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            raise DialogueError(
                "Cannot read " + filename + " in the selected agent directory as UTF-8."
            ) from None
    validate_parts(parts)
    return {
        "inputs": parts,
        "model_config": model_config(parts["model_config"], thinking),
    }
