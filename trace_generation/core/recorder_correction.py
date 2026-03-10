"""
Self-correction dataset recording module.
Records multi-turn conversations where models fail initially, then receive correction prompts.
"""

import json
import os
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

import requests
from PIL import Image
from playwright.sync_api import Page, sync_playwright, ViewportSize  # pyright: ignore[reportMissingImports]

from .model_client import GPTAgent
from .action_parser import ActionParser
from .action_executor import ActionExecutor
from .constants import (
    BASE_URL,
    CHALLENGE_ROUTES,
    SYSTEM_PROMPT,
    DEFAULT_PROMPTS,
    FOLLOWUP_PROMPTS,
)
from .config import COMMON_VIEWPORTS
from .solvers import SOLVER_MAP
from .utils import ensure_directories, image_dimensions
from .recorder import detect_challenge_type
from .reasoning import generate_correction_reasoning


class SelfCorrectionRecorder:
    """Records self-correction conversations for CAPTCHA solving."""

    def __init__(self, run_dir: str, server_url: str = BASE_URL):
        """
        Initialize the self-correction recorder.

        Args:
            run_dir: Directory to save recordings
            server_url: CAPTCHA server URL
        """
        self.run_dir = run_dir
        self.server_url = server_url
        self.img_dir = os.path.join(run_dir, "img")

        # Initialize components with system prompt from constants
        self.agent = GPTAgent(system_prompt=SYSTEM_PROMPT)
        self.action_parser = ActionParser()
        self.action_executor = ActionExecutor()

        # Ensure directories exist
        os.makedirs(self.img_dir, exist_ok=True)

    def get_challenge_id_from_page(self, page: Page) -> Optional[str]:
        """Extract challenge ID from the page."""
        try:
            # Method 1: Look for hidden input field
            challenge_id_element = page.locator('input[name="challenge_id"]')
            if challenge_id_element.count() > 0:
                return challenge_id_element.get_attribute('value')

            # Method 2: Look for data attribute
            challenge_id_element = page.locator('[data-challenge-id]')
            if challenge_id_element.count() > 0:
                return challenge_id_element.get_attribute('data-challenge-id')

            # Method 3: Look for JavaScript variable
            challenge_id = page.evaluate("""
                () => {
                    if (typeof window.challengeId !== 'undefined') {
                        return window.challengeId;
                    }
                    if (typeof window.challenge_id !== 'undefined') {
                        return window.challenge_id;
                    }
                    return null;
                }
            """)
            if challenge_id:
                return challenge_id

            print("Warning: Could not find challenge ID on page")
            return None

        except Exception as e:
            print(f"Error extracting challenge ID: {e}")
            return None

    def fetch_challenge_status(self, page: Page, challenge_id: str) -> Dict:
        """Fetch challenge status from the server."""
        try:
            response = requests.get(f"{self.server_url}/status/{challenge_id}")
            if response.ok:
                return response.json()
            else:
                return {}
        except Exception as exc:
            print(f"Error fetching challenge status for {challenge_id}: {exc}")
            return {}

    def fetch_solution(self, challenge_id: str) -> Dict:
        """Fetch solution from the server."""
        try:
            response = requests.get(f"{self.server_url}/solution/{challenge_id}")
            if response.ok:
                return response.json()
            return {}
        except Exception as exc:
            print(f"Error fetching solution for {challenge_id}: {exc}")
            return {}

    def capture_screenshot(self, page: Page, sample_id: str, suffix: str) -> str:
        """Capture and save a screenshot."""
        filename = f"{sample_id}_{suffix}.png"
        filepath = os.path.join(self.img_dir, filename)
        page.screenshot(path=filepath)
        return filename

    def _convert_solver_actions_to_model_format(
        self,
        solver_actions: List[Dict[str, str]],
        image_width: int,
        image_height: int
    ) -> List[str]:
        """
        Convert solver actions (absolute coordinates) to model format (relative coordinates).

        Args:
            solver_actions: Actions from solver with absolute pixel coordinates
            image_width: Width of the screenshot
            image_height: Height of the screenshot

        Returns:
            List of action strings in model output format with relative coordinates
        """
        import re

        converted_actions = []

        for action in solver_actions:
            action_type = action.get("action", "")

            if action_type == "click":
                # Parse: {"action": "click", "point": "<point>x y</point>"}
                point_str = action.get("point", "")
                match = re.search(r'<point>([\d.]+)\s+([\d.]+)</point>', point_str)
                if match:
                    abs_x, abs_y = float(match.group(1)), float(match.group(2))
                    rel_x = abs_x / image_width
                    rel_y = abs_y / image_height
                    converted_actions.append(
                        f"click(point='<relative-point>{rel_x:.4f} {rel_y:.4f}</relative-point>')"
                    )

            elif action_type == "drag":
                # Parse: {"action": "drag", "start_point": "<point>x y</point>", "end_point": "<point>x y</point>"}
                start_str = action.get("start_point", "")
                end_str = action.get("end_point", "")
                start_match = re.search(r'<point>([\d.]+)\s+([\d.]+)</point>', start_str)
                end_match = re.search(r'<point>([\d.]+)\s+([\d.]+)</point>', end_str)
                if start_match and end_match:
                    start_x, start_y = float(start_match.group(1)), float(start_match.group(2))
                    end_x, end_y = float(end_match.group(1)), float(end_match.group(2))
                    rel_start_x = start_x / image_width
                    rel_start_y = start_y / image_height
                    rel_end_x = end_x / image_width
                    rel_end_y = end_y / image_height
                    converted_actions.append(
                        f"drag(start_point='<relative-point>{rel_start_x:.4f} {rel_start_y:.4f}</relative-point>', "
                        f"end_point='<relative-point>{rel_end_x:.4f} {rel_end_y:.4f}</relative-point>')"
                    )

            elif action_type == "type":
                # Parse: {"action": "type", "content": "text"}
                content = action.get("content", "")
                # Escape special characters for the model format
                content_escaped = content.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
                converted_actions.append(f"type(content='{content_escaped}')")

        return converted_actions

    def _get_solver_actions(
        self,
        page: Page,
        captcha_type: str,
        solution_data: Dict,
        execute: bool = False
    ) -> List[Dict[str, str]]:
        """
        Get solver actions from solver without executing them.

        Args:
            page: Playwright page object
            captcha_type: Type of CAPTCHA (text, icon_selection, etc.)
            solution_data: Solution data from /solution endpoint
            execute: Whether to actually execute actions (default: False)

        Returns:
            List of action dictionaries from solver
        """
        try:
            solver = SOLVER_MAP.get(captcha_type)
            if not solver:
                print(f"No solver found for captcha type: {captcha_type}")
                return []

            # Text types expect the plain solution string.
            if captcha_type in ("text", "compact_text"):
                solution_text = solution_data.get("solution", "")
                actions = solver(page, solution_text, execute=execute)
            else:
                actions = solver(page, solution_data, execute=execute)

            return actions if actions else []

        except Exception as e:
            print(f"Error getting solver actions for {captcha_type}: {e}")
            return []

    def run_initial_attempt(
        self,
        page: Page,
        challenge_id: str,
        sample_id: str,
        captcha_type: str
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Run the model's initial attempt to solve the CAPTCHA.

        Returns:
            (success, attempt_data) where attempt_data contains:
                - initial_screenshot
                - after_screenshot
                - model_response
                - actions
                - solver_actions
        """
        attempt_data = {}

        # Capture initial screenshot
        initial_screenshot = self.capture_screenshot(page, sample_id, "initial")
        attempt_data["initial_screenshot"] = initial_screenshot

        # Build initial prompt
        prompt = random.choice(DEFAULT_PROMPTS).strip()

        # Get initial screenshot as PIL image for the agent
        initial_img_path = os.path.join(self.img_dir, initial_screenshot)
        initial_pil = Image.open(initial_img_path)
        image_width, image_height = initial_pil.size

        # Fetch solution and generate correct actions BEFORE model attempts
        solution_data = self.fetch_solution(challenge_id)
        attempt_data["solution_data"] = solution_data

        # Reset agent history
        self.agent.reset()

        # Get model response
        model_response = self.agent(prompt, images=[initial_pil])
        attempt_data["model_response"] = model_response

        # Parse and validate actions (converts relative coords to absolute pixels)
        actions = self.action_parser.parse_response(model_response)
        validated_actions = self.action_parser.validate_actions(actions, image_width, image_height)
        attempt_data["actions"] = [self._action_to_dict(a) for a in validated_actions]

        # Execute actions
        if validated_actions:
            self.action_executor.execute_actions(page, [self._action_to_dict(a) for a in validated_actions])
            page.wait_for_timeout(500)

        # Capture screenshot after actions
        after_screenshot = self.capture_screenshot(page, sample_id, "after_screenshot")
        attempt_data["after_screenshot"] = after_screenshot

        # Check if solved
        status = self.fetch_challenge_status(page, challenge_id)
        success = status.get('status') == 'solved'

        # Get solver actions from solver (execute=False means no actual clicking)
        solver_actions = []
        if not success:
            solver_actions = self._get_solver_actions(
                page, captcha_type, solution_data, execute=False
            )

        # Convert to model format (relative coordinates) for correction prompt
        if solver_actions:
            solver_actions_formatted = self._convert_solver_actions_to_model_format(
                solver_actions, image_width, image_height
            )
            attempt_data["solver_actions_formatted"] = solver_actions_formatted
            attempt_data["solver_actions"] = solver_actions
        else:
            attempt_data["solver_actions_formatted"] = []
            attempt_data["solver_actions"] = []

        return success, attempt_data

    def _format_action_for_display(self, action: Dict) -> str:
        """Format an action dictionary into a readable string for correction prompts."""
        action_type = action.get("type", "unknown")
        if action_type == "click":
            x, y = action.get("x", 0), action.get("y", 0)
            return f"click at ({x}, {y})"
        elif action_type == "drag":
            x, y = action.get("x", 0), action.get("y", 0)
            end_x, end_y = action.get("end_x", 0), action.get("end_y", 0)
            return f"drag from ({x}, {y}) to ({end_x}, {end_y})"
        elif action_type == "type":
            text = action.get("text", "")
            return f"type '{text}'"
        else:
            return f"{action_type}"

    def run_correction_turn(
        self,
        page: Page,
        captcha_type: str,
        attempt_data: Dict,
        solution: Dict
    ) -> Dict:
        """Run the correction turn using the reasoning model on the current failed state."""
        conversations = {
            "model_response": attempt_data.get("model_response", ""),
            "model_actions": [self._format_action_for_display(a) for a in attempt_data.get("actions", [])],
            "solver_actions_formatted": attempt_data.get("solver_actions_formatted", []),
            "solver_actions": attempt_data.get("solver_actions", []),
        }

        after_screenshot_path = os.path.join(self.img_dir, attempt_data["after_screenshot"])
        screenshot_paths = [after_screenshot_path]

        # Generate corrected reasoning on the current failed state.
        correction_prompt, corrected_response = generate_correction_reasoning(
            challenge_type=captcha_type,
            conversations=conversations,
            solution_data=solution,
            screenshot_paths=screenshot_paths
        )

        return {
            "correction_prompt": correction_prompt,
            "corrected_response": corrected_response,
            "solution": solution
        }

    def record_example(
        self,
        captcha_type: str,
        sample_number: int
    ) -> Optional[Dict]:
        """
        Record a single self-correction example.

        Returns:
            Dataset example dict if model failed (and correction was recorded),
            None if model succeeded (skip this example).
        """
        sample_id = f"captcha_sample_{sample_number}"
        challenge_route = CHALLENGE_ROUTES[captcha_type]
        challenge_url = f"{self.server_url}{challenge_route}"

        # Rotate through viewports based on sample number
        viewport = COMMON_VIEWPORTS[sample_number % len(COMMON_VIEWPORTS)]

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                viewport=cast(ViewportSize, viewport),
                ignore_https_errors=True,
            )
            page = context.new_page()

            try:
                # Navigate to challenge
                page.goto(challenge_url)
                page.wait_for_load_state("networkidle")

                # Extract challenge ID from page DOM
                challenge_id = self.get_challenge_id_from_page(page)
                if not challenge_id:
                    print(f"Could not extract challenge ID from page for {captcha_type}")
                    browser.close()
                    return None

                # Detect actual challenge type
                actual_type = detect_challenge_type(page)

                # Run initial attempt
                success, attempt_data = self.run_initial_attempt(
                    page, challenge_id, sample_id, actual_type
                )

                # If model succeeded, skip this example
                if success:
                    print(f"  Model succeeded on {sample_id}, skipping...")
                    browser.close()
                    return None
                else:
                    print(f"  Model failed on {sample_id}, recording correction...")

                # Fetch solution
                solution = self.fetch_solution(challenge_id)

                # Run correction turn
                correction_data = self.run_correction_turn(
                    page, actual_type, attempt_data, solution
                )

                # Build dataset example
                example = self._build_dataset_example(
                    sample_id,
                    captcha_type,
                    actual_type,
                    challenge_id,
                    attempt_data,
                    correction_data
                )

                browser.close()
                return example

            except Exception as e:
                print(f"Error recording example {sample_id}: {e}")
                import traceback
                traceback.print_exc()
                browser.close()
                return None

    def _build_dataset_example(
        self,
        sample_id: str,
        requested_type: str,
        actual_type: str,
        challenge_id: str,
        attempt_data: Dict,
        correction_data: Dict
    ) -> Dict:
        """Build the final dataset example structure."""
        # Build conversations list
        conversations = []

        # System message
        conversations.append({
            "from": "system",
            "value": {"content": SYSTEM_PROMPT}
        })

        # Initial user message
        conversations.append({
            "from": "human",
            "value": {
                "input": random.choice(DEFAULT_PROMPTS).strip(),
                "image": attempt_data["initial_screenshot"],
                "challenge_type": actual_type
            }
        })

        # Initial model response (failed attempt)
        # Convert actions to ShareGPT format
        sharegpt_actions = [self._action_dict_to_sharegpt_format(a) for a in attempt_data["actions"]]
        conversations.append({
            "from": "gpt",
            "value": {
                "response": attempt_data["model_response"],
                "actions": sharegpt_actions,
                "convert_actions": False
            }
        })

        # Correction message from human
        conversations.append({
            "from": "human",
            "value": {
                "input": random.choice(FOLLOWUP_PROMPTS).strip(),
                "actual_input": correction_data["correction_prompt"],
                "image": attempt_data["after_screenshot"],
            }
        })

        # Corrected response from model
        conversations.append({
            "from": "gpt",
            "value": {
                "response": correction_data["corrected_response"],
                "actions": attempt_data["solver_actions"],
                "convert_actions": True
            }
        })

        # Get image dimensions
        initial_img_path = os.path.join(self.img_dir, attempt_data["initial_screenshot"])
        img_width, img_height = image_dimensions(initial_img_path)

        # Build full example
        example = {
            "id": sample_id,
            "requested_type": requested_type,
            "resolved_type": actual_type,
            "requested_challenge": requested_type,
            "actual_challenge": actual_type,
            "challenge_meta": {
                "challenge_id": challenge_id,
                "solution": correction_data["solution"]
            },
            "images": {
                "initial": attempt_data["initial_screenshot"],
                "final": attempt_data["after_screenshot"]
            },
            "image_dimensions": {
                "initial": {"width": img_width, "height": img_height},
                "final": {"width": img_width, "height": img_height}
            },
            "conversations": conversations,
            "metadata": {
                "initial_success": False,
                "correction_applied": True
            }
        }

        return example

    def _action_to_dict(self, action) -> Dict:
        """Convert Action object to dictionary for execution."""
        return {
            "type": action.type,
            "x": action.x,
            "y": action.y,
            "end_x": action.end_x,
            "end_y": action.end_y,
            "text": action.text,
            "duration": action.duration,
            "coord_mode": getattr(action, "coord_mode", "absolute")
        }

    def _action_dict_to_sharegpt_format(self, action_dict: Dict) -> Dict:
        """
        Convert action dictionary to ShareGPT format.

        Converts from execution format (type, x, y) to ShareGPT format (action, point).
        """
        action_type = action_dict.get("type")
        result = {"action": action_type}

        if action_type == "click":
            x, y = action_dict.get("x"), action_dict.get("y")
            if x is not None and y is not None:
                result["point"] = f"<point>{x} {y}</point>"

        elif action_type == "drag":
            x, y = action_dict.get("x"), action_dict.get("y")
            end_x, end_y = action_dict.get("end_x"), action_dict.get("end_y")
            if all(v is not None for v in [x, y, end_x, end_y]):
                result["start_point"] = f"<point>{x} {y}</point>"
                result["end_point"] = f"<point>{end_x} {end_y}</point>"

        elif action_type == "type":
            text = action_dict.get("text")
            if text is not None:
                result["content"] = text

        elif action_type == "scroll":
            x, y = action_dict.get("x"), action_dict.get("y")
            if x is not None and y is not None:
                result["point"] = f"<point>{x} {y}</point>"
            # Note: direction would need to be stored if we want to support it

        return result
