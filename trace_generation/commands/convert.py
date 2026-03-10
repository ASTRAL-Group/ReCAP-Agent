#!/usr/bin/env python3
import argparse
from pathlib import Path
from typing import Optional, Sequence, Tuple

from ..core.sharegpt_converter import (
    ActionFormat,
    CoordinateMode,
    convert,
    write_sharegpt,
)


FORMAT_CHOICES = ("qwen3", "ui-tars-relative", "ui-tars-absolute")


def parse_args(
    argv: Optional[Sequence[str]] = None,
    prog: Optional[str] = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Convert one raw trace JSON file to ShareGPT format.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Path to source JSON trace file. If omitted, interactive prompt is used.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Path to output JSON file. If omitted, inferred from source + format.",
    )
    parser.add_argument(
        "--format",
        choices=FORMAT_CHOICES,
        help=(
            "Target format: "
            "qwen3, ui-tars-relative, or ui-tars-absolute. "
            "If omitted, interactive prompt is used."
        ),
    )
    parser.add_argument(
        "-I",
        "--interactive",
        action="store_true",
        help="Force interactive prompts.",
    )
    return parser.parse_args(argv)


def _default_suffix(format_name: str) -> str:
    if format_name == "qwen3":
        return "_sharegpt_qwen3"
    if format_name == "ui-tars-absolute":
        return "_sharegpt_ui_tars_absolute"
    return "_sharegpt_ui_tars_relative"


def _is_converted_file(path: Path) -> bool:
    return (
        path.name.endswith("_sharegpt_qwen3.json")
        or path.name.endswith("_sharegpt_ui_tars_relative.json")
        or path.name.endswith("_sharegpt_ui_tars_absolute.json")
        or path.name.endswith("_sharegpt.json")
        or path.name.endswith("_sharegpt_absolute.json")
    )


def _discover_source_files(root: Path = Path("runs")) -> list[Path]:
    if not root.exists():
        return []
    candidates: list[Path] = []
    for path in sorted(root.rglob("*.json")):
        if path.name == "stats.json" or _is_converted_file(path):
            continue
        candidates.append(path)
    return candidates


def _prompt_source_file() -> Path:
    candidates = _discover_source_files()
    if candidates:
        print("Choose source JSON file:")
        for idx, candidate in enumerate(candidates, start=1):
            print(f"  {idx}. {candidate}")
        while True:
            raw = input("Enter number or custom path [1]: ").strip()
            if not raw:
                return candidates[0]
            if raw.isdigit():
                idx = int(raw)
                if 1 <= idx <= len(candidates):
                    return candidates[idx - 1]
            custom = Path(raw).expanduser()
            if custom.is_file():
                return custom
            print("Invalid selection. Please choose a listed number or valid file path.")

    while True:
        raw = input("Enter source JSON path: ").strip()
        custom = Path(raw).expanduser()
        if custom.is_file():
            return custom
        print("File not found. Try again.")


def _prompt_format() -> str:
    print("Choose output format:")
    print("  1. qwen3")
    print("  2. ui-tars-relative")
    print("  3. ui-tars-absolute")
    while True:
        raw = input("Enter choice [1]: ").strip()
        if not raw or raw == "1":
            return "qwen3"
        if raw == "2":
            return "ui-tars-relative"
        if raw == "3":
            return "ui-tars-absolute"
        if raw in FORMAT_CHOICES:
            return raw
        print("Invalid selection. Choose 1/2/3 or a format name.")


def _resolve_modes(format_name: str) -> Tuple[ActionFormat, CoordinateMode]:
    if format_name == "qwen3":
        return "qwen3", "absolute"
    if format_name == "ui-tars-absolute":
        return "ui-tars", "absolute"
    return "ui-tars", "relative"


def convert_one(
    input_path: Path,
    output_path: Path,
    format_name: str,
) -> None:
    action_format, coordinate_mode = _resolve_modes(format_name)
    sharegpt_entries = convert(
        input_path,
        coordinate_mode=coordinate_mode,
        action_format=action_format,
    )
    write_sharegpt(sharegpt_entries, output_path)
    print(f"Wrote {output_path}")


def main(
    argv: Optional[Sequence[str]] = None,
    prog: Optional[str] = None,
) -> None:
    args = parse_args(argv, prog=prog)
    interactive = args.interactive or (
        args.input is None and args.format is None and args.output is None
    )

    input_path = args.input
    format_name = args.format

    if interactive:
        input_path = _prompt_source_file() if input_path is None else input_path
        format_name = _prompt_format() if format_name is None else format_name

    if input_path is None:
        raise SystemExit("Missing --input. Use -I for interactive mode.")
    if not input_path.is_file():
        raise SystemExit(f"Input file not found: {input_path}")

    if format_name is None:
        format_name = "qwen3"

    output_path = args.output
    if output_path is None:
        suffix = _default_suffix(format_name)
        output_path = input_path.with_name(f"{input_path.stem}{suffix}.json")

    convert_one(input_path, output_path, format_name)


if __name__ == "__main__":
    main()
