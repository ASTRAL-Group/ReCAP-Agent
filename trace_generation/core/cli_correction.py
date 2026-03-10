#!/usr/bin/env python3
"""
CLI entry point for self-correction dataset recording.
Records multi-turn conversations where models fail initially and receive correction.
"""

import argparse
import json
import os
import sys
import uuid
from typing import Optional, Sequence

from .constants import CLI_CHALLENGE_OPTIONS, SUPPORTED_CHALLENGE_TYPES


def positive_int(value: str) -> int:
    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError("number of samples must be a positive integer")
    return ivalue


def parse_args(
    argv: Optional[Sequence[str]] = None,
    prog: Optional[str] = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Generate self-correction datasets for CAPTCHA challenges. "
                    "Only records examples where the model initially fails.",
    )
    parser.add_argument(
        "-n",
        "--num-samples",
        type=positive_int,
        default=10,
        help="number of failed examples to record (default: 10)",
    )
    parser.add_argument(
        "-r",
        "--run-id",
        help="optional run identifier; defaults to a random suffix",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="self_correction_conversations",
        help="output file name without extension (default: self_correction_conversations)",
    )
    parser.add_argument(
        "-t",
        "--challenge-type",
        choices=list(SUPPORTED_CHALLENGE_TYPES),
        help="restrict recording to a specific challenge type",
    )
    parser.add_argument(
        "--max-attempts",
        type=positive_int,
        default=100,
        help="maximum total attempts before giving up (default: 100)",
    )
    parser.add_argument(
        "-I",
        "--interactive",
        action="store_true",
        help="force interactive menu even when parameters are supplied",
    )
    return parser.parse_args(argv)


