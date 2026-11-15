"""One fresh rating request built from the selected agent's five input files."""

import copy
import uuid
from pathlib import Path
from typing import Any, Callable, Dict

from . import api
from .inputs import AGENTS, load_agent
from .records import TrialStore, now
from .response import aggregate, capture_raw, empty_counts, evaluate


def build_payload(agent: Dict[str, Any]) -> Dict[str, Any]:
    """Build the dialogue-style system/user payload from the five rating inputs."""
    parts = agent["inputs"]
    return {
        **copy.deepcopy(agent["model_config"]),
        "messages": [
            {"role": "system", "content": parts["persona"]},
            {
                "role": "user",
                "content": "Memory:\n"
                + parts["memory"]
                + "\n\nStatements:\n"
                + parts["statements"]
                + "\n\nStarting prompt for discussion:\n"
                + parts["starting_prompt"],
            },
        ],
        "stream": False,
    }


def run(
    agent_id: str,
    input_dir: Path,
    trial_name: str,
    thinking: str,
    keys_file: Path,
    output_dir: Path,
    emit: Callable[[str], None] = print,
) -> Dict[str, Any]:
    """Validate inputs, make one rating request, and save its ordered JSON result."""
    if agent_id not in AGENTS:
        raise api.RatingError("Choose agent_a or agent_b.")
    if not isinstance(trial_name, str) or not trial_name.strip():
        raise api.RatingError("The trial name must be nonblank text.")
    if thinking not in ("enabled", "disabled"):
        raise api.RatingError("Choose whether to enable thinking for this trial.")
    agent = load_agent(input_dir, thinking)
    statements = agent["statements"]
    key = api.load_key(keys_file)
    payload = build_payload(agent)
    state = {
        "trial_id": uuid.uuid4().hex,
        "trial_name": trial_name,
        "created_at": now(),
        "finished_at": None,
        "thinking": thinking,
        "agent_name": AGENTS[agent_id],
        "inputs": agent["inputs"],
        "status": "running",
        "statements": statements,
        "request": payload,
        "attempts": [],
        "accepted_attempt": None,
        "ratings": None,
        "issues": [],
        "token_totals": aggregate([]),
    }
    api.ensure_no_secret(state, key)
    store = TrialStore(output_dir, trial_name, state["trial_id"], key)
    store.save(state)
    current = None
    try:
        emit("Trial: " + state["trial_id"])
        emit("JSON: " + str(store.path.resolve()))
        current = {
            "number": 1,
            "started_at": now(),
            "status": "pending",
            "request": payload,
            "token_counts": empty_counts(),
            "accounting_valid": False,
            "issues": [],
        }
        state["attempts"].append(current)
        state["token_totals"] = aggregate(state["attempts"])
        store.save(state)
        emit("Request 1 (thinking {}).".format(thinking))
        try:
            raw = api.complete(payload, key)
        except api.TransportError as error:
            if error.raw is not None:
                current.update(capture_raw(error.raw, key))
            current.update(
                status="failed",
                finished_at=now(),
                issues=[error.code],
                error=str(error),
                remote_outcome_uncertain=error.uncertain,
            )
            state.update(status="failed", issues=[error.code], error=str(error))
        else:
            result = evaluate(raw, statements, thinking, payload["max_tokens"], key)
            current.update(result)
            current["finished_at"] = now()
            if not result["issues"]:
                current["status"] = "accepted"
                state.update(
                    status="completed",
                    accepted_attempt=1,
                    ratings=result["ratings"],
                )
            else:
                current["status"] = "rejected"
                state.update(status="failed", issues=result["issues"])
        state["finished_at"] = now()
        state["token_totals"] = aggregate(state["attempts"])
        store.save(state)
    except KeyboardInterrupt:
        if current is not None and current["status"] == "pending":
            current.update(status="interrupted", remote_outcome_uncertain=True)
        state.update(status="interrupted", issues=["interrupted"], finished_at=now())
        state["token_totals"] = aggregate(state["attempts"])
        store.save(state)
        raise
    except api.RatingError as error:
        if current is not None and current["status"] == "pending":
            current.update(status="failed", issues=["local_error"])
        state.update(
            status="failed", issues=["local_error"], error=str(error), finished_at=now()
        )
        state["token_totals"] = aggregate(state["attempts"])
        store.save(state)
        raise
    return state
