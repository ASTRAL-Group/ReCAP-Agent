import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple, cast

import requests
import random
from playwright.sync_api import Page, sync_playwright, ViewportSize
from tqdm import tqdm

from .constants import (
    BASE_URL,
    CHALLENGE_ROUTES,
    DEFAULT_PROMPTS,
    FOLLOWUP_PROMPTS,
    SYSTEM_PROMPT,
)
from .config import COMMON_VIEWPORTS
from .reasoning import generate_model_reasoning
from .solvers import SOLVER_MAP
from .utils import ensure_directories, format_point, image_dimensions

def detect_challenge_type(page: Page) -> str:
    if page.locator(".compact-captcha").count() > 0:
        return "compact_text"
    if page.locator(".icon-match-captcha").count() > 0:
        return "icon_match"
    if page.locator(".paged-captcha").count() > 0:
        return "paged"
    if page.locator(".icon-slider-captcha").count() > 0:
        return "paged"
    if page.locator(".icon-captcha").count() > 0:
        return "icon_selection"
    if page.locator(".slider-captcha").count() > 0:
        return "slider"
    if page.locator("#challenge-wrapper").count() > 0 and page.locator("#checkbox").count() > 0:
        return "image_grid"
    return "text"


def _fetch_status_payload(challenge_id: str) -> Dict[str, Any]:
    try:
        response = requests.get(f"{BASE_URL}/status/{challenge_id}")
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        print(f"Warning: failed to fetch challenge status ({exc}).")
        return {}


def _extract_slider_meta(status_payload: Dict[str, Any]) -> Dict[str, Any]:
    keys = [
        "puzzle_width",
        "puzzle_height",
        "piece_size",
        "piece_top",
        "hole_left",
        "slider_size",
        "puzzle_mask",
        "tolerance",
        "track_width",
        "requires_submit",
    ]
    return {key: status_payload.get(key) for key in keys if status_payload.get(key) is not None}


def _extract_icon_meta(status_payload: Dict[str, Any]) -> Dict[str, Any]:
    keys = ["positions", "all_icons", "icon_size", "canvas_dimensions", "requires_submit"]
    return {key: status_payload.get(key) for key in keys if status_payload.get(key) is not None}


def _extract_icon_match_meta(status_payload: Dict[str, Any]) -> Dict[str, Any]:
    keys = [
        "pieces",
        "tolerance",
        "canvas_dimensions",
        "icon_size",
        "requires_submit",
        "pair_icon",
        "pair_icon_name",
        "match_pair_ids",
    ]
    return {key: status_payload.get(key) for key in keys if status_payload.get(key) is not None}


def _extract_paged_meta(status_payload: Dict[str, Any]) -> Dict[str, Any]:
    keys = [
        "card_icons",
        "card_backgrounds",
        "target_icon",
        "target_icon_name",
        "target_category",
        "mode",
        "data_source",
        "card_images",
        "instruction",
        "instruction_text",
        "challenge_title",
        "challenge_subtitle",
        "total_cards",
        "requires_submit",
    ]
    return {key: status_payload.get(key) for key in keys if status_payload.get(key) is not None}


def _build_system_message() -> Dict[str, Any]:
    return {
        "from": "system",
        "value": {
            "content": SYSTEM_PROMPT.strip(),
        },
    }


def _choose_default_prompt() -> str:
    return random.choice(DEFAULT_PROMPTS).strip()


def _choose_followup_prompt() -> str:
    return random.choice(FOLLOWUP_PROMPTS).strip()


def _active_paged_state(page: Page, card_icons: List[str]) -> Tuple[int, str]:
    """Return (index, icon_key) for the currently visible card."""
    active_locator = page.locator(".icon-card.active").first
    if active_locator.count() == 0:
        active_locator = page.locator(".icon-card").first
    idx_str = active_locator.get_attribute("data-index") or "0"
    try:
        idx = int(idx_str)
    except (TypeError, ValueError):
        idx = 0
    icon_key = (
        active_locator.get_attribute("data-icon")
        or active_locator.get_attribute("data-card-key")
        or ""
    )
    if not icon_key and card_icons and 0 <= idx < len(card_icons):
        icon_key = card_icons[idx]
    return idx, icon_key


