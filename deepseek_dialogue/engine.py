"""Dialogue scheduling, strict delivery limits, and local run records."""

import copy
import json
import os
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from . import api, inputs
from .api import DialogueError
from .inputs import GENERATION, GENERATION_DISABLED

AGENTS = ("agent_a", "agent_b")
LABELS = {"agent_a": "Agent A", "agent_b": "Agent B"}
PEER_LIMIT = 512
FORMAT_VERSION = 2
RESUME_TARGET = 20


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _integer(value: Any) -> bool:
    return type(value) is int and value >= 0


def _check_limit(value: int) -> None:
    if not _integer(value) or value == 0:
        raise DialogueError("The message limit must be a positive integer.")


def _usage(raw: Any) -> Dict[str, Any]:
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
        if _integer(raw.get(key)):
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
                if _integer(details.get(field))
            }
    return result


def _delivery_bound(
    usage: Dict[str, Any], generation: Optional[Dict[str, Any]] = None
) -> Optional[int]:
    generation = GENERATION if generation is None else generation
    usage = _usage(usage)
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    total = usage.get("total_tokens")
    details = usage.get("completion_tokens_details", {})
    reasoning = details.get("reasoning_tokens") if isinstance(details, dict) else None
    disabled = generation["thinking"]["type"] == "disabled"
    if reasoning is None and disabled:
        reasoning = 0
    if not all(_integer(n) for n in (prompt, completion, total, reasoning)):
        return None
    if disabled and reasoning != 0:
        return None
    if reasoning > completion or completion > generation["max_tokens"]:
        return None
    if total != prompt + completion:
        return None
    return completion - reasoning


def _response(
    raw: Dict[str, Any], generation: Optional[Dict[str, Any]] = None
) -> Tuple[Dict[str, Any], Optional[str]]:
    generation = GENERATION if generation is None else generation
    record = {
        "word_counts": {"message": None, "thinking": None},
        "usage": (
            copy.deepcopy(raw.get("usage"))
            if isinstance(raw.get("usage"), dict)
            else {}
        ),
    }
    for field in ("id", "model", "system_fingerprint"):
        if isinstance(raw.get(field), str):
            record[field] = raw[field]
    choices = raw.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        return record, "invalid_choices"
    choice = choices[0]
    if not isinstance(choice, dict) or not isinstance(choice.get("message"), dict):
        return record, "invalid_message"
    message = choice["message"]
    for field in ("content", "reasoning_content"):
        if isinstance(message.get(field), str):
            record[field] = message[field]
    record["word_counts"] = {
        "message": len(record["content"].split()) if "content" in record else None,
        "thinking": (
            len(record["reasoning_content"].split())
            if "reasoning_content" in record
            else None
        ),
    }
    if isinstance(choice.get("finish_reason"), str):
        record["finish_reason"] = choice["finish_reason"]
    if message.get("role") != "assistant" or message.get("tool_calls"):
        return record, "unexpected_role_or_tool_call"
    if choice.get("finish_reason") != "stop":
        return record, "incomplete_response"
    if not record.get("content", "").strip():
        return record, "empty_final_message"
    if generation["thinking"]["type"] == "disabled" and record.get("reasoning_content"):
        return record, "unexpected_reasoning_content"
    bound = _delivery_bound(record["usage"], generation)
    if bound is None:
        return record, "missing_or_inconsistent_usage"
    record["non_reasoning_token_bound"] = bound
    if bound > PEER_LIMIT:
        return record, "peer_message_exceeds_512_tokens"
    return record, None


def _generation(state: Dict[str, Any], agent: str) -> Dict[str, Any]:
    if state["format_version"] == 1:
        return state["settings"]["generation"]
    config = state["settings"]["agents"][agent]["model_config"]
    return {key: value for key, value in config.items() if key != "model"}


def _memory(state: Dict[str, Any], agent: str) -> str:
    """Rebuild memory exactly once per accepted turn, including the opening turn."""
    initial = state["settings"]["agents"][agent]["inputs"]["memory"]
    transcript = "\n\n".join(
        "[" + item["sender"] + "]\n" + item["content"] for item in state["messages"]
    )
    return "Initial memory:\n" + initial + "\n\nDialogue so far:\n" + transcript


