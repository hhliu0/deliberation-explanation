"""Command-line interface for a saved, two-agent dialogue."""

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
    parser.add_argument(
        "--max-messages",
        type=positive_int,
        default=20,
        help="number of NEW accepted messages to generate (default: 20)",
    )
    _add_storage_options(parser)


def _add_storage_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--keys-file",
        type=Path,
        default=Path("keys.local.env"),
        help="local credentials file (default: keys.local.env)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("runs/dialogue"),
        help="directory for saved dialogue runs (default: runs/dialogue)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deepseek_dialogue",
        description="Run and inspect a saved DeepSeek dialogue. Agent A always starts.",
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

    resume = commands.add_parser(
        "resume", help="continue a saved chat to 20 total accepted messages"
    )
    resume.add_argument(
        "chat_id",
        nargs="?",
        help="chat/trial ID or saved JSON path (prompted when omitted)",
    )
    _add_storage_options(resume)

    inspect = commands.add_parser("inspect", help="read a saved run without API calls")
    inspect.add_argument("run_path", type=Path)
    inspect.add_argument(
        "--show-thinking", action="store_true", help="also display saved reasoning"
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            engine.run_dialogue(
                agent_a_path=args.agent_a,
                agent_b_path=args.agent_b,
                max_messages=args.max_messages,
                keys_file=args.keys_file,
                output_dir=args.output_dir,
                emit=print,
                thinking=args.thinking,
            )
        elif args.command == "resume":
            chat_id = args.chat_id
            if chat_id is None:
                try:
                    chat_id = input("Chat ID: ")
                except EOFError:
                    raise DialogueError("No chat ID supplied.") from None
            chat_id = chat_id.strip()
            if not chat_id:
                raise DialogueError("Chat ID cannot be empty.")
            engine.resume_dialogue(
                chat_id=chat_id,
                keys_file=args.keys_file,
                output_dir=args.output_dir,
                emit=print,
            )
        else:
            engine.inspect_run(
                run_path=args.run_path,
                show_thinking=args.show_thinking,
                emit=print,
            )
    except KeyboardInterrupt:
        print("Interrupted. Inspect the saved run before resuming.", file=sys.stderr)
        return 130
    except DialogueError as exc:
        print("Error: {}".format(exc), file=sys.stderr)
        return 1
    except (ValueError, OSError):
        print(
            "Cannot start/inspect run: check the input files and settings.",
            file=sys.stderr,
        )
        return 1
    return 0
