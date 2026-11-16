"""Run ten non-thinking dialogue rounds, then rate using each agent's memory."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

from dialogue.source import engine as dialogue_engine
from dialogue.source import inputs as dialogue_inputs
from dialogue.source.api import DialogueError
from dialogue.source.cli import positive_int
from ratings.source import engine as rating_engine
from ratings.source import inputs as rating_inputs
from ratings.source.api import RatingError

PROJECT_DIR = Path(__file__).resolve().parent
AGENTS = ("agent_a", "agent_b")
STATEMENT_COUNT = 12


def validate_statements(
    dialogue_texts: Dict[str, str], rating_agents: Dict[str, Any]
) -> None:
    """Require the same twelve statements in the same order in both stages."""
    statements = rating_agents["agent_a"]["statements"]
    if len(statements) != STATEMENT_COUNT:
        raise ValueError("This workflow requires exactly 12 statements.")
    expected = [item["id"] + ": " + item["text"] for item in statements]
    for agent in AGENTS:
        if rating_agents[agent]["statements"] != statements:
            raise ValueError(
                "Both rating agents must have the same ordered statements."
            )
        if dialogue_texts[agent].strip().splitlines() != expected:
            raise ValueError(
                "Dialogue and rating statements must match in ID, text, and order: "
                + agent
            )


def run_workflow(
    trial_name: str,
    rounds: int = 10,
    check_only: bool = False,
    emit: Callable[[str], None] = print,
) -> int:
    """Validate both stages, finish the dialogue, then rate each final memory once."""
    if not trial_name.strip():
        raise ValueError("The trial name must be nonblank.")
    if type(rounds) is not int or rounds < 1:
        raise ValueError("Rounds must be a positive integer.")
    dialogue_dir = PROJECT_DIR / "dialogue"
    ratings_dir = PROJECT_DIR / "ratings"
    keys_file = PROJECT_DIR / "keys.local.env"
    dialogue_agents = {
        agent: dialogue_inputs.load_agent(dialogue_dir / "prompt" / agent, "disabled")
        for agent in AGENTS
    }
    rating_agents = {
        agent: rating_inputs.load_agent(ratings_dir / "prompt" / agent, "disabled")
        for agent in AGENTS
    }
    validate_statements(
        {agent: dialogue_agents[agent]["inputs"]["statements"] for agent in AGENTS},
        rating_agents,
    )
    emit(
        "Skeptic + Extrapolator: {} rounds ({} replies), 12 statements, "
        "then one rating per agent. Thinking disabled throughout.".format(
            rounds, 2 * rounds
        )
    )
    if check_only:
        emit("Input checks passed. No provider requests made.")
        return 0

    dialogue_path = dialogue_engine.run_dialogue(
        agent_a_path=dialogue_dir / "prompt" / "agent_a",
        agent_b_path=dialogue_dir / "prompt" / "agent_b",
        max_messages=2 * rounds,
        keys_file=keys_file,
        output_dir=dialogue_dir / "archive",
        emit=emit,
        trial_name=trial_name,
        thinking="disabled",
    )
    dialogue = json.loads(dialogue_path.read_text(encoding="utf-8"))
    messages = dialogue["messages"]
    if (
        not dialogue["ended_at"]
        or dialogue["thinking"] != "not enabled"
        or len(messages) != 2 * rounds
        or any(item["speaker"] != AGENTS[i % 2] for i, item in enumerate(messages))
    ):
        raise ValueError(
            "The dialogue did not finish the expected non-thinking rounds."
        )

    # Check again against the saved dialogue if prompts changed while it was running.
    rating_agents = {
        agent: rating_inputs.load_agent(ratings_dir / "prompt" / agent, "disabled")
        for agent in AGENTS
    }
    validate_statements(
        {agent: dialogue[agent + "_inputs"]["statements.txt"] for agent in AGENTS},
        rating_agents,
    )
    failed = False
    for agent in AGENTS:
        memory = dialogue_engine.blend_memory(
            dialogue[agent + "_inputs"]["memory.txt"],
            ((item["speaker"], item["message"]) for item in messages),
        )
        state = rating_engine.run(
            agent_id=agent,
            input_dir=ratings_dir / "prompt" / agent,
            trial_name="{} {} {} ratings".format(
                trial_name, dialogue["trial_id"], agent
            ),
            thinking="disabled",
            keys_file=keys_file,
            output_dir=ratings_dir / "archive",
            emit=emit,
            memory=memory,
        )
        if state["status"] != "completed":
            emit(agent + " ratings failed: " + ", ".join(state["issues"]))
            failed = True
            continue
        emit(agent + " completed ratings:")
        for rating in state["ratings"]:
            emit("  {}: {}".format(rating["id"], rating["score"]))
    return 1 if failed else 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the fixed non-thinking workflow or check its inputs without API calls."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trial-name", default="skeptic-extrapolator")
    parser.add_argument(
        "--rounds", type=positive_int, default=10, help="A/B exchanges (default: 10)"
    )
    parser.add_argument(
        "--trials",
        type=positive_int,
        default=1,
        help="fresh dialogue-plus-ratings experiments (default: 1)",
    )
    parser.add_argument(
        "--check", action="store_true", help="validate inputs without provider requests"
    )
    args = parser.parse_args(argv)
    try:
        if not args.trial_name.strip():
            raise ValueError("The trial name must be nonblank.")
        if args.check:
            print("Planned independent trials: {}.".format(args.trials))
            return run_workflow(args.trial_name, args.rounds, check_only=True)
        for trial in range(1, args.trials + 1):
            print("Experiment {}/{}.".format(trial, args.trials))
            trial_name = args.trial_name
            if args.trials > 1:
                trial_name += " trial {} of {}".format(trial, args.trials)
            result = run_workflow(trial_name, args.rounds)
            if result:
                print("Batch stopped after a failed experiment.", file=sys.stderr)
                return result
        return 0
    except KeyboardInterrupt:
        print(
            "Interrupted. Retain the printed JSON files for saved progress.",
            file=sys.stderr,
        )
        return 130
    except (DialogueError, RatingError, ValueError) as error:
        print("Error: " + str(error), file=sys.stderr)
        return 1
    except (OSError, KeyError, TypeError):
        print(
            "Cannot complete workflow; check inputs and saved JSON files.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
