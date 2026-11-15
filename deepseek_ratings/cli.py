"""Terminal-only entry point for an independent rating trial."""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from .api import RatingError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deepseek_ratings",
        description="Rate a statement list using one persona and a fresh DeepSeek request.",
    )
    parser.add_argument("--personas", type=Path, required=True, metavar="FILE")
    parser.add_argument("--statements", type=Path, required=True, metavar="FILE")
    parser.add_argument(
        "--persona", help="persona ID (optional for a single-persona file)"
    )
    parser.add_argument(
        "--thinking", choices=("enabled", "disabled"), default="enabled"
    )
    parser.add_argument("--keys-file", type=Path, default=Path("ratings.local.env"))
    parser.add_argument("--output-dir", type=Path, default=Path("runs/ratings"))
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from .engine import run
    except ModuleNotFoundError as error:
        if error.name != "yaml":
            raise
        print(
            "PyYAML is required; use the documented rating virtual environment.",
            file=sys.stderr,
        )
        return 1
    try:
        state = run(
            args.personas,
            args.statements,
            args.persona,
            args.thinking,
            args.keys_file,
            args.output_dir,
        )
    except KeyboardInterrupt:
        print(
            "Interrupted. No automatic continuation; inspect the printed YAML path.",
            file=sys.stderr,
        )
        return 130
    except RatingError as error:
        print("Error: " + str(error), file=sys.stderr)
        return 1
    except (OSError, UnicodeError, ValueError, RecursionError):
        print(
            "Local operation failed; inspect the last saved trial if one was created.",
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
    print("Trial totals (all attempts): " + json.dumps(state["token_totals"]))
    return 0
