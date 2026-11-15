"""Command-line interface for running a two-agent dialogue."""

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from . import engine
from .api import DialogueError


def positive_int(value: str) -> int:
    """Parse a strictly positive count for argparse."""
    try:
        count = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    if count < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return count


def _add_run_options(parser: argparse.ArgumentParser) -> None:
    """Add the trial name, message limit, credential file, and output directory."""
    parser.add_argument(
        "--trial-name",
        required=True,
        metavar="NAME",
        help="name to include in this trial's JSON log",
    )
    parser.add_argument(
        "--max-messages",
        type=positive_int,
        default=20,
        help="number of accepted messages to generate (default: 20)",
    )
    parser.add_argument(
        "--keys-file",
        type=Path,
        default=Path("keys.local.env"),
        help="local credentials file (default: keys.local.env)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("Dialogue Archive"),
        help="directory for saved dialogue runs (default: Dialogue Archive)",
    )


def build_parser() -> argparse.ArgumentParser:
    """Define the dialogue run command and its arguments."""
    parser = argparse.ArgumentParser(
        prog="deepseek_dialogue",
        description="Start a new DeepSeek dialogue. Agent A always starts.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser(
        "run", help="start a dialogue from five text files per agent"
    )
    run.add_argument(
        "--agent-a",
        type=Path,
        default=Path("prompts/Agent A"),
        metavar="DIR",
        help="Agent A input directory (default: prompts/Agent A)",
    )
    run.add_argument(
        "--agent-b",
        type=Path,
        default=Path("prompts/Agent B"),
        metavar="DIR",
        help="Agent B input directory (default: prompts/Agent B)",
    )
    run.add_argument(
        "--thinking",
        choices=("enabled", "disabled"),
        default=None,
        help="override both agents' file-based thinking settings for this run",
    )
    _add_run_options(run)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the dialogue with parsed options and return its process exit status."""
    args = build_parser().parse_args(argv)
    try:
        engine.run_dialogue(
            agent_a_path=args.agent_a,
            agent_b_path=args.agent_b,
            max_messages=args.max_messages,
            keys_file=args.keys_file,
            output_dir=args.output_dir,
            emit=print,
            trial_name=args.trial_name,
            thinking=args.thinking,
        )
    except KeyboardInterrupt:
        print(
            "Interrupted. Read the saved JSON file for recorded progress.",
            file=sys.stderr,
        )
        return 130
    except DialogueError as exc:
        print("Error: {}".format(exc), file=sys.stderr)
        return 1
    except (ValueError, OSError):
        print(
            "Cannot start run: check the input files and settings.",
            file=sys.stderr,
        )
        return 1
    return 0
