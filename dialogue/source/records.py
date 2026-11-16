"""Local JSON snapshots, timestamps, and exclusive run-file access."""

import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from . import api
from .api import DialogueError
from .inputs import FILES


def now() -> str:
    """Return the current UTC time as an ISO 8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


def snapshot(state: Dict[str, Any]) -> Dict[str, Any]:
    """Select the ordered trial details, accepted turns, and original input texts."""
    responses = {
        attempt["message_id"]: attempt["response"]
        for attempt in state["attempts"]
        if attempt["status"] == "accepted"
    }
    messages = []
    for message in state["messages"]:
        response = responses[message["message_id"]]
        message_tokens = response["non_reasoning_token_bound"]
        messages.append(
            {
                "speaker": message["sender"],
                "message": message["content"],
                "thinking": response.get("reasoning_content"),
                "message_token_count": message_tokens,
                "thinking_token_count": response["usage"]["completion_tokens"]
                - message_tokens,
            }
        )
    agents = state["settings"]["agents"]
    return {
        "trial_name": state["trial_name"],
        "trial_id": state["trial_id"],
        "started_at": state["created_at"],
        "ended_at": state["ended_at"],
        "thinking": (
            "thinking enabled"
            if state["settings"]["thinking_override"] == "enabled"
            else "not enabled"
        ),
        "messages": messages,
        "agent_a_inputs": {
            filename: agents["agent_a"]["inputs"][part]
            for part, filename in FILES.items()
        },
        "agent_b_inputs": {
            filename: agents["agent_b"]["inputs"][part]
            for part, filename in FILES.items()
        },
    }


def save(path: Path, state: Dict[str, Any], keys: Dict[str, str]) -> None:
    """Timestamp and check the state, then atomically save the selected JSON fields."""
    state["updated_at"] = now()
    if state["status"] in ("completed", "stopped") and state["ended_at"] is None:
        state["ended_at"] = state["updated_at"]
    api.ensure_no_keys(state, keys)
    data = snapshot(state)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=".dialogue-",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(path))
    except OSError:
        raise DialogueError(
            "Cannot save the run. No further requests will be made; retain the last saved snapshot."
        ) from None
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def filename(trial_name: str, trial_id: str) -> str:
    """Build a bounded filename from the readable trial name followed by its ID."""
    prefix = "".join(
        char if char.isprintable() and char not in '<>:"/\\|?*' else "_"
        for char in trial_name
    )
    prefix = prefix.strip(" .").encode("utf-8")[:180].decode("utf-8", errors="ignore")
    prefix = prefix.rstrip(" .") or "trial"
    return prefix + "_" + trial_id + ".json"


def reserve(output_dir: Path, state: Dict[str, Any], keys: Dict[str, str]) -> Path:
    """Create a new owner-only run file and save its initial snapshot."""
    api.ensure_no_keys(str(output_dir), keys)
    path = output_dir / filename(state["trial_name"], state["trial_id"])
    api.ensure_no_keys(str(path), keys)
    try:
        output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
    except OSError:
        raise DialogueError(
            "Cannot create a new run file in the output directory."
        ) from None
    save(path, state, keys)
    return path


@contextmanager
def run_lock(path: Path):
    """Prevent concurrent writers from overwriting the same run."""
    lock = path.with_suffix(path.suffix + ".lock")
    try:
        descriptor = os.open(str(lock), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise DialogueError("This run is locked by another command.") from None
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(str(os.getpid()) + "\n")
        yield
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass
