#!/usr/bin/env python3
"""
Interactive dataset validator.

Checks each sample for short assistant responses and offers to delete any
problematic entries along with their associated images.
"""

import argparse
import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate dataset samples and optionally delete those with short assistant responses."
    )
    parser.add_argument(
        "dataset",
        type=Path,
        help="Path to the conversations.json file to validate.",
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=200,
        help="Minimum length required for each assistant response (default: 200 characters).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Automatically delete samples with short responses without prompting.",
    )
    return parser.parse_args()


def load_dataset(path: Path) -> List[Dict]:
    with path.open("r", encoding="utf-8") as infile:
        return json.load(infile)


def save_dataset(path: Path, data: Iterable[Dict]) -> None:
    with path.open("w", encoding="utf-8") as outfile:
        json.dump(list(data), outfile, ensure_ascii=False, indent=2)


def locate_short_responses(sample: Dict, min_length: int) -> List[Tuple[int, str]]:
    issues: List[Tuple[int, str]] = []
    for idx, turn in enumerate(sample.get("conversations", [])):
        if turn.get("from") != "gpt":
            continue
        response = (turn.get("value") or {}).get("response") or ""
        if len(response.strip()) < min_length:
            issues.append((idx, response))
    return issues


def delete_image(path_str: str) -> None:
    if not path_str:
        return
    path = Path(path_str)
    try:
        path.unlink()
        print(f"Deleted image: {path}")
    except FileNotFoundError:
        print(f"(missing image skipped) {path}")
    except IsADirectoryError:
        print(f"(directory skipped) {path}")


def delete_sample_assets(sample: Dict) -> None:
    images = sample.get("images") or {}
    delete_image(images.get("initial"))
    delete_image(images.get("final"))

    challenge_meta = sample.get("challenge_meta") or {}
    stage_images = challenge_meta.get("stage_images") or {}
    for path_str in stage_images.values():
        delete_image(path_str)

    step_images = challenge_meta.get("step_images") or {}
    for path_str in step_images.values():
        delete_image(path_str)


def prompt_delete(sample_id: str, issues: List[Tuple[int, str]], auto_yes: bool) -> bool:
    print(f"\nSample '{sample_id}' has {len(issues)} short assistant response(s):")
    for turn_idx, content in issues:
        snippet = content.strip().replace("\n", " ")
        if len(snippet) > 120:
            snippet = snippet[:117] + "..."
        print(f"  - turn #{turn_idx} length={len(content.strip())}: {snippet!r}")

    if auto_yes:
        print("Auto-delete enabled; removing sample.")
        return True

    while True:
        choice = input("Delete this sample and its images? [y/N]: ").strip().lower()
        if not choice:
            return False
        if choice in {"y", "yes"}:
            return True
        if choice in {"n", "no"}:
            return False
        print("Please answer 'y' or 'n'.")


def main() -> None:
    args = parse_args()
    dataset_path = args.dataset
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    data = load_dataset(dataset_path)
    kept_samples: List[Dict] = []
    removed_count = 0

    for sample in data:
        sample_id = sample.get("id") or "<unknown>"
        issues = locate_short_responses(sample, args.min_length)
        if not issues:
            kept_samples.append(sample)
            continue

        if prompt_delete(sample_id, issues, args.yes):
            delete_sample_assets(sample)
            removed_count += 1
        else:
            kept_samples.append(sample)

    if removed_count:
        backup_path = dataset_path.with_suffix(dataset_path.suffix + ".bak")
        if not backup_path.exists():
            os.rename(dataset_path, backup_path)
            print(f"Original dataset backed up to {backup_path}")
        save_dataset(dataset_path, kept_samples)
        print(f"Removed {removed_count} sample(s); dataset updated at {dataset_path}")
    else:
        print("No samples removed; dataset left unchanged.")


if __name__ == "__main__":
    main()
