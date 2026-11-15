"""Durable owner-only YAML snapshots and exclusive rejected-attempt backups."""

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import yaml

from .api import RatingError, ensure_no_secret
from .response import LIKERT_RESPONSES


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RecordDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def _string(dumper, value):
    return dumper.represent_scalar(
        "tag:yaml.org,2002:str", value, style="|" if "\n" in value else None
    )


RecordDumper.add_representer(str, _string)


def _sync_directory(path: Path) -> None:
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


def _write_yaml(path: Path, data: Dict[str, Any]) -> None:
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
            yaml.dump(
                data,
                stream,
                Dumper=RecordDumper,
                allow_unicode=True,
                sort_keys=False,
            )
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(path))
        _sync_directory(path.parent)
    except (OSError, yaml.YAMLError, RecursionError):
        raise RatingError(
            "Cannot save a trial or score file. Stopped; retain the last saved snapshot."
        ) from None
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def save_scores(
    log_path: Path, state: Dict[str, Any], attempt: Dict[str, Any], key: str
) -> Path:
    """Export only the requested metadata and statement/score pairs for one call."""
    number = attempt["number"]
    if type(number) is not int or number < 1:
        raise RatingError("Cannot export scores without a valid call number.")
    path = (
        log_path.parent
        / "scores"
        / (log_path.stem + ".attempt-" + str(number) + ".yaml")
    )
    by_id = {}
    for item in attempt.get("ratings") or []:
        score = item["score"]
        # Only historical format-1 exports translate numbers. New API answers
        # must already contain exact text labels to pass response validation.
        if state.get("format_version") == 1 and type(score) is int and 1 <= score <= 5:
            score = LIKERT_RESPONSES[score - 1]
        if not isinstance(score, str) or score not in LIKERT_RESPONSES:
            raise RatingError("Cannot export an invalid Likert response.")
        by_id[item["id"]] = score
    data = {
        "trial_id": state["trial_id"],
        "created_at": attempt["started_at"],
        "status": "expired" if state["status"] == "expired" else attempt["status"],
        "model": state["request"]["model"],
        "scores": [
            {"statement": item["text"], "score": by_id.get(item["id"])}
            for item in state["statements"]
        ],
    }
    ensure_no_secret(str(path), key)
    ensure_no_secret(data, key)
    try:
        _create_directory(path.parent)
    except OSError:
        raise RatingError("Cannot create the separate scores directory.") from None
    _write_yaml(path, data)
    return path


class TrialStore:
    def __init__(self, output_dir: Path, trial_id: str, key: str):
        self.key = key
        self.path = output_dir / (trial_id + ".yaml")
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
        state["updated_at"] = now()
        ensure_no_secret(state, self.key)
        # Preserve the complete log before producing any derived score files.
        _write_yaml(self.path, state)
        for attempt in state["attempts"]:
            if attempt["status"] != "pending":
                save_scores(self.path, state, attempt, self.key)

    def backup(self, attempt: int) -> Path:
        path = (
            self.path.parent
            / "backups"
            / (self.path.stem + ".attempt-" + str(attempt) + ".yaml")
        )
        try:
            _create_directory(path.parent)
            descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(self.path.read_bytes())
                stream.flush()
                os.fsync(stream.fileno())
            _sync_directory(path.parent)
        except OSError:
            raise RatingError(
                "Cannot durably back up the rejected attempt; no retry."
            ) from None
        return path
