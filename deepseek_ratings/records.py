"""Durable owner-only JSON snapshots containing accepted ratings and input texts."""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .api import RatingError, ensure_no_secret
from .inputs import FILES


def now() -> str:
    """Return the current UTC time as an ISO 8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


def snapshot(state: Dict[str, Any]) -> Dict[str, Any]:
    """Select ordered trial details, accepted output, and original input texts."""
    accepted = next(
        (
            attempt
            for attempt in state["attempts"]
            if attempt["number"] == state["accepted_attempt"]
            and attempt["status"] == "accepted"
        ),
        None,
    )
    ratings = {
        item["id"]: item["score"]
        for item in (state["ratings"] or [])
        if accepted is not None and state["status"] == "completed"
    }
    return {
        "trial_name": state["trial_name"],
        "trial_id": state["trial_id"],
        "started_at": state["created_at"],
        "ended_at": state["finished_at"],
        "thinking": (
            "thinking enabled" if state["thinking"] == "enabled" else "not enabled"
        ),
        "ratings": [
            {"statement": item["text"], "rating": ratings.get(item["id"])}
            for item in state["statements"]
        ],
        "agent_message": {
            "agent_name": state["agent_name"],
            "message": accepted["content"] if accepted is not None else None,
            "thinking": (
                accepted["reasoning_content"] if accepted is not None else None
            ),
            "message_token_count": (
                accepted["token_counts"]["message_output_tokens"]
                if accepted is not None
                else None
            ),
            "thinking_token_count": (
                accepted["token_counts"]["thinking_tokens"]
                if accepted is not None
                else None
            ),
        },
        "inputs": {filename: state["inputs"][part] for part, filename in FILES.items()},
    }


def filename(trial_name: str, trial_id: str) -> str:
    """Build a bounded filename from the readable trial name followed by its ID."""
    prefix = "".join(
        char if char.isprintable() and char not in '<>:"/\\|?*' else "_"
        for char in trial_name
    )
    prefix = prefix.strip(" .").encode("utf-8")[:180].decode("utf-8", errors="ignore")
    prefix = prefix.rstrip(" .") or "trial"
    return prefix + "_" + trial_id + ".json"


def _sync_directory(path: Path) -> None:
    """Flush directory entries after creating or replacing a file."""
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _create_directory(path: Path) -> None:
    """Persist each new directory's entry in its parent before proceeding."""
    if path.is_dir():
        return
    if path.parent != path:
        _create_directory(path.parent)
    path.mkdir(mode=0o700, exist_ok=True)
    _sync_directory(path.parent)


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    """Atomically replace a snapshot and persist its file and directory data."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=".ratings-",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(path))
        _sync_directory(path.parent)
    except (OSError, TypeError, ValueError, RecursionError):
        raise RatingError(
            "Cannot save the trial file. Stopped; retain the last saved snapshot."
        ) from None
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


class TrialStore:
    """Reserve and maintain a single named JSON file for an independent trial."""

    def __init__(self, output_dir: Path, trial_name: str, trial_id: str, key: str):
        """Reserve a unique owner-only file after checking its complete path."""
        self.key = key
        self.path = output_dir / filename(trial_name, trial_id)
        ensure_no_secret(str(self.path), key)
        try:
            _create_directory(output_dir)
            descriptor = os.open(
                str(self.path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
            os.close(descriptor)
        except OSError:
            raise RatingError("Cannot reserve a unique trial file.") from None

    def save(self, state: Dict[str, Any]) -> None:
        """Timestamp and check the full state before saving its JSON projection."""
        state["updated_at"] = now()
        if (
            state["status"] in ("completed", "failed", "interrupted")
            and state["finished_at"] is None
        ):
            state["finished_at"] = state["updated_at"]
        ensure_no_secret(state, self.key)
        _write_json(self.path, snapshot(state))
