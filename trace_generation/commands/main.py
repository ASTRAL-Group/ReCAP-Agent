#!/usr/bin/env python3
import argparse
import sys
from typing import Optional, Sequence

from . import convert as convert_cli
from ..core import cli as direct_cli
from ..core import cli_correction as correction_cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trace_generation",
        description="Unified CLI for trace generation and dataset conversion.",
    )
    parser.add_argument(
        "command",
        choices=("direct", "self-correction", "self_correction", "convert"),
        help="Subcommand to run.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = list(argv) if argv is not None else sys.argv[1:]
    parser = build_parser()

    if not args or args[0] in {"-h", "--help"}:
        parser.print_help()
        return

    command = args[0]
    remaining = args[1:]
    if command == "direct":
        direct_cli.main(remaining, prog="trace_generation direct")
        return
    if command in {"self-correction", "self_correction"}:
        correction_cli.main(remaining, prog="trace_generation self-correction")
        return
    if command == "convert":
        convert_cli.main(remaining, prog="trace_generation convert")
        return

    parser.error(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
