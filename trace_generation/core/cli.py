import argparse
import json
import os
import shutil
import sys
import uuid
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, List, Optional, Sequence, Tuple

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
        description="Generate conversational datasets for Dynamic CAPTCHA challenges.",
    )
    parser.add_argument(
        "-n",
        "--num-samples",
        type=positive_int,
        help="number of samples to record",
    )
    parser.add_argument(
        "-r",
        "--run-id",
        help="optional run identifier; defaults to a random suffix",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="output file name without extension (default: conversations)",
    )
    parser.add_argument(
        "-t",
        "--challenge-type",
        choices=list(SUPPORTED_CHALLENGE_TYPES),
        help="restrict recording to a specific challenge type",
    )
    parser.add_argument(
        "-I",
        "--interactive",
        action="store_true",
        help="force interactive menu even when parameters are supplied",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=positive_int,
        help="number of parallel workers to launch (default: 1)",
    )
    parser.add_argument(
        "--debug-mode",
        action="store_true",
        help="Enable debug mode to keep annotated and final images (uses more disk space)",
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


def _prompt_bool(prompt: str, default: bool) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{prompt} [{suffix}]: ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Please answer with 'y' or 'n'.")


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


def _prompt_requires_submit() -> Optional[bool]:
    """Prompt user for requires_submit preference.
    
    Returns:
        None for random selection, True for always submit button, False for always auto-submit
    """
    print("\nChoose submit button behavior for applicable captchas:")
    print("  0. Random (default - randomly choose for each captcha)")
    print("  1. Always show submit button")
    print("  2. Always auto-submit")
    while True:
        choice = input("Enter choice number [0]: ").strip()
        if not choice:
            return None  # Random
        if not choice.isdigit():
            print("Please enter a number from the list.")
            continue
        idx = int(choice)
        if idx == 0:
            return None  # Random
        elif idx == 1:
            return True  # Always submit button
        elif idx == 2:
            return False  # Always auto-submit
        print("Invalid option. Try again.")



def prompt_interactive_defaults(args: argparse.Namespace) -> argparse.Namespace:
    print("Dynamic CAPTCHA Dataset Recorder\n")
    defaults = argparse.Namespace(
        num_samples=args.num_samples or 10,
        run_id=args.run_id or str(uuid.uuid4())[-4:],
        output=args.output or "conversations",
        challenge_type=args.challenge_type,
        workers=args.workers or 1,
        requires_submit=None,  # Default to random
        debug_mode=args.debug_mode,
    )

    defaults.num_samples = _prompt_int("How many samples to record?", defaults.num_samples)
    defaults.run_id = _prompt_str("Run identifier", defaults.run_id)
    defaults.output = _prompt_str("Output file name (without extension)", defaults.output)
    defaults.challenge_type = (
        defaults.challenge_type if defaults.challenge_type is not None else _prompt_challenge_type()
    )
    defaults.requires_submit = _prompt_requires_submit()
    defaults.workers = _prompt_int("How many parallel workers?", defaults.workers)
    defaults.debug_mode = _prompt_bool(
        "Enable debug mode (keep annotated/final images)?", defaults.debug_mode
    )
    print()
    return defaults


def _distribute_work(num_samples: int, workers: int) -> List[int]:
    base = num_samples // workers
    remainder = num_samples % workers
    counts = [base + (1 if idx < remainder else 0) for idx in range(workers)]
    return [count for count in counts if count > 0]


def _make_worker_tasks(
    num_samples: int,
    base_run_id: str,
    output_name: str,
    challenge_type: Optional[str],
    requires_submit: Optional[bool],
    debug_mode: bool,
    workers: int,
) -> List[Tuple[int, str, str, Optional[str], Optional[bool], bool]]:
    if workers <= 1:
        return [(num_samples, base_run_id, output_name, challenge_type, requires_submit, debug_mode)]

    sample_splits = _distribute_work(num_samples, workers)
    tasks: List[Tuple[int, str, str, Optional[str], Optional[bool], bool]] = []
    for idx, count in enumerate(sample_splits):
        worker_run_id = f"{base_run_id}_{idx + 1}"
        tasks.append((count, worker_run_id, output_name, challenge_type, requires_submit, debug_mode))
    return tasks


def _run_worker(args: Tuple[int, str, str, Optional[str], Optional[bool], bool]) -> Tuple[str, str]:
    from .recorder import record_conversational_dataset

    num_samples, run_id, output_name, challenge_type, requires_submit, debug_mode = args
    record_conversational_dataset(
        num_samples=num_samples,
        run_id=run_id,
        output_file_name=output_name,
        challenge_type=challenge_type,
        requires_submit=requires_submit,
        debug_mode=debug_mode,
    )
    return run_id, output_name


def _aggregate_results(
    run_id: str,
    output_name: str,
    worker_runs: Sequence[str],
) -> None:
    if len(worker_runs) <= 1:
        return

    aggregate_dir = os.path.join("runs", run_id)
    aggregate_img_dir = os.path.join(aggregate_dir, "img")
    os.makedirs(aggregate_img_dir, exist_ok=True)

    aggregated: List[dict] = []
    next_index = 0

    def copy_image(src_rel: Optional[str], dst_rel: str) -> bool:
        if not src_rel:
            return False
        src_abs = os.path.join(os.getcwd(), src_rel)
        dst_abs = os.path.join(os.getcwd(), dst_rel)
        if not os.path.exists(src_abs):
            print(f"Warning: expected image {src_rel} missing; skipping copy.")
            return False
        os.makedirs(os.path.dirname(dst_abs), exist_ok=True)
        shutil.copy2(src_abs, dst_abs)
        return True

    for worker_run in worker_runs:
        worker_dir = os.path.join("runs", worker_run)
        worker_json = os.path.join(worker_dir, f"{output_name}.json")
        if not os.path.exists(worker_json):
            print(f"Warning: expected worker output {worker_json} not found; skipping.")
            continue
        try:
            with open(worker_json, "r", encoding="utf-8") as infile:
                worker_entries = json.load(infile)
        except json.JSONDecodeError as exc:
            print(f"Warning: unable to parse {worker_json} ({exc}); skipping.")
            continue

        for entry in worker_entries:
            base_name = f"captcha_sample_{next_index}"
            path_mapping: Dict[str, str] = {}

            initial_src = entry.get("images", {}).get("initial")
            initial_dst = os.path.join("runs", run_id, "img", f"{base_name}.png")
            if copy_image(initial_src, initial_dst):
                entry["images"]["initial"] = initial_dst
                path_mapping[initial_src] = initial_dst

            final_src = entry.get("images", {}).get("final")
            final_dst = os.path.join("runs", run_id, "img", f"{base_name}_final.png")
            if copy_image(final_src, final_dst):
                entry["images"]["final"] = final_dst
                path_mapping[final_src] = final_dst

            stage_images = entry.get("challenge_meta", {}).get("stage_images")
            if stage_images:
                new_stage_images: Dict[str, str] = {}
                for stage_key, stage_src in stage_images.items():
                    stage_dst = os.path.join(
                        "runs",
                        run_id,
                        "img",
                        f"{base_name}_{stage_key}.png",
                    )
                    if copy_image(stage_src, stage_dst):
                        new_stage_images[stage_key] = stage_dst
                        path_mapping[stage_src] = stage_dst
                    else:
                        new_stage_images[stage_key] = stage_src
                entry["challenge_meta"]["stage_images"] = new_stage_images

            step_images = entry.get("challenge_meta", {}).get("step_images")
            if step_images:
                new_step_images: Dict[str, str] = {}
                for step_key, step_src in step_images.items():
                    step_dst = os.path.join(
                        "runs",
                        run_id,
                        "img",
                        f"{base_name}_{step_key}.png",
                    )
                    if copy_image(step_src, step_dst):
                        new_step_images[step_key] = step_dst
                        path_mapping[step_src] = step_dst
                    else:
                        new_step_images[step_key] = step_src
                entry["challenge_meta"]["step_images"] = new_step_images

            for convo in entry.get("conversations", []):
                value = convo.get("value", {})
                image_path = value.get("image")
                if image_path in path_mapping:
                    value["image"] = path_mapping[image_path]

            entry["id"] = base_name
            aggregated.append(entry)
            next_index += 1

    if not aggregated:
        print("Warning: no worker data collected; aggregated file not created.")
        return

    os.makedirs(aggregate_dir, exist_ok=True)
    aggregate_path = os.path.join(aggregate_dir, f"{output_name}.json")
    with open(aggregate_path, "w", encoding="utf-8") as outfile:
        json.dump(aggregated, outfile, indent=2)
    print(f"Aggregated dataset written to {aggregate_path}")

    for worker_run in worker_runs:
        worker_dir = os.path.join("runs", worker_run)
        if os.path.isdir(worker_dir):
            shutil.rmtree(worker_dir, ignore_errors=True)


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
            num_samples=args.num_samples or 10,
            run_id=args.run_id or str(uuid.uuid4())[-4:],
            output=args.output or "conversations",
            challenge_type=args.challenge_type,
            workers=args.workers or 1,
            requires_submit=None,  # Default to random for non-interactive mode
            debug_mode=args.debug_mode,
        )

    workers = max(1, config.workers)
    tasks = _make_worker_tasks(
        num_samples=config.num_samples,
        base_run_id=config.run_id,
        output_name=config.output,
        challenge_type=config.challenge_type,
        requires_submit=config.requires_submit,
        debug_mode=config.debug_mode,
        workers=workers,
    )
    if not tasks:
        print("Nothing to do (no samples requested).")
        return

    challenge_label = next(
        (label for label, value in CLI_CHALLENGE_OPTIONS if value == config.challenge_type),
        "Mixed rotation (all challenge types)",
    )
    print(
        f"Recording {config.num_samples} samples "
        f"for run {config.run_id} (challenge={challenge_label}) "
        f"using {len(tasks)} worker(s)"
    )

    if len(tasks) == 1:
        _run_worker(tasks[0])
    else:
        with ProcessPoolExecutor(max_workers=len(tasks)) as executor:
            future_to_run = {executor.submit(_run_worker, task): task[1] for task in tasks}
            for future in as_completed(future_to_run):
                worker_run_id = future_to_run[future]
                try:
                    future.result()
                    print(f"Worker {worker_run_id} completed.")
                except Exception as exc:  # noqa: BLE001
                    print(f"Worker {worker_run_id} failed: {exc}")

        _aggregate_results(
            run_id=config.run_id,
            output_name=config.output,
            worker_runs=[task[1] for task in tasks],
        )


if __name__ == "__main__":
    main()
