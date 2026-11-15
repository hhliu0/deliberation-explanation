"""Terminal entry point for one independent, five-file rating trial."""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from .api import RatingError
from .inputs import AGENTS

TOOL_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = TOOL_DIR.parent


def build_parser() -> argparse.ArgumentParser:
    """Define agent selection, trial naming, thinking mode, and local paths."""
    parser = argparse.ArgumentParser(
        prog="ratings.source",
        description="Rate statements using one agent's five files and a fresh DeepSeek request.",
    )
    parser.add_argument("--agent", choices=tuple(AGENTS), required=True)
    parser.add_argument("--trial-name", required=True, metavar="NAME")
    thinking = parser.add_mutually_exclusive_group(required=True)
    thinking.add_argument(
        "--enable-thinking", dest="thinking", action="store_const", const="enabled"
    )
    thinking.add_argument(
        "--not-enable-thinking", dest="thinking", action="store_const", const="disabled"
    )
    parser.add_argument(
        "--prompts-dir",
        type=Path,
        default=TOOL_DIR / "prompt",
        help="parent of agent_a and agent_b input folders (default: ratings/prompt)",
    )
    parser.add_argument(
        "--keys-file",
        type=Path,
        default=PROJECT_DIR / "keys.local.env",
        help="shared credentials file (default: keys.local.env, uses DEEPSEEK_API_KEY_A)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=TOOL_DIR / "archive",
        help="JSON destination (default: ratings/archive)",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the selected agent and display validated scores and token summaries."""
    args = build_parser().parse_args(argv)
    from .engine import run

    try:
        state = run(
            agent_id=args.agent,
            input_dir=args.prompts_dir / args.agent,
            trial_name=args.trial_name,
            thinking=args.thinking,
            keys_file=args.keys_file,
            output_dir=args.output_dir,
        )
    except KeyboardInterrupt:
        print(
            "Interrupted. Read the printed JSON path for saved progress.",
            file=sys.stderr,
        )
        return 130
    except RatingError as error:
        print("Error: " + str(error), file=sys.stderr)
        return 1
    except (OSError, UnicodeError, ValueError, RecursionError):
        print(
            "Local operation failed; read the saved JSON file if one was created.",
            file=sys.stderr,
        )
        return 1
    if state["status"] != "completed":
        print("Trial failed: " + ", ".join(state["issues"]), file=sys.stderr)
        if state.get("error"):
            print(state["error"], file=sys.stderr)
        return 1
    print("Completed ratings:")
    for rating in state["ratings"]:
        print(
            "  {}: {}".format(
                json.dumps(rating["id"], ensure_ascii=True), rating["score"]
            )
        )
    counts = state["attempts"][state["accepted_attempt"] - 1]["token_counts"]
    print(
        "Accepted answer tokens — input: {}; message: {}; thinking: {}.".format(
            counts["input_tokens"],
            counts["message_output_tokens"],
            counts["thinking_tokens"],
        )
    )
    print("Trial totals: " + json.dumps(state["token_totals"]))
    return 0
