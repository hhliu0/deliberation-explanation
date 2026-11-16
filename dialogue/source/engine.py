"""Dialogue setup, request construction, response validation, and turn scheduling."""

import copy
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

from . import api, inputs, records, reporting, usage
from .api import DialogueError
from .inputs import GENERATION

AGENTS = ("agent_a", "agent_b")
LABELS = {"agent_a": "Agent A", "agent_b": "Agent B"}
PEER_LIMIT = 512
FORMAT_VERSION = 2


def _check_limit(value: int) -> None:
    """Reject message limits that are not positive integers."""
    if not usage.is_integer(value) or value == 0:
        raise DialogueError("The message limit must be a positive integer.")


def _response(
    raw: Dict[str, Any], generation: Optional[Dict[str, Any]] = None
) -> Tuple[Dict[str, Any], Optional[str]]:
    """Record response details and return any reason it cannot be delivered."""
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
    bound = usage.delivery_bound(record["usage"], generation)
    if bound is None:
        return record, "missing_or_inconsistent_usage"
    record["non_reasoning_token_bound"] = bound
    if bound > PEER_LIMIT:
        return record, "peer_message_exceeds_512_tokens"
    return record, None


def _generation(state: Dict[str, Any], agent: str) -> Dict[str, Any]:
    """Read an agent's generation settings from the current run."""
    config = state["settings"]["agents"][agent]["model_config"]
    return {key: value for key, value in config.items() if key != "model"}


def blend_memory(initial: str, messages: Iterable[Tuple[str, str]]) -> str:
    """Append accepted, speaker-labeled replies without marking a memory boundary."""
    transcript = "\n\n".join(
        "[" + speaker + "]\n" + content for speaker, content in messages
    )
    return initial + ("\n\n" if initial and transcript else "") + transcript


def _memory(state: Dict[str, Any], agent: str) -> str:
    """Combine the agent's initial memory with all accepted, speaker-labeled replies."""
    return blend_memory(
        state["settings"]["agents"][agent]["inputs"]["memory"],
        ((item["sender"], item["content"]) for item in state["messages"]),
    )


def _payload(state: Dict[str, Any], agent: str) -> Dict[str, Any]:
    """Build the API request from one agent's inputs and accepted dialogue."""
    settings = state["settings"]["agents"][agent]
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


def _execute(
    state: Dict[str, Any], path: Path, keys: Dict[str, str], emit: Callable[[str], None]
) -> Path:
    """Alternate agent requests, saving each attempt and stopping on errors or limits."""
    pending = None
    interrupted = False
    try:
        records.save(path, state, keys)
        emit("Chat ID: " + state["trial_id"])
        emit("Saved trial: " + str(path.resolve()))
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
                "started_at": records.now(),
                "status": "in_flight",
            }
            state["attempts"].append(pending)
            records.save(path, state, keys)
            emit(LABELS[agent] + " is replying...")
            try:
                raw = api.complete(_payload(state, agent), keys[agent])
                api.ensure_no_keys(raw, keys)
                record, failure = _response(raw, _generation(state, agent))
                pending["response"] = record
                pending["finished_at"] = records.now()
                if failure:
                    pending["status"] = "rejected"
                    pending["error_code"] = failure
                    state["status"] = "stopped"
                    records.save(path, state, keys)
                    emit(
                        "Stopped: "
                        + failure
                        + ". No message was delivered to the counterpart."
                    )
                    emit(reporting.usage_text(record["usage"]))
                    break
                pending["status"] = "accepted"
                state["messages"].append(
                    {
                        "sender": agent,
                        "content": record["content"],
                        "message_id": pending["message_id"],
                    }
                )
                records.save(path, state, keys)
                emit("\n" + LABELS[agent] + ":\n" + record["content"])
                emit(reporting.usage_text(record["usage"]))
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
                pending["finished_at"] = records.now()
                state["status"] = "stopped"
                records.save(path, state, keys)
                emit("Stopped: " + str(error))
                break
            except DialogueError:
                # A response containing a credential is never retained, even in diagnostics.
                if pending is not None and "response" not in pending:
                    pending["status"] = "error"
                    pending["error_code"] = "credential_in_response"
                    state["status"] = "stopped"
                    records.save(path, state, keys)
                raise
        else:
            state["status"] = "completed"
            records.save(path, state, keys)
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
        state["status"] = "stopped"
        state.setdefault("interruption_notes", []).append(
            {
                "stopped_at": records.now(),
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
        records.save(path, state, keys)
        emit(
            "\nStopped by Ctrl+C. An interrupted request may still be billed by DeepSeek."
        )
    reporting.summary(state, emit, AGENTS, LABELS)
    emit("Trial " + state["status"] + ". Saved: " + str(path.resolve()))
    if interrupted:
        raise KeyboardInterrupt()
    if state["status"] != "completed":
        raise DialogueError(
            "The trial stopped early. Read the saved JSON file for details."
        )
    return path


def run_dialogue(
    agent_a_path: Path,
    agent_b_path: Path,
    max_messages: int,
    keys_file: Path,
    output_dir: Path,
    emit: Callable[[str], None],
    trial_name: str,
    thinking: str,
) -> Path:
    """Load both agents, create a fresh run record, and execute the dialogue."""
    _check_limit(max_messages)
    if not isinstance(trial_name, str) or not trial_name.strip():
        raise DialogueError("The trial name must be nonblank text.")
    if thinking not in ("enabled", "disabled"):
        raise DialogueError("Choose whether to enable thinking for this trial.")
    agents = {
        "agent_a": inputs.load_agent(agent_a_path, thinking),
        "agent_b": inputs.load_agent(agent_b_path, thinking),
    }
    keys = api.load_keys(keys_file)
    state = {
        "format_version": FORMAT_VERSION,
        "trial_id": uuid.uuid4().hex,
        "created_at": records.now(),
        "ended_at": None,
        "trial_name": trial_name,
        "status": "running",
        "settings": {
            "agents": agents,
            "thinking_override": thinking,
            "memory_format": "blended",
            "peer_max_tokens": PEER_LIMIT,
        },
        "target_message_count": max_messages,
        "messages": [],
        "attempts": [],
        "interruption_notes": [],
    }
    api.ensure_no_keys(state, keys)
    path = records.reserve(output_dir, state, keys)
    with records.run_lock(path):
        return _execute(state, path, keys, emit)
