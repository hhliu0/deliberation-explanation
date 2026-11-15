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


def now() -> str:
    """Return the current UTC time as an ISO 8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


def save(path: Path, state: Dict[str, Any], keys: Dict[str, str]) -> None:
    """Timestamp and check the state for credentials, then atomically save its JSON."""
    state["updated_at"] = now()
    api.ensure_no_keys(state, keys)
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
            json.dump(state, stream, ensure_ascii=False, indent=2)
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


def reserve(output_dir: Path, state: Dict[str, Any], keys: Dict[str, str]) -> Path:
    """Create a new owner-only run file and save its initial snapshot."""
    api.ensure_no_keys(str(output_dir), keys)
    try:
        output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = output_dir / (state["trial_id"] + ".json")
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
