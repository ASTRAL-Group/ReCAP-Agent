from __future__ import annotations

import logging
import random
import threading
import uuid
from typing import Any, Dict, List, Optional, Tuple

from flask import jsonify

from challenges import (
    generate_compact_text_captcha_layout,
    generate_icon_captcha_layout,
    generate_icon_match_captcha_layout,
    generate_image_grid_captcha_layout,
    generate_slider_captcha_layout,
    generate_paged_captcha_layout,
    generate_text_captcha_layout,
    get_random_text_captcha_entry,
    validate_click_position,
)

logger = logging.getLogger(__name__)


class ChallengeManager:
    """Encapsulates challenge state storage and verification logic."""

    _CHALLENGE_TYPES: Tuple[str, ...] = (
        "text",
        "compact_text",
        "icon_selection",
        "paged",
        "slider",
        "image_grid",
        "icon_match",
    )

    _DEFAULT_STATIC_SEED = 1337

    def __init__(self, text_dataset, static_seed: Optional[int] = None):
        self._text_dataset = text_dataset
        self._states: Dict[str, Dict[str, Any]] = {}
        self._static_seed = static_seed if static_seed is not None else self._DEFAULT_STATIC_SEED
        self._static_rng = random.Random(self._static_seed)
        self._static_rng_lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #
    @property
    def dataset_size(self) -> int:
        return len(self._text_dataset) if self._text_dataset else 0

    @property
    def states(self) -> Dict[str, Dict[str, Any]]:
        return self._states

    # ------------------------------------------------------------------ #
    # Challenge creation helpers
    # ------------------------------------------------------------------ #
    def random_challenge_type(self) -> str:
        return random.choice(self._CHALLENGE_TYPES)

    def build_static_challenge(self) -> Tuple[str, int]:
        """
        Build a challenge using a deterministic random sequence so the same
        series of CAPTCHA layouts is returned every time the server starts.
        """

        with self._static_rng_lock:
            original_state = random.getstate()
            try:
                # Replace the module-level RNG state with the static generator state.
                random.setstate(self._static_rng.getstate())
                challenge_type = random.choice(self._CHALLENGE_TYPES)
                html, status = self.build_challenge(challenge_type, dataset_scope="static")
                if status == 200 and isinstance(html, str):
                    client_seed = self._static_rng.getrandbits(32)
                    html = self._inject_static_client_rng(html, client_seed)
                result = (html, status)
                # Persist the consumed RNG state back into the static generator.
                self._static_rng.setstate(random.getstate())
            finally:
                random.setstate(original_state)

        return result

    def _inject_static_client_rng(self, html: str, seed: int) -> str:
        """Inject a deterministic RNG helper for client-side positioning."""

        sanitized_seed = seed & 0xFFFFFFFF
        script = f"""
<script>
(function() {{
    if (window.__CAPTCHA_STATIC_RANDOM) {{
        return;
    }}
    var seed = {sanitized_seed};
    function mulberry32(a) {{
        var t = a >>> 0;
        return function() {{
            t = (t + 0x6D2B79F5) | 0;
            var r = Math.imul(t ^ (t >>> 15), 1 | t);
            r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
            return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
        }};
    }}
    window.__CAPTCHA_STATIC_RANDOM = mulberry32(seed);
}})();
</script>
"""
        lower_html = html.lower()
        body_start = lower_html.find("<body")
        if body_start != -1:
            body_tag_end = lower_html.find(">", body_start)
            if body_tag_end != -1:
                insertion_point = body_tag_end + 1
                return f"{html[:insertion_point]}{script}{html[insertion_point:]}"

        closing_tag = "</body>"
        insertion_point = lower_html.rfind(closing_tag)
        if insertion_point == -1:
            return f"{html}{script}"
        return f"{html[:insertion_point]}{script}{html[insertion_point:]}"

    def reset_static_sequence(self) -> None:
        """Reset the deterministic RNG back to the initial seed."""

        with self._static_rng_lock:
            self._static_rng.seed(self._static_seed)

    def build_challenge(
        self,
        challenge_type: str,
        requires_submit: Optional[bool] = None,
        dataset_scope: str = "dynamic",
    ) -> Tuple[str, int]:
        builders = {
            "text": self._build_text_challenge,
            "compact_text": self._build_compact_text_challenge,
            "icon_selection": self._build_icon_challenge,
            "paged": self._build_paged_challenge,
            "icon_match": self._build_icon_match_challenge,
            "slider": self._build_slider_challenge,
            "image_grid": self._build_image_grid_challenge,
        }
        builder = builders.get(challenge_type)
        if builder is None:
            return "Unknown challenge type.", 400
        # Pass requires_submit to builders that support it
        if challenge_type in {"icon_selection", "slider"}:
            return builder(requires_submit=requires_submit, dataset_scope=dataset_scope)
        return builder(dataset_scope=dataset_scope)

    def _build_text_challenge(self, dataset_scope: str = "dynamic") -> Tuple[str, int]:
        return self._build_text_like_challenge(compact=False, dataset_scope=dataset_scope)

    def _build_compact_text_challenge(self, dataset_scope: str = "dynamic") -> Tuple[str, int]:
        return self._build_text_like_challenge(compact=True, dataset_scope=dataset_scope)

    def _build_text_like_challenge(self, compact: bool, dataset_scope: str = "dynamic") -> Tuple[str, int]:
        if not self._text_dataset:
            return "Error: No CAPTCHA data available", 500

        entry = get_random_text_captcha_entry(self._text_dataset, dataset_scope=dataset_scope)
        if not entry:
            return "Error: No CAPTCHA data available", 500

        layout_fn = (
            generate_compact_text_captcha_layout if compact else generate_text_captcha_layout
        )
        html_content, layout_metadata = layout_fn(entry["image_index"])

        challenge_id = self._register_state(
            {
                "type": "compact_text" if compact else "text",
                "answer": entry["answer"],
                "status": "unsolved",
                "failed_attempts": 0,
                "image_index": entry["image_index"],
                "dataset_scope": dataset_scope,
                "metadata": layout_metadata,
            }
        )

        html_content = html_content.replace("PLACEHOLDER_CHALLENGE_ID", challenge_id)
        return html_content, 200

    def _build_icon_challenge(
        self, requires_submit: Optional[bool] = None, dataset_scope: str = "dynamic"
    ) -> Tuple[str, int]:
        html_content, layout_metadata = generate_icon_captcha_layout(
            requires_submit=requires_submit, dataset_scope=dataset_scope
        )
        requires_submit = layout_metadata.get("requires_submit", True)

        challenge_id = self._register_state(
            {
                "type": "icon_selection",
                "target_icon": layout_metadata["target_icon"],
                "target_icon_name": layout_metadata["target_icon_name"],
                "status": "unsolved",
                "failed_attempts": 0,
                "requires_submit": requires_submit,
                "dataset_scope": dataset_scope,
                "metadata": layout_metadata,
            }
        )

        html_content = html_content.replace("PLACEHOLDER_CHALLENGE_ID", challenge_id)
        return html_content, 200

    def _build_paged_challenge(self, dataset_scope: str = "dynamic") -> Tuple[str, int]:
        html_content, layout_metadata = generate_paged_captcha_layout(dataset_scope=dataset_scope)

        challenge_id = self._register_state(
            {
                "type": "paged",
                "mode": layout_metadata.get("mode"),
                "data_source": layout_metadata.get("data_source"),
                "target_icon": layout_metadata["target_icon"],
                "target_icon_name": layout_metadata["target_icon_name"],
                "card_icons": layout_metadata.get("card_icons", []),
                "card_images": layout_metadata.get("card_images", []),
                "target_category": layout_metadata.get("target_category"),
                "instruction": layout_metadata.get("instruction"),
                "instruction_text": layout_metadata.get("instruction_text"),
                "challenge_title": layout_metadata.get("challenge_title"),
                "challenge_subtitle": layout_metadata.get("challenge_subtitle"),
                "status": "unsolved",
                "failed_attempts": 0,
                "requires_submit": True,
                "total_cards": layout_metadata.get("total_cards"),
                "dataset_scope": dataset_scope,
                "metadata": layout_metadata,
            }
        )

        html_content = html_content.replace("PLACEHOLDER_CHALLENGE_ID", challenge_id)
        return html_content, 200

    def _build_icon_match_challenge(self, dataset_scope: str = "dynamic") -> Tuple[str, int]:
        html_content, layout_metadata = generate_icon_match_captcha_layout()
        requires_submit = layout_metadata.get("requires_submit", False)

        challenge_id = self._register_state(
            {
                "type": "icon_match",
                "pair_icon": layout_metadata["pair_icon"],
                "pair_icon_name": layout_metadata["pair_icon_name"],
                "match_pair_ids": layout_metadata["match_pair_ids"],
                "status": "unsolved",
                "failed_attempts": 0,
                "requires_submit": requires_submit,
                "metadata": layout_metadata,
            }
        )

        html_content = html_content.replace("PLACEHOLDER_CHALLENGE_ID", challenge_id)
        return html_content, 200
    
    def _build_slider_challenge(
        self, requires_submit: Optional[bool] = None, dataset_scope: str = "dynamic"
    ) -> Tuple[str, int]:
        html_content, layout_metadata = generate_slider_captcha_layout(
            requires_submit=requires_submit, dataset_scope=dataset_scope
        )
        requires_submit = layout_metadata.get("requires_submit", True)

        challenge_id = self._register_state(
            {
                "type": "slider",
                "target_position": layout_metadata["target_position"],
                "tolerance": layout_metadata["tolerance"],
                "track_width": layout_metadata["track_width"],
                "track_height": layout_metadata["track_height"],
                "slider_size": layout_metadata["slider_size"],
                "puzzle_width": layout_metadata.get("puzzle_width"),
                "puzzle_height": layout_metadata.get("puzzle_height"),
                "piece_size": layout_metadata.get("piece_size"),
                "piece_top": layout_metadata.get("piece_top"),
                "hole_left": layout_metadata.get("hole_left"),
                "background_image": layout_metadata.get("background_image"),
                "puzzle_mask": layout_metadata.get("puzzle_mask"),
                "status": "unsolved",
                "failed_attempts": 0,
                "requires_submit": requires_submit,
                "dataset_scope": dataset_scope,
                "metadata": layout_metadata,
            }
        )

        html_content = html_content.replace("PLACEHOLDER_CHALLENGE_ID", challenge_id)
        return html_content, 200

    def _build_image_grid_challenge(self, dataset_scope: str = "dynamic") -> Tuple[str, int]:
        html_content, layout_metadata = generate_image_grid_captcha_layout(dataset_scope=dataset_scope)

        challenge_id = self._register_state(
            {
                "type": "image_grid",
                "instruction": layout_metadata["instruction"],
                "target_category": layout_metadata["target_category"],
                "correct_tiles": layout_metadata["correct_tiles"],
                "images": layout_metadata["images"],
                "status": "unsolved",
                "failed_attempts": 0,
                "dataset_scope": dataset_scope,
                "metadata": layout_metadata,
            }
        )

        html_content = html_content.replace("PLACEHOLDER_CHALLENGE_ID", challenge_id)
        return html_content, 200

    def _register_state(self, state: Dict[str, Any]) -> str:
        challenge_id = str(uuid.uuid4())
        self._states[challenge_id] = state
        return challenge_id

    # ------------------------------------------------------------------ #
    # Verification and status helpers
    # ------------------------------------------------------------------ #
    def verify_submission(self, challenge_id: str, payload: Dict[str, Any]):
        if challenge_id not in self._states:
            return jsonify({"success": False, "message": "Invalid challenge ID."}), 400

        challenge = self._states[challenge_id]

        if challenge["status"] == "solved":
            return jsonify({"success": True, "message": "CAPTCHA already solved!"})

        challenge_type = challenge["type"]
        if challenge_type in {"text", "compact_text"}:
            submission = payload.get("submission", "").strip()
            if submission.lower() == challenge["answer"].lower():
                challenge["status"] = "solved"
                return jsonify({"success": True, "message": "CAPTCHA solved!"})

            challenge["failed_attempts"] += 1
            return jsonify({"success": False, "message": "Incorrect, please try again."})

        if challenge_type == "icon_selection":
            return self._verify_icon_challenge(challenge, payload)

        if challenge_type == "paged":
            return self._verify_paged_challenge(challenge, payload)

        if challenge_type == "icon_match":
            return self._verify_icon_match_challenge(challenge, payload)

        if challenge_type == "slider":
            return self._verify_slider_challenge(challenge, payload)

        if challenge_type == "image_grid":
            return self._verify_image_grid_challenge(challenge, payload)

        return jsonify({"success": False, "message": "Unknown CAPTCHA type."}), 400

    def _verify_icon_challenge(self, challenge: Dict[str, Any], payload: Dict[str, Any]):
        click_position = payload.get("click_position")
        if not click_position:
            challenge["failed_attempts"] += 1
            return jsonify(
                {"success": False, "message": "No click position provided. Please click on the canvas."}
            )

        click_x = click_position.get("x", 0)
        click_y = click_position.get("y", 0)

        target_icon = challenge["target_icon"]
        positions = challenge["metadata"].get("positions", [])
        all_icons = challenge["metadata"].get("all_icons", [])

        target_icon_index = next((i for i, icon in enumerate(all_icons) if icon == target_icon), -1)
        if target_icon_index < 0 or target_icon_index >= len(positions):
            challenge["failed_attempts"] += 1
            return jsonify(
                {"success": False, "message": "Error: Could not find target icon position."}
            )

        target_x, target_y = positions[target_icon_index]
        icon_size = challenge["metadata"].get("icon_size", 70)
        if "icon_size" not in challenge["metadata"]:
            css_vars = challenge["metadata"].get("css_variables", "")
            import re

            match = re.search(r"--icon-size:\s*(\d+)px", css_vars)
            icon_size = int(match.group(1)) if match else 70
        logger.debug(
            "Click validation: click=(%s, %s) target=(%s, %s) size=%s",
            click_x,
            click_y,
            target_x,
            target_y,
            icon_size,
        )

        if validate_click_position(click_x, click_y, target_x, target_y, icon_size, tolerance=20):
            challenge["status"] = "solved"
            return jsonify({"success": True, "message": "CAPTCHA solved!"})

        challenge["failed_attempts"] += 1
        return jsonify({"success": False, "message": "Incorrect. Please try again."})

    def _verify_paged_challenge(self, challenge: Dict[str, Any], payload: Dict[str, Any]):
        selected_icon = payload.get("selected_icon")
        current_index = payload.get("current_index")
        metadata = challenge.get("metadata", {})
        card_icons = challenge.get("card_icons") or metadata.get("card_icons", [])

        # Derive selection from index when possible to avoid spoofed payloads
        if selected_icon is None and card_icons and current_index is not None:
            try:
                idx = int(current_index)
            except (TypeError, ValueError):
                idx = None
            if idx is not None and 0 <= idx < len(card_icons):
                selected_icon = card_icons[idx]

        if not selected_icon:
            challenge["failed_attempts"] += 1
            return jsonify(
                {
                    "success": False,
                    "message": "No card selected. Slide to the requested card and submit your choice.",
                }
            )

        if card_icons and current_index is not None:
            try:
                idx = int(current_index)
            except (TypeError, ValueError):
                idx = None
            if idx is None or idx < 0 or idx >= len(card_icons) or card_icons[idx] != selected_icon:
                challenge["failed_attempts"] += 1
                return jsonify(
                    {
                        "success": False,
                        "message": "Selection mismatch. Use the arrows to highlight a card, then submit.",
                    }
                )

        if selected_icon == challenge.get("target_icon"):
            challenge["status"] = "solved"
            return jsonify({"success": True, "message": "CAPTCHA solved!"})

        challenge["failed_attempts"] += 1
        return jsonify(
            {
                "success": False,
                "message": "That's not the requested card. Slide through the cards and try again.",
            }
        )

    def _verify_icon_match_challenge(self, challenge: Dict[str, Any], payload: Dict[str, Any]):
        match_attempt = payload.get("match_attempt")
        if not match_attempt:
            challenge["failed_attempts"] += 1
            return jsonify(
                {
                    "success": False,
                    "message": "No drag data provided. Drag one matching icon onto the other.",
                }
            )

        source_id = match_attempt.get("source_id")
        target_id = match_attempt.get("target_id")
        drop_position = match_attempt.get("drop_position") or {}
        drop_x = drop_position.get("x")
        drop_y = drop_position.get("y")

        if not source_id or not target_id or drop_x is None or drop_y is None:
            challenge["failed_attempts"] += 1
            return jsonify(
                {
                    "success": False,
                    "message": "Incomplete drag data. Please try again.",
                }
            )

        required_pair = set(challenge.get("match_pair_ids", []))
        attempt_pair = {source_id, target_id}
        if required_pair != attempt_pair:
            challenge["failed_attempts"] += 1
            return jsonify(
                {
                    "success": False,
                    "message": "Those icons don't match. Identify the identical pair.",
                }
            )

        pieces = challenge.get("metadata", {}).get("pieces", [])
        piece_by_id = {piece["id"]: piece for piece in pieces}
        target_piece = piece_by_id.get(target_id)

        if not target_piece:
            challenge["failed_attempts"] += 1
            return jsonify(
                {
                    "success": False,
                    "message": "Error: target icon not found.",
                }
            )

        icon_size = target_piece.get("size", challenge.get("metadata", {}).get("icon_size", 60))
        tolerance = challenge.get("metadata", {}).get("tolerance", 24)

        target_center_x = target_piece["x"] + icon_size / 2
        target_center_y = target_piece["y"] + icon_size / 2

        delta_x = drop_x - target_center_x
        delta_y = drop_y - target_center_y
        distance_sq = delta_x * delta_x + delta_y * delta_y

        if distance_sq <= tolerance * tolerance:
            challenge["status"] = "solved"
            return jsonify({"success": True, "message": "Great! Icons matched successfully."})

        challenge["failed_attempts"] += 1
        return jsonify(
            {
                "success": False,
                "message": "Almost! Drag the icon right on top of its twin.",
            }
        )

    def _verify_slider_challenge(self, challenge: Dict[str, Any], payload: Dict[str, Any]):
        slider_position = payload.get("slider_position")
        if slider_position is None:
            challenge["failed_attempts"] += 1
            return jsonify(
                {"success": False, "message": "No slider position provided. Please drag the slider."}
            )
        try:
            slider_position = float(slider_position)
        except (TypeError, ValueError):
            challenge["failed_attempts"] += 1
            return jsonify({"success": False, "message": "Invalid slider position. Please try again."})

        target_position = challenge.get("target_position", 0)
        tolerance = challenge.get("tolerance", 20)
        distance = abs(slider_position - target_position)

        if distance <= tolerance:
            challenge["status"] = "solved"
            return jsonify({"success": True, "message": "CAPTCHA solved!"})

        challenge["failed_attempts"] += 1
        return jsonify({"success": False, "message": "Incorrect position. Please try again."})

    def _verify_image_grid_challenge(self, challenge: Dict[str, Any], payload: Dict[str, Any]):
        selected_tiles = payload.get("selected_tiles", [])
        if not isinstance(selected_tiles, list):
            challenge["failed_attempts"] += 1
            return jsonify({"success": False, "message": "Invalid tile selection format."})
        try:
            selected_tiles = [int(tile) for tile in selected_tiles]
        except (TypeError, ValueError):
            challenge["failed_attempts"] += 1
            return jsonify({"success": False, "message": "Invalid tile selection values."})
        selected_tiles = [tile for tile in selected_tiles if 0 <= tile <= 8]

        correct_tiles = challenge.get("correct_tiles", [])

        set_selected = set(selected_tiles)
        set_correct = set(correct_tiles)

        # no tiles to select
        if len(set_selected) == 0 and len(set_correct) == 0:
            challenge["status"] = "solved"
            return jsonify({"success": True, "message": "Image Grid verification successful!"})

        challenge["selected_tiles"] = selected_tiles  # Store the latest selected tiles

        intersection = len(set_selected & set_correct)
        union = len(set_selected | set_correct)

        if union > 0:
            jaccard_index = intersection / union
            if jaccard_index >= 0.75:
                challenge["status"] = "solved"
                return jsonify({"success": True, "message": "Image Grid verification successful!"})

        challenge["failed_attempts"] += 1
        return jsonify({"success": False, "message": "Verification failed. Please try again."})

    # ------------------------------------------------------------------ #
    # Status/solution helpers
    # ------------------------------------------------------------------ #
    def build_status_response(self, challenge_id: str):
        if challenge_id not in self._states:
            return jsonify({"error": "Challenge not found."}), 404

        challenge = self._states[challenge_id]
        response = {
            "challenge_id": challenge_id,
            "type": challenge["type"],
            "status": challenge["status"],
            "failed_attempts": challenge["failed_attempts"],
        }

        if challenge["type"] in {"text", "compact_text"}:
            response["image_index"] = challenge["image_index"]
        elif challenge["type"] == "icon_selection":
            response["target_icon"] = challenge["target_icon"]
            response["target_icon_name"] = challenge["target_icon_name"]
            metadata = challenge.get("metadata", {})
            if metadata:
                positions = metadata.get("positions")
                if positions:
                    response["positions"] = positions
                all_icons = metadata.get("all_icons")
                if all_icons:
                    response["all_icons"] = all_icons
                icon_size = metadata.get("icon_size")
                if icon_size is not None:
                    response["icon_size"] = icon_size
                canvas_dimensions = metadata.get("canvas_dimensions")
                if canvas_dimensions:
                    response["canvas_dimensions"] = canvas_dimensions
            response["requires_submit"] = challenge.get("requires_submit", True)
        elif challenge["type"] == "paged":
            response["target_icon"] = challenge["target_icon"]
            response["target_icon_name"] = challenge["target_icon_name"]
            response["mode"] = challenge.get("mode")
            response["data_source"] = challenge.get("data_source")
            response["target_category"] = challenge.get("target_category")
            response["instruction"] = challenge.get("instruction")
            response["instruction_text"] = challenge.get("instruction_text")
            response["card_icons"] = challenge.get("card_icons", [])
            response["card_images"] = challenge.get("card_images", [])
            response["challenge_title"] = challenge.get("challenge_title")
            response["challenge_subtitle"] = challenge.get("challenge_subtitle")
            response["total_cards"] = challenge.get("total_cards")
            response["requires_submit"] = challenge.get("requires_submit", True)
            metadata = challenge.get("metadata", {})
            if metadata:
                response["card_backgrounds"] = metadata.get("card_backgrounds")
        elif challenge["type"] == "icon_match":
            response["pair_icon"] = challenge["pair_icon"]
            response["pair_icon_name"] = challenge["pair_icon_name"]
            response["match_pair_ids"] = challenge.get("match_pair_ids", [])
            metadata = challenge.get("metadata", {})
            if metadata:
                response["pieces"] = metadata.get("pieces")
                response["tolerance"] = metadata.get("tolerance")
                response["canvas_dimensions"] = metadata.get("canvas_dimensions")
                response["icon_size"] = metadata.get("icon_size")
                response["requires_submit"] = metadata.get("requires_submit", False)
        elif challenge["type"] == "slider":
            response.update(
                {
                    "target_position": challenge["target_position"],
                    "tolerance": challenge["tolerance"],
                    "track_width": challenge["track_width"],
                    "slider_size": challenge["slider_size"],
                    "track_height": challenge["track_height"],
                    "puzzle_width": challenge.get("puzzle_width"),
                    "puzzle_height": challenge.get("puzzle_height"),
                    "piece_size": challenge.get("piece_size"),
                    "piece_top": challenge.get("piece_top"),
                    "hole_left": challenge.get("hole_left"),
                    "background_image": challenge.get("background_image"),
                    "puzzle_mask": challenge.get("puzzle_mask"),
                    "requires_submit": challenge.get("requires_submit", True),
                }
            )
        elif challenge["type"] == "image_grid":
            response.update(
                {
                    "instruction": challenge["instruction"],
                    "target_category": challenge["target_category"],
                    "correct_tiles": challenge["correct_tiles"],
                    "images": challenge["images"],
                    "selected_tiles": challenge.get("selected_tiles", []),
                }
            )

        return jsonify(response)

    def get_image_grid_data(self, challenge_id: str):
        if challenge_id not in self._states:
            return jsonify({"error": "Challenge not found."}), 404

        challenge = self._states[challenge_id]
        if challenge["type"] != "image_grid":
            return jsonify({"error": "Invalid challenge type."}), 400

        return jsonify(
            {
                "instruction": challenge["instruction"],
                "target_category": challenge["target_category"],
                "correct_tiles": challenge["correct_tiles"],
                "images": challenge["images"],
            }
        )

    def get_solution(self, challenge_id: str):
        if challenge_id not in self._states:
            return jsonify({"error": "Challenge not found."}), 404

        challenge = self._states[challenge_id]
        ctype = challenge["type"]

        if ctype in {"text", "compact_text"}:
            return jsonify({"solution": challenge["answer"]})
        if ctype == "icon_selection":
            return jsonify({"solution": challenge["target_icon"]})
        if ctype == "paged":
            return jsonify(
                {
                    "solution": challenge["target_icon"],
                    "target_icon_name": challenge.get("target_icon_name"),
                    "card_icons": challenge.get("card_icons", []),
                    "mode": challenge.get("mode"),
                    "data_source": challenge.get("data_source"),
                    "card_images": challenge.get("card_images", []),
                    "target_category": challenge.get("target_category"),
                    "instruction": challenge.get("instruction"),
                    "instruction_text": challenge.get("instruction_text"),
                    "challenge_title": challenge.get("challenge_title"),
                    "challenge_subtitle": challenge.get("challenge_subtitle"),
                    "total_cards": challenge.get("total_cards"),
                }
            )
        if ctype == "icon_match":
            return jsonify(
                {
                    "solution": challenge.get("match_pair_ids"),
                    "pair_icon": challenge.get("pair_icon"),
                }
            )
        if ctype == "slider":
            return jsonify(
                {
                    "solution": challenge["target_position"],
                    "tolerance": challenge["tolerance"],
                    "track_width": challenge["track_width"],
                }
            )
        if ctype == "image_grid":
            return jsonify(
                {
                    "solution": challenge["correct_tiles"],
                    "instruction": challenge["instruction"],
                    "target_category": challenge["target_category"],
                }
            )

        return jsonify({"error": "Unknown CAPTCHA type."}), 400

    # ------------------------------------------------------------------ #
    # Asset helpers
    # ------------------------------------------------------------------ #
    def get_text_captcha_image(self, image_index: int):
        return self._text_dataset[image_index]["image"]