def _solve_paged_with_steps(
    page: Page,
    solution_data: Dict[str, Any],
    img_dir: str,
    sample_index: int,
    initial_image_path: str,
) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]], str, int, int]:
    """Navigate the icon slider step-by-step, capturing multi-turn state."""
    from .utils import wait_for_success_message  # Local import to avoid circular

    target_icon = solution_data.get("solution") or solution_data.get("target_icon")
    card_icons = solution_data.get("card_icons") or []
    try:
        total_cards = int(solution_data.get("total_cards") or 0)
    except (TypeError, ValueError):
        total_cards = 0
    if total_cards <= 0:
        total_cards = len(card_icons) if card_icons else page.locator(".icon-card").count()
    total_cards = max(total_cards, 1)

    actions: List[Dict[str, str]] = []
    step_logs: List[Dict[str, Any]] = []
    nav_right = page.locator(".nav-right")
    submit_locator = page.locator("#submit-btn")

    current_image = initial_image_path
    current_width, current_height = image_dimensions(current_image)
    current_index, current_icon = _active_paged_state(page, card_icons)
    initial_state = {
        "current_index": current_index,
        "current_icon": current_icon,
        "total_cards": total_cards,
        "target_icon": target_icon,
        "target_category": solution_data.get("target_category"),
        "mode": solution_data.get("mode") or solution_data.get("data_source"),
        "data_source": solution_data.get("data_source"),
        "matched": target_icon is not None and current_icon == target_icon,
    }

    max_steps = total_cards + 2  # a little buffer to avoid infinite loops

    for step_idx in range(max_steps):
        matched = target_icon is not None and current_icon == target_icon
        if matched:
            break

        nav_box = nav_right.bounding_box()
        if not nav_box:
            raise RuntimeError("Unable to locate icon slider navigation button.")

        click_point = format_point(
            nav_box["x"] + nav_box["width"] / 2,
            nav_box["y"] + nav_box["height"] / 2,
        )
        step_action = {"action": "click", "point": click_point}
        actions.append(step_action)

        nav_right.click()
        page.wait_for_timeout(250)

        after_path = os.path.join(img_dir, f"captcha_sample_{sample_index}_step{step_idx+1}.png")
        page.screenshot(path=after_path, full_page=True)
        after_width, after_height = image_dimensions(after_path)

        next_index, next_icon = _active_paged_state(page, card_icons)

        step_logs.append(
            {
                "before_image": current_image,
                "after_image": after_path,
                "after_dimensions": {"width": after_width, "height": after_height},
                "actions": [step_action],
                "meta": {
                    "step_type": "navigate",
                    "before_index": current_index,
                    "before_icon": current_icon,
                    "after_index": next_index,
                    "after_icon": next_icon,
                    "total_cards": total_cards,
                    "target_icon": target_icon,
                    "matched_before": matched,
                    "matched_after": target_icon is not None and next_icon == target_icon,
                },
            }
        )

        current_image = after_path
        current_width, current_height = after_width, after_height
        current_index, current_icon = next_index, next_icon

    final_path = current_image
    final_width, final_height = current_width, current_height

    # Click submit once the target is in view (or after navigation attempts) - required for icon slider
    submit_box = submit_locator.bounding_box()
    if not submit_box:
        raise RuntimeError("Unable to locate icon slider submit button.")

    submit_point = format_point(
        submit_box["x"] + submit_box["width"] / 2,
        submit_box["y"] + submit_box["height"] / 2,
    )
    submit_action = {"action": "click", "point": submit_point}
    actions.append(submit_action)
    submit_locator.click()
    page.wait_for_timeout(250)

    submit_path = os.path.join(img_dir, f"captcha_sample_{sample_index}_submit.png")
    page.screenshot(path=submit_path, full_page=True)
    final_path = submit_path
    final_width, final_height = image_dimensions(submit_path)

    step_logs.append(
        {
            "before_image": current_image,
            "after_image": submit_path,
            "after_dimensions": {"width": final_width, "height": final_height},
            "actions": [submit_action],
            "meta": {
                "step_type": "submit",
                "before_index": current_index,
                "before_icon": current_icon,
                "after_index": current_index,
                "after_icon": current_icon,
                "total_cards": total_cards,
                "target_icon": target_icon,
                "matched_before": target_icon is not None and current_icon == target_icon,
                "matched_after": target_icon is not None and current_icon == target_icon,
            },
        }
    )

    wait_for_success_message(page)
    return actions, step_logs, final_path, final_width, final_height, initial_state