def _payload(state: Dict[str, Any], agent: str) -> Dict[str, Any]:
    """Assemble five file-backed parts; accepted public replies extend memory."""
    settings = state["settings"]["agents"][agent]
    if state["format_version"] == 1:
        # Resume historical runs with their original request structure.
        messages = [{"role": "system", "content": settings["prompt"]}]
        messages.extend(
            {"role": "assistant", "name": item["sender"], "content": item["content"]}
            for item in state["messages"]
        )
        return {
            "model": settings["model"],
            **copy.deepcopy(_generation(state, agent)),
            "messages": messages,
            "stream": False,
        }

    parts = settings["inputs"]
    model_config = copy.deepcopy(settings["model_config"])  # 1. API settings
    persona = parts["persona"]  # 2. This agent's identity and perspective
    memory = _memory(state, agent)  # 3. Initial memory plus accepted turns
    statements = parts["statements"]  # 4. The discussion target(s)
    starting_prompt = parts["starting_prompt"]  # 5. Discussion instructions
    return {
        **model_config,
        "messages": [
            {"role": "system", "content": persona},
            {
                "role": "user",
                "content": "Memory:\n"
                + memory
                + "\n\nStatements:\n"
                + statements
                + "\n\nStarting prompt for discussion:\n"
                + starting_prompt,
            },
        ],
        "stream": False,
    }


def _save_memory(path: Path, state: Dict[str, Any]) -> None:
    """Export derived memory after the authoritative JSON snapshot is saved."""
    if state["format_version"] == 1:
        return
    directory = path.parent / "archive" / path.stem
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    for agent in AGENTS:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=directory,
                prefix=".memory-",
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                stream.write(_memory(state, agent))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(str(temporary), str(directory / (agent + ".memory.txt")))
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()


def _save(path: Path, state: Dict[str, Any], keys: Dict[str, str]) -> None:
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
        _save_memory(path, state)
    except OSError:
        raise DialogueError(
            "Cannot save the run. No further requests will be made; retain the last saved snapshot."
        ) from None
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _reserve(output_dir: Path, state: Dict[str, Any], keys: Dict[str, str]) -> Path:
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
    _save(path, state, keys)
    return path


def _chat_path(chat_id: str, output_dir: Path) -> Path:
    reference = chat_id.strip()
    if not reference:
        raise DialogueError("Enter a chat ID or saved JSON path.")
    if Path(reference).suffix.lower() == ".json":
        return Path(reference)
    try:
        identifier = uuid.UUID(reference).hex
    except ValueError:
        raise DialogueError("Enter a valid chat ID or saved JSON path.") from None
    return output_dir / (identifier + ".json")