def _prompt_int(prompt: str, default: int) -> int:
    while True:
        raw = input(f"{prompt} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("Please enter a valid integer.")
            continue
        if value <= 0:
            print("Please enter a positive integer.")
            continue
        return value


def _prompt_str(prompt: str, default: str) -> str:
    raw = input(f"{prompt} [{default}]: ").strip()
    return raw or default


def _prompt_challenge_type() -> Optional[str]:
    print("\nChoose the challenge type to record:")
    for idx, (label, _) in enumerate(CLI_CHALLENGE_OPTIONS):
        print(f"  {idx}. {label}")
    while True:
        choice = input("Enter choice number [0]: ").strip()
        if not choice:
            return CLI_CHALLENGE_OPTIONS[0][1]
        if not choice.isdigit():
            print("Please enter a number from the list.")
            continue
        idx = int(choice)
        if 0 <= idx < len(CLI_CHALLENGE_OPTIONS):
            return CLI_CHALLENGE_OPTIONS[idx][1]
        print("Invalid option. Try again.")


def prompt_interactive_defaults(args: argparse.Namespace) -> argparse.Namespace:
    print("Self-Correction CAPTCHA Dataset Recorder\n")
    print("NOTE: Only examples where the model fails will be recorded.\n")

    defaults = argparse.Namespace(
        num_samples=args.num_samples,
        run_id=args.run_id or str(uuid.uuid4())[-4:],
        output=args.output,
        challenge_type=args.challenge_type,
        max_attempts=args.max_attempts,
    )

    defaults.num_samples = _prompt_int(
        "How many FAILED examples to record?", defaults.num_samples
    )
    defaults.run_id = _prompt_str("Run identifier", defaults.run_id)
    defaults.output = _prompt_str("Output file name (without extension)", defaults.output)
    defaults.challenge_type = (
        defaults.challenge_type if defaults.challenge_type is not None
        else _prompt_challenge_type()
    )
    defaults.max_attempts = _prompt_int(
        "Maximum total attempts before giving up?", defaults.max_attempts
    )
    print()
    return defaults


def record_self_correction_dataset(
    num_samples: int,
    run_id: str,
    output_file_name: str,
    challenge_type: Optional[str],
    max_attempts: int,
) -> None:
    """
    Record self-correction dataset by attempting challenges until we collect
    enough failed examples.

    Args:
        num_samples: Number of failed examples to record
        run_id: Unique run identifier
        output_file_name: Output filename without extension
        challenge_type: Specific challenge type or None for mixed
        max_attempts: Maximum total attempts before giving up
    """
    run_dir = os.path.join("runs", run_id)
    os.makedirs(run_dir, exist_ok=True)

    from .recorder_correction import SelfCorrectionRecorder

    recorder = SelfCorrectionRecorder(run_dir)

    # Available challenge types for rotation
    all_types = list(SUPPORTED_CHALLENGE_TYPES)

    recorded_examples = []
    recorded_count = 0
    attempted_count = 0
    success_count = 0

    print(f"\nRecording self-correction dataset:")
    print(f"  Target: {num_samples} failed examples")
    print(f"  Max attempts: {max_attempts}")
    print(f"  Challenge type: {challenge_type or 'Mixed (all types)'}")
    print(f"  Run ID: {run_id}\n")

    while recorded_count < num_samples and attempted_count < max_attempts:
        # Determine which captcha type to attempt
        if challenge_type:
            current_type = challenge_type
        else:
            # Rotate through all types
            current_type = all_types[attempted_count % len(all_types)]

        attempted_count += 1
        print(f"[Attempt {attempted_count}] Trying {current_type}...")

        try:
            # Record the example (returns None if model succeeded)
            example = recorder.record_example(current_type, recorded_count)

            if example is None:
                # Model succeeded, skip this example
                success_count += 1
                print(f"  ✓ Model succeeded (skipped) - Success rate: {success_count}/{attempted_count} ({100*success_count/attempted_count:.1f}%)\n")
            else:
                # Model failed, recorded correction
                recorded_examples.append(example)
                recorded_count += 1
                print(f"  ✗ Model failed, correction recorded - Progress: {recorded_count}/{num_samples}\n")

        except Exception as e:
            print(f"  Error during attempt: {e}")
            import traceback
            traceback.print_exc()
            print()

    # Save the recorded examples
    output_path = os.path.join(run_dir, f"{output_file_name}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(recorded_examples, f, indent=2)

    # Save statistics
    stats = {
        "recorded_examples": recorded_count,
        "total_attempts": attempted_count,
        "successes": success_count,
        "failure_rate": (attempted_count - success_count) / attempted_count if attempted_count > 0 else 0,
        "target_samples": num_samples,
        "max_attempts": max_attempts,
        "challenge_type": challenge_type,
        "run_id": run_id
    }
    stats_path = os.path.join(run_dir, "stats.json")
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    # Print final summary
    print("\n" + "="*60)
    print("Recording Complete!")
    print("="*60)
    print(f"Recorded examples: {recorded_count}/{num_samples}")
    print(f"Total attempts: {attempted_count}")
    print(f"Successes (skipped): {success_count}")
    print(f"Failures (recorded): {recorded_count}")
    print(f"Model failure rate: {100*(attempted_count-success_count)/attempted_count:.1f}%")
    print(f"\nDataset saved to: {output_path}")
    print(f"Statistics saved to: {stats_path}")

    print("="*60 + "\n")

    if recorded_count < num_samples:
        print(f"WARNING: Only recorded {recorded_count}/{num_samples} examples.")
        print(f"Reached max attempts limit ({max_attempts}).")
        if success_count > 0:
            print(f"Model success rate was high ({100*success_count/attempted_count:.1f}%).")
            print("Consider using a weaker model or harder challenges.")


def main(
    argv: Optional[Sequence[str]] = None,
    prog: Optional[str] = None,
) -> None:
    args = parse_args(argv, prog=prog)
    interactive = args.interactive or (len(argv) == 0 if argv is not None else len(sys.argv) == 1)

    if interactive:
        config = prompt_interactive_defaults(args)
    else:
        config = argparse.Namespace(
            num_samples=args.num_samples,
            run_id=args.run_id or str(uuid.uuid4())[-4:],
            output=args.output,
            challenge_type=args.challenge_type,
            max_attempts=args.max_attempts,
        )

    record_self_correction_dataset(
        num_samples=config.num_samples,
        run_id=config.run_id,
        output_file_name=config.output,
        challenge_type=config.challenge_type,
        max_attempts=config.max_attempts,
    )


if __name__ == "__main__":
    main()