def record_conversational_dataset(
    num_samples: int,
    run_id: str,
    output_file_name: str,
    challenge_type: Optional[str] = None,
    requires_submit: Optional[bool] = None,
    debug_mode: bool = False,
) -> None:
    img_dir = ensure_directories(run_id)
    output_path = os.path.join("runs", run_id, f"{output_file_name}.json")

    if challenge_type is not None:
        if challenge_type not in CHALLENGE_ROUTES:
            raise ValueError(
                f"Unknown challenge type '{challenge_type}'. "
                f"Expected one of: {', '.join(CHALLENGE_ROUTES)}."
            )
        challenge_cycle = [challenge_type]
    else:
        challenge_cycle = list(CHALLENGE_ROUTES.keys())

    dataset: List[dict] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        
        for i in tqdm(range(num_samples), desc="Recording samples", unit="sample"):
            viewport = COMMON_VIEWPORTS[i % len(COMMON_VIEWPORTS)]
            
            context = browser.new_context(
                viewport=cast(ViewportSize, viewport),
                ignore_https_errors=True,
            )
            page = context.new_page()

            requested_type = challenge_cycle[i % len(challenge_cycle)]
            challenge_url = f"{BASE_URL}{CHALLENGE_ROUTES[requested_type]}"
            
            # Add requires_submit query parameter for applicable challenge types
            if requires_submit is not None and requested_type in {"slider", "icon_selection"}:
                submit_value = "true" if requires_submit else "false"
                challenge_url += f"?requires_submit={submit_value}"
            
            page.goto(challenge_url)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(600)
            try:
                page.wait_for_selector("#challenge-id", state="attached", timeout=5000)
            except Exception as exc:
                raise RuntimeError(f"Timed out waiting for challenge id element on {challenge_url}") from exc

            actual_type = detect_challenge_type(page)
            challenge_id = page.locator("#challenge-id").input_value()
            if not challenge_id:
                raise RuntimeError("Unable to read challenge ID from the page.")

            solution_response = requests.get(f"{BASE_URL}/solution/{challenge_id}")
            solution_response.raise_for_status()
            solution_data = solution_response.json()

            slider_meta: Dict[str, Any] = {}
            icon_meta: Dict[str, Any] = {}
            paged_meta: Dict[str, Any] = {}
            icon_match_meta: Dict[str, Any] = {}
            image_grid_meta: Dict[str, Any] = {}

            status_payload: Dict[str, Any] = {}
            if actual_type in {"slider", "icon_selection", "paged", "icon_match"}:
                status_payload = _fetch_status_payload(challenge_id)

            if actual_type == "slider" and status_payload:
                slider_meta = _extract_slider_meta(status_payload)
                for key, value in slider_meta.items():
                    solution_data.setdefault(key, value)

            if actual_type == "icon_selection" and status_payload:
                icon_meta = _extract_icon_meta(status_payload)
                for key, value in icon_meta.items():
                    solution_data.setdefault(key, value)

            if actual_type == "paged" and status_payload:
                paged_meta = _extract_paged_meta(status_payload)
                for key, value in paged_meta.items():
                    solution_data.setdefault(key, value)

            if actual_type == "icon_match" and status_payload:
                icon_match_meta = _extract_icon_match_meta(status_payload)
                for key, value in icon_match_meta.items():
                    solution_data.setdefault(key, value)

            screenshot_path = os.path.join(img_dir, f"captcha_sample_{i}.png")
            page.screenshot(path=screenshot_path, full_page=True)
            initial_width, initial_height = image_dimensions(screenshot_path)
            final_screenshot_path = os.path.join(img_dir, f"captcha_sample_{i}_final.png")
            final_width = 0
            final_height = 0

            if actual_type == "image_grid":
                checkbox_locator = page.locator("#checkbox")
                checkbox_box = checkbox_locator.bounding_box()
                if not checkbox_box:
                    raise RuntimeError("Unable to locate image-grid checkbox.")

                checkbox_point = format_point(
                    checkbox_box["x"] + checkbox_box["width"] / 2,
                    checkbox_box["y"] + checkbox_box["height"] / 2,
                )
                opening_actions = [{"action": "click", "point": checkbox_point}]
                opening_reasoning = (
                    "Thinking: I'll open the image-grid challenge first, then select the required tiles and verify."
                )
                checkbox_locator.click()
                page.wait_for_selector(".image-tile", state="visible", timeout=5000)

                correct_tiles: List[int] = []
                instruction = solution_data.get("instruction") or solution_data.get("target_category") or ""

                if challenge_id:
                    try:
                        challenge_response = requests.get(
                            f"{BASE_URL}/challenge/image_grid/data/{challenge_id}", timeout=5
                        )
                        challenge_response.raise_for_status()
                        challenge_payload = challenge_response.json()
                        correct_tiles = [int(idx) for idx in challenge_payload.get("correct_tiles", [])]
                        instruction = challenge_payload.get("instruction", instruction)
                    except Exception as exc:  # noqa: BLE001
                        print(
                            f"Warning: failed to fetch challenge data for image-grid ({exc}). Using solution endpoint data."
                        )

                if not correct_tiles:
                    raw_tiles = solution_data.get("solution", [])
                    if isinstance(raw_tiles, list):
                        try:
                            correct_tiles = [int(idx) for idx in raw_tiles]
                        except (TypeError, ValueError):
                            correct_tiles = []

                correct_tiles = sorted(correct_tiles)
                requires_selection = len(correct_tiles) > 0
                image_grid_meta.update(
                    {
                        "correct_tiles": correct_tiles,
                        "requires_tile_selection": requires_selection,
                    }
                )
                solution_data["correct_tiles"] = correct_tiles
                solution_data["requires_tile_selection"] = requires_selection
                solution_data["solution"] = correct_tiles
                if instruction:
                    solution_data["instruction"] = instruction

                stage2_path = os.path.join(img_dir, f"captcha_sample_{i}_stage2.png")
                page.wait_for_timeout(300)
                page.screenshot(path=stage2_path, full_page=True)
                stage2_width, stage2_height = image_dimensions(stage2_path)

                solver = SOLVER_MAP.get(actual_type)
                if solver is None:
                    raise RuntimeError(f"No solver available for challenge type '{actual_type}'.")
                actions_stage2 = solver(page, solution_data)
                page.screenshot(path=final_screenshot_path, full_page=True)
                final_width, final_height = image_dimensions(final_screenshot_path)

                thinking_stage2, annotated_files_stage2 = generate_model_reasoning(
                    actual_type,
                    solution_data,
                    [stage2_path, final_screenshot_path],
                    actions=actions_stage2,
                )
                
                # Clean up annotated files if not in debug mode
                if not debug_mode:
                    for annotated_file in annotated_files_stage2:
                        try:
                            if os.path.exists(annotated_file):
                                os.remove(annotated_file)
                        except Exception as e:
                            print(f"Warning: Could not remove annotated file {annotated_file}: {e}")

                initial_prompt = _choose_default_prompt()
                followup_prompt = _choose_followup_prompt()

                conversation = [
                    _build_system_message(),
                    {
                        "from": "human",
                        "value": {
                            "input": initial_prompt,
                            "image": screenshot_path,
                            "challenge_type": actual_type,
                        },
                    },
                    {
                        "from": "gpt",
                        "value": {
                            "response": opening_reasoning,
                            "actions": opening_actions,
                        },
                    },
                    {
                        "from": "human",
                        "value": {
                            "input": followup_prompt,
                            "image": stage2_path,
                            "challenge_type": actual_type,
                        },
                    },
                    {
                        "from": "gpt",
                        "value": {
                            "response": thinking_stage2,
                            "actions": actions_stage2,
                        },
                    },
                ]

                image_grid_meta.update(
                    {
                        "stage_images": {"after_checkbox": stage2_path},
                        "stage_image_dimensions": {
                            "after_checkbox": {"width": stage2_width, "height": stage2_height}
                        },
                    }
                )
            else:
                solver = SOLVER_MAP.get(actual_type)
                if solver is None and actual_type != "paged":
                    raise RuntimeError(f"No solver available for challenge type '{actual_type}'.")
                if actual_type in {"text", "compact_text"}:
                    solution_data = solution_data.get("solution", "")

                if actual_type == "paged":
                    actions, step_logs, final_screenshot_path, final_width, final_height, initial_state = _solve_paged_with_steps(
                        page,
                        solution_data,
                        img_dir,
                        i,
                        screenshot_path,
                    )

                    if not step_logs:
                        step_logs.append(
                            {
                                "before_image": screenshot_path,
                                "after_image": final_screenshot_path,
                                "after_dimensions": {"width": final_width, "height": final_height},
                                "actions": actions,
                                "meta": {
                                    "step_type": "submit" if actions else "observe",
                                    "before_index": initial_state.get("current_index", 0),
                                    "before_icon": initial_state.get("current_icon", ""),
                                    "after_index": initial_state.get("current_index", 0),
                                    "after_icon": initial_state.get("current_icon", ""),
                                    "total_cards": initial_state.get("total_cards", 1),
                                    "target_icon": initial_state.get("target_icon"),
                                    "matched_before": initial_state.get("matched", False),
                                    "matched_after": initial_state.get("matched", False),
                                },
                            }
                        )

                    annotated_files: List[str] = []
                    conversation: List[Dict[str, Any]] = [_build_system_message()]
                    initial_prompt = _choose_default_prompt()
                    followup_prompt = _choose_followup_prompt()
                    conversation.append(
                        {
                            "from": "human",
                            "value": {
                                "input": initial_prompt,
                                "image": screenshot_path,
                                "challenge_type": actual_type,
                                    "state": {
                                        "current_index": initial_state.get("current_index"),
                                        "total_cards": initial_state.get("total_cards"),
                                        "target_icon": initial_state.get("target_icon"),
                                        "current_icon": initial_state.get("current_icon"),
                                        "matched": initial_state.get("matched"),
                                    },
                            },
                        }
                    )

                    # Build multi-turn conversation per step; include the submit decision
                    for idx, step in enumerate(step_logs):
                        step_type = step["meta"].get("step_type")
                        matched_after = step["meta"].get("matched_after")

                        step_solution_data = dict(solution_data)
                        step_solution_data.update(
                            {
                                "current_card_index": step["meta"].get("before_index"),
                                "current_card_icon": step["meta"].get("before_icon"),
                                "total_cards": step["meta"].get("total_cards"),
                                "target_icon": step["meta"].get("target_icon"),
                                "matched": step["meta"].get("matched_before"),
                                "step_type": step_type,
                            }
                        )
                        reasoning, step_annotated = generate_model_reasoning(
                            actual_type,
                            step_solution_data,
                            [step["before_image"], step["after_image"]],
                            actions=step["actions"],
                        )
                        annotated_files.extend(step_annotated)

                        conversation.append(
                            {
                                "from": "gpt",
                                "value": {
                                    "response": reasoning,
                                    "actions": step["actions"],
                                },
                            }
                        )

                        # If this was the submit step, stop without adding another user prompt
                        if step_type == "submit":
                            break

                        conversation.append(
                            {
                                "from": "human",
                                "value": {
                                    "input": followup_prompt,
                                    "image": step["after_image"],
                                    "challenge_type": actual_type,
                                    "state": {
                                        "current_index": step["meta"].get("after_index"),
                                        "total_cards": step["meta"].get("total_cards"),
                                        "target_icon": step["meta"].get("target_icon"),
                                        "current_icon": step["meta"].get("after_icon"),
                                        "matched": matched_after,
                                        "step_type": step_type,
                                    },
                                },
                            }
                        )

                    # Clean up annotated files if not in debug mode
                    if not debug_mode:
                        for annotated_file in annotated_files:
                            try:
                                if os.path.exists(annotated_file):
                                    os.remove(annotated_file)
                            except Exception as e:
                                print(f"Warning: Could not remove annotated file {annotated_file}: {e}")
                    step_images: Dict[str, str] = {}
                    step_image_dimensions: Dict[str, Dict[str, int]] = {}
                    step_counter = 1
                    for step in step_logs:
                        if step["meta"].get("step_type") != "navigate":
                            continue
                        step_key = f"step_{step_counter}"
                        step_images[step_key] = step["after_image"]
                        dims = step.get("after_dimensions")
                        if isinstance(dims, dict):
                            step_image_dimensions[step_key] = dims
                        step_counter += 1
                    if step_images:
                        paged_meta["step_images"] = step_images
                        paged_meta["step_image_dimensions"] = step_image_dimensions
                else:
                    actions = solver(page, solution_data)
                    page.screenshot(path=final_screenshot_path, full_page=True)
                    final_width, final_height = image_dimensions(final_screenshot_path)

                    thinking, annotated_files = generate_model_reasoning(
                        actual_type,
                        solution_data,
                        [screenshot_path, final_screenshot_path],
                        actions=actions,
                    )
                    
                    # Clean up annotated files if not in debug mode
                    if not debug_mode:
                        for annotated_file in annotated_files:
                            try:
                                if os.path.exists(annotated_file):
                                    os.remove(annotated_file)
                            except Exception as e:
                                print(f"Warning: Could not remove annotated file {annotated_file}: {e}")
                    initial_prompt = _choose_default_prompt()
                    conversation = [
                        _build_system_message(),
                        {
                            "from": "human",
                            "value": {
                                "input": initial_prompt,
                                "image": screenshot_path,
                                "challenge_type": actual_type,
                            },
                        },
                        {
                            "from": "gpt",
                            "value": {
                                "response": thinking,
                                "actions": actions,
                            },
                        },
                    ]


            dataset.append(
                {
                    "id": f"captcha_sample_{i}",
                    "requested_type": requested_type,
                    "resolved_type": actual_type,
                    "requested_challenge": requested_type,
                    "actual_challenge": actual_type,
                    "challenge_meta": {
                        "challenge_id": challenge_id,
                        **slider_meta,
                        **icon_meta,
                        **paged_meta,
                        **icon_match_meta,
                        **image_grid_meta,
                    },
                    "images": {
                        "initial": screenshot_path,
                        "final": final_screenshot_path,
                    },
                    "image_dimensions": {
                        "initial": {"width": initial_width, "height": initial_height},
                        "final": {"width": final_width, "height": final_height},
                    },
                    "conversations": conversation,
                }
            )
            
            time.sleep(0.5)
            context.close()
        browser.close()

    with open(output_path, "w") as outfile:
        json.dump(dataset, outfile, indent=2)

    print(f"Dataset successfully generated and saved to {output_path}")


if __name__ == "__main__":
    while True:
        run_id = str(uuid.uuid4())[-4:]
        if not os.path.exists(os.path.join("runs", run_id)):
            break

    output_file_name = "conversations"
    num_samples = 5

    print(f"Recording {num_samples} samples for run {run_id}")
    record_conversational_dataset(num_samples, run_id, output_file_name, challenge_type = None)
