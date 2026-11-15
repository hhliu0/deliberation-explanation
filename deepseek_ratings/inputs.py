"""Strict, safe YAML inputs; no application input-token limit."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .api import RatingError


class InputLoader(yaml.SafeLoader):
    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise RatingError(
                "YAML aliases are unsupported; use explicit input values."
            )
        return super().compose_node(parent, index)


def _mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result:
            raise RatingError("YAML mapping keys must be unique strings.")
        result[key] = loader.construct_object(value_node)
    return result


InputLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def _load(path: Path, field: str) -> Dict[str, Any]:
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=InputLoader)
    except (OSError, UnicodeError, yaml.YAMLError, RecursionError):
        raise RatingError("Cannot read valid UTF-8 input YAML.") from None
    if (
        not isinstance(data, dict)
        or set(data) != {"version", field}
        or type(data["version"]) is not int
        or data["version"] != 1
    ):
        raise RatingError(
            "Input YAML needs version: 1 and the expected data field only."
        )
    return data


def _text(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        value.encode("utf-8")
    except UnicodeError:
        return False
    return True


def load_inputs(
    personas_path: Path, statements_path: Path, persona_id: Optional[str]
) -> Tuple[str, Dict[str, str], List[Dict[str, str]]]:
    agents = _load(personas_path, "agents")["agents"]
    if not isinstance(agents, dict) or not agents:
        raise RatingError("agents must be a nonempty mapping of persona IDs.")
    for identifier, persona in agents.items():
        if (
            not _text(identifier)
            or not isinstance(persona, dict)
            or set(persona) != {"name", "system_prompt"}
            or not all(_text(value) for value in persona.values())
        ):
            raise RatingError(
                "Each persona needs a nonempty ID, name, and system_prompt."
            )
    if persona_id is None:
        if len(agents) != 1:
            raise RatingError(
                "Use --persona to select one of the personas in the file."
            )
        persona_id = next(iter(agents))
    if persona_id not in agents:
        raise RatingError("The selected persona ID is not in the personas file.")
    statements = _load(statements_path, "statements")["statements"]
    if not isinstance(statements, list) or not statements:
        raise RatingError("statements must be a nonempty list of id/text mappings.")
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
    return persona_id, agents[persona_id], statements