@contextmanager
def _chat_lock(path: Path):
    """Prevent two local commands from overwriting the same conversation."""
    lock = path.with_suffix(path.suffix + ".lock")
    try:
        descriptor = os.open(str(lock), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise DialogueError(
            "This chat is locked by another command. If that process has exited, "
            "remove the adjacent .json.lock file before resuming."
        ) from None
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(str(os.getpid()) + "\n")
        yield
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def _read_state(path: Path) -> Dict[str, Any]:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(state, dict) or state.get("format_version") not in (1, 2):
            raise ValueError()
        if not isinstance(state["trial_id"], str):
            raise ValueError()
        settings = state["settings"]
        if settings["peer_max_tokens"] != PEER_LIMIT:
            raise ValueError()
        for agent in AGENTS:
            agent_config = settings["agents"][agent]
            if state["format_version"] == 1:
                if settings["generation"] not in (GENERATION, GENERATION_DISABLED):
                    raise ValueError()
                for field in ("prompt", "model"):
                    if (
                        not isinstance(agent_config[field], str)
                        or not agent_config[field].strip()
                    ):
                        raise ValueError()
            else:
                inputs.validate_parts(agent_config["inputs"])
                expected = inputs.model_config(
                    agent_config["inputs"]["model_config"],
                    settings["thinking_override"],
                )
                if agent_config["model_config"] != expected:
                    raise ValueError()
        if not isinstance(state["messages"], list) or not isinstance(
            state["attempts"], list
        ):
            raise ValueError()
        if not isinstance(state.get("interruption_notes", []), list):
            raise ValueError()
        if not isinstance(state.get("resume_notes", []), list):
            raise ValueError()
        attempts = {}
        for attempt in state["attempts"]:
            if not isinstance(attempt, dict) or attempt["agent"] not in AGENTS:
                raise ValueError()
            if (
                not isinstance(attempt["message_id"], str)
                or attempt["message_id"] in attempts
            ):
                raise ValueError()
            if not isinstance(attempt["trial_id"], str):
                raise ValueError()
            if attempt["status"] not in (
                "in_flight",
                "unknown",
                "accepted",
                "rejected",
                "error",
            ):
                raise ValueError()
            if "response" in attempt and not isinstance(attempt["response"], dict):
                raise ValueError()
            attempts[attempt["message_id"]] = attempt
        accepted_ids = [
            attempt["message_id"]
            for attempt in state["attempts"]
            if attempt["status"] == "accepted"
        ]
        message_ids = [item["message_id"] for item in state["messages"]]
        if accepted_ids != message_ids:
            raise ValueError()
        for index, item in enumerate(state["messages"]):
            if item["sender"] != AGENTS[index % 2]:
                raise ValueError()
            if not isinstance(item["content"], str) or not item["content"].strip():
                raise ValueError()
            attempt = attempts[item["message_id"]]
            result = attempt["response"]
            if (
                attempt["status"] != "accepted"
                or attempt["agent"] != item["sender"]
                or result.get("content") != item["content"]
                or result.get("finish_reason") != "stop"
            ):
                raise ValueError()
            bound = _delivery_bound(
                _usage(result.get("usage")), _generation(state, item["sender"])
            )
            if bound is None or bound > PEER_LIMIT:
                raise ValueError()
        return state
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, DialogueError):
        raise DialogueError(
            "Cannot read this run: it is unreadable, incomplete, or incompatible."
        ) from None


def _usage_text(usage: Dict[str, Any]) -> str:
    usage = _usage(usage)

    def count(value: Any) -> str:
        return str(value) if _integer(value) else "unknown"

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
    bound = _delivery_bound(usage)
    if bound is not None:
        text += ", non-reasoning bound=" + str(bound)
    return text


def _summary(state: Dict[str, Any], emit: Callable[[str], None]) -> None:
    fields = (
        "prompt_tokens",
        "completion_tokens",
        "reasoning_tokens",
        "total_tokens",
        "prompt_cache_hit_tokens",
        "prompt_cache_miss_tokens",
    )
    for agent in (*AGENTS, "all", "current_trial"):
        attempts = [
            a
            for a in state["attempts"]
            if agent == "all"
            or a["agent"] == agent
            or (agent == "current_trial" and a["trial_id"] == state["trial_id"])
        ]
        labels = ("input", "output", "thinking", "total", "cache hit", "cache miss")
        chunks = []
        for field, label in zip(fields, labels):
            known = []
            for attempt in attempts:
                usage = _usage(attempt.get("response", {}).get("usage"))
                value = (
                    usage.get("completion_tokens_details", {}).get(field)
                    if field == "reasoning_tokens"
                    else usage.get(field)
                )
                if _integer(value):
                    known.append(value)
            missing = len(attempts) - len(known)
            value_text = str(sum(known)) if known or not attempts else "unknown"
            if missing and known:
                value_text += " (+ " + str(missing) + " unknown requests)"
            chunks.append(label + "=" + value_text)
        label = (
            "Whole history"
            if agent == "all"
            else ("Current trial" if agent == "current_trial" else LABELS[agent])
        )
        emit(
            label
            + " totals (local, "
            + str(len(attempts))
            + " requests): "
            + ", ".join(chunks)
        )


def _execute(
    state: Dict[str, Any], path: Path, keys: Dict[str, str], emit: Callable[[str], None]
) -> Path:
    pending = None
    interrupted = False
    try:
        _save(path, state, keys)
        emit("Chat ID: " + state["trial_id"])
        emit("Saved trial: " + str(path.resolve()))
        if state["format_version"] == 2:
            emit(
                "Memory archive: "
                + str((path.parent / "archive" / path.stem).resolve())
            )
        emit(
            "Progress: "
            + str(len(state["messages"]))
            + "/"
            + str(state["target_message_count"])
            + " messages"
        )
        while len(state["messages"]) < state["target_message_count"]:
            agent = AGENTS[len(state["messages"]) % 2]
            pending = {
                "message_id": uuid.uuid4().hex,
                "trial_id": state["trial_id"],
                "agent": agent,
                "started_at": now(),
                "status": "in_flight",
            }
            state["attempts"].append(pending)
            _save(path, state, keys)
            emit(LABELS[agent] + " is thinking...")
            try:
                raw = api.complete(_payload(state, agent), keys[agent])
                api.ensure_no_keys(raw, keys)
                record, failure = _response(raw, _generation(state, agent))
                pending["response"] = record
                pending["finished_at"] = now()
                if failure:
                    pending["status"] = "rejected"
                    pending["error_code"] = failure
                    state["status"] = "paused"
                    _save(path, state, keys)
                    emit(
                        "Paused: "
                        + failure
                        + ". No message was delivered to the counterpart."
                    )
                    emit(_usage_text(record["usage"]))
                    break
                pending["status"] = "accepted"
                state["messages"].append(
                    {
                        "sender": agent,
                        "content": record["content"],
                        "message_id": pending["message_id"],
                    }
                )
                _save(path, state, keys)
                emit("\n" + LABELS[agent] + ":\n" + record["content"])
                emit(_usage_text(record["usage"]))
                emit(
                    "Words (local): message="
                    + str(record["word_counts"]["message"])
                    + ", thinking="
                    + str(record["word_counts"]["thinking"])
                )
                emit(
                    "Progress: "
                    + str(len(state["messages"]))
                    + "/"
                    + str(state["target_message_count"])
                    + " messages"
                )
                pending = None
            except api.APIError as error:
                pending["status"] = "unknown" if error.uncertain else "error"
                pending["error_code"] = error.code
                pending["finished_at"] = now()
                state["status"] = "paused"
                _save(path, state, keys)
                emit("Paused: " + str(error))
                break
            except DialogueError:
                # A response containing a credential is never retained, even in diagnostics.
                if pending is not None and "response" not in pending:
                    pending["status"] = "error"
                    pending["error_code"] = "credential_in_response"
                    state["status"] = "paused"
                    _save(path, state, keys)
                raise
        else:
            state["status"] = "completed"
            _save(path, state, keys)
    except KeyboardInterrupt:
        interrupted = True
        if (
            pending is not None
            and pending["status"] == "accepted"
            and not any(
                item["message_id"] == pending["message_id"]
                for item in state["messages"]
            )
        ):
            pending["status"] = "unknown"
            pending["error_code"] = "interrupted_before_acceptance"
        if pending is not None and pending["status"] == "in_flight":
            pending["status"] = "unknown"
            pending["error_code"] = "interrupted_request"
        state["status"] = "paused"
        state.setdefault("interruption_notes", []).append(
            {
                "stopped_at": now(),
                "after_message_count": len(state["messages"]),
                "after_message_id": (
                    state["messages"][-1]["message_id"] if state["messages"] else None
                ),
                "pending_message_id": (
                    pending["message_id"]
                    if pending is not None and pending["status"] == "unknown"
                    else None
                ),
                "remark": "Stopped here by Ctrl+C after "
                + str(len(state["messages"]))
                + " accepted messages.",
            }
        )
        _save(path, state, keys)
        emit(
            "\nPaused by Ctrl+C. An interrupted request may still be billed by DeepSeek."
        )
    _summary(state, emit)
    emit("Trial " + state["status"] + ". Saved: " + str(path.resolve()))
    if interrupted:
        raise KeyboardInterrupt()
    if state["status"] != "completed":
        raise DialogueError(
            "The trial is paused. Inspect the saved JSON before resuming."
        )
    return path


def run_dialogue(
    agent_a_path: Path,
    agent_b_path: Path,
    max_messages: int,
    keys_file: Path,
    output_dir: Path,
    emit: Callable[[str], None],
    thinking: Optional[str] = None,
) -> Path:
    _check_limit(max_messages)
    agents = {
        "agent_a": inputs.load_agent(agent_a_path, thinking),
        "agent_b": inputs.load_agent(agent_b_path, thinking),
    }
    keys = api.load_keys(keys_file)
    state = {
        "format_version": FORMAT_VERSION,
        "trial_id": uuid.uuid4().hex,
        "parent_trial_id": None,
        "created_at": now(),
        "status": "running",
        "settings": {
            "agents": agents,
            "thinking_override": thinking,
            "peer_max_tokens": PEER_LIMIT,
        },
        "new_message_limit": max_messages,
        "initial_message_count": 0,
        "target_message_count": max_messages,
        "messages": [],
        "attempts": [],
        "interruption_notes": [],
        "resume_notes": [],
    }
    api.ensure_no_keys(state, keys)
    path = _reserve(output_dir, state, keys)
    with _chat_lock(path):
        return _execute(state, path, keys, emit)


def resume_dialogue(
    chat_id: str,
    keys_file: Path,
    output_dir: Path,
    emit: Callable[[str], None],
) -> Path:
    path = _chat_path(chat_id, output_dir)
    with _chat_lock(path):
        state = _read_state(path)
        count = len(state["messages"])
        if count >= RESUME_TARGET:
            try:
                _save_memory(path, state)
            except OSError:
                raise DialogueError(
                    "Cannot rebuild the memory archive. No API requests were made."
                ) from None
            emit(
                "Chat already has "
                + str(count)
                + " messages; target is 20. No API requests made."
            )
            emit("Saved chat: " + str(path.resolve()))
            return path
        keys = api.load_keys(keys_file)
        api.ensure_no_keys(state, keys)
        previous_status = state.get("status", "unknown")
        state["status"] = "running"
        state["resumed_at"] = now()
        state.setdefault("resume_notes", []).append(
            {
                "resumed_at": state["resumed_at"],
                "after_message_count": count,
                "after_message_id": (
                    state["messages"][-1]["message_id"] if state["messages"] else None
                ),
                "previous_status": previous_status,
                "remark": "This chat stopped here at "
                + str(count)
                + " accepted messages before continuing toward 20.",
            }
        )
        state["initial_message_count"] = count
        state["new_message_limit"] = RESUME_TARGET - count
        state["target_message_count"] = RESUME_TARGET
        state.setdefault("interruption_notes", [])
        for attempt in state["attempts"]:
            if attempt["status"] == "in_flight":
                attempt["status"] = "unknown"
                attempt["error_code"] = "previous_process_ended"
        return _execute(state, path, keys, emit)


def inspect_run(
    run_path: Path, show_thinking: bool, emit: Callable[[str], None]
) -> None:
    state = _read_state(run_path)
    emit(
        "Chat: " + state["trial_id"] + " (" + str(state.get("status", "unknown")) + ")"
    )
    for note in state.get("interruption_notes", []):
        if isinstance(note, dict):
            emit(
                "Interruption: "
                + str(note.get("remark", "Stopped here."))
                + " At: "
                + str(note.get("stopped_at", "unknown"))
            )
    for number, attempt in enumerate(state["attempts"], 1):
        emit(
            "\nRequest "
            + str(number)
            + " — "
            + LABELS[attempt["agent"]]
            + " ["
            + attempt["status"]
            + "]"
        )
        record = attempt.get("response", {})
        emit("Message ID: " + attempt["message_id"])
        if isinstance(record.get("content"), str):
            emit(record["content"])
        if show_thinking:
            emit(
                "Thinking (local only):\n"
                + str(record.get("reasoning_content", "Not returned."))
            )
        emit(_usage_text(_usage(record.get("usage"))))
        counts = record.get("word_counts", {})
        if isinstance(counts, dict):
            emit(
                "Words (local): message="
                + str(counts.get("message", "unknown"))
                + ", thinking="
                + str(counts.get("thinking", "unknown"))
            )
        if isinstance(attempt.get("error_code"), str):
            emit("Outcome: " + attempt["error_code"])
    _summary(state, emit)
