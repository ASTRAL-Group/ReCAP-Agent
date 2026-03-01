from __future__ import annotations

import glob
import io
import os

from flask import Blueprint, current_app, redirect, request, send_file, send_from_directory, url_for
from PIL import Image, ImageDraw, ImageFont

from challenges.common import split_items_by_scope

from .challenge_manager import ChallengeManager


def create_routes(manager: ChallengeManager) -> Blueprint:
    bp = Blueprint("captcha", __name__)

    def _asset_path(*parts: str) -> str:
        return os.path.abspath(os.path.join(current_app.root_path, "..", *parts))

    def _render_challenge(challenge_type: str):
        # Parse requires_submit query parameter
        requires_submit_param = request.args.get("requires_submit")
        requires_submit = None
        if requires_submit_param is not None:
            requires_submit = requires_submit_param.lower() in {"true", "1", "yes"}
        
        html, status = manager.build_challenge(challenge_type, requires_submit=requires_submit)
        return (html, status) if status != 200 else html

    @bp.route("/")
    def index():
        return redirect(url_for("captcha.random_challenge"))

    @bp.route("/challenge")
    def random_challenge():
        captcha_type = manager.random_challenge_type()
        return _render_challenge(captcha_type)

    @bp.route("/challenge/static")
    def static_sequence_challenge():
        reset_flag = request.args.get("reset")
        if reset_flag and reset_flag.lower() in {"1", "true", "yes", "restart"}:
            manager.reset_static_sequence()
        html, status = manager.build_static_challenge()
        return (html, status) if status != 200 else html

    @bp.route("/challenge/text")
    def challenge_text():
        return _render_challenge("text")

    @bp.route("/challenge/compact")
    def challenge_compact():
        return _render_challenge("compact_text")

    @bp.route("/challenge/icon")
    def challenge_icon():
        return _render_challenge("icon_selection")

    @bp.route("/challenge/paged")
    def challenge_paged():
        return _render_challenge("paged")

    @bp.route("/challenge/icon-slider")
    def challenge_icon_slider():
        # Legacy alias
        return _render_challenge("paged")

    @bp.route("/challenge/icon-match")
    def challenge_icon_match():
        return _render_challenge("icon_match")

    @bp.route("/challenge/slider")
    def challenge_slider():
        return _render_challenge("slider")

    @bp.route("/challenge/image_grid")
    def challenge_image_grid():
        return _render_challenge("image_grid")

    @bp.route("/challenge/image_grid/data/<challenge_id>")
    def image_grid_data(challenge_id: str):
        return manager.get_image_grid_data(challenge_id)

    @bp.route("/verify", methods=["POST"])
    def verify():
        payload = request.get_json(force=True, silent=True) or {}
        challenge_id = payload.get("challenge_id")
        return manager.verify_submission(challenge_id, payload)

    @bp.route("/status/<challenge_id>")
    def status(challenge_id: str):
        return manager.build_status_response(challenge_id)

    @bp.route("/solution/<challenge_id>")
    def solution(challenge_id: str):
        return manager.get_solution(challenge_id)

    @bp.route("/captcha-image/<int:image_index>")
    def serve_captcha_image(image_index: int):
        image = manager.get_text_captcha_image(image_index)
        img_io = io.BytesIO()
        image.save(img_io, "PNG")
        img_io.seek(0)
        return send_file(img_io, mimetype="image/png")

    @bp.route("/image-grid-image/<category>/<int:image_index>")
    def serve_image_grid_image(category: str, image_index: int):
        category_mapping = {
            "Traffic Light": "Traffic Light",
            "Crosswalk": "Crosswalk",
            "Bicycle": "Bicycle",
            "Hydrant": "Hydrant",
            "Car": "Car",
            "Bus": "Bus",
            "Motorcycle": "Motorcycle",
            "Bridge": "Bridge",
            "Palm": "Palm",
            "Stair": "Stair",
            "Chimney": "Chimney",
        }

        dataset_folder = category_mapping.get(category, "Other")
        dataset_path = _asset_path("data", "recaptchav2", "images", dataset_folder)

        if not os.path.exists(dataset_path):
            return _serve_image_grid_placeholder(image_index)

        image_files = sorted(glob.glob(os.path.join(dataset_path, "*.png")))
        if not image_files:
            return _serve_image_grid_placeholder(image_index)

        scope = (request.args.get("scope") or "dynamic").strip().lower()
        scoped_files = split_items_by_scope(image_files, scope)
        if not scoped_files:
            return _serve_image_grid_placeholder(image_index)

        selected_image = scoped_files[image_index % len(scoped_files)]

        try:
            return send_file(selected_image, mimetype="image/png")
        except Exception as exc:  # noqa: BLE001
            current_app.logger.warning("Error serving image %s: %s", selected_image, exc)
            return _serve_image_grid_placeholder(image_index)

    def _serve_image_grid_placeholder(image_index: int):
        img = Image.new("RGB", (100, 100), color="#f0f0f0")
        draw = ImageDraw.Draw(img)

        colors = ["#4285f4", "#34a853", "#fbbc04", "#ea4335", "#9aa0a6"]
        color = colors[image_index % len(colors)]

        draw.rectangle([10, 10, 90, 90], fill=color, outline="#333", width=2)

        try:
            font = ImageFont.load_default()
            draw.text((50, 45), f"{image_index + 1}", fill="white", anchor="mm", font=font)
        except Exception:  # noqa: BLE001
            draw.text((50, 45), f"{image_index + 1}", fill="white", anchor="mm")

        img_io = io.BytesIO()
        img.save(img_io, "PNG")
        img_io.seek(0)
        return send_file(img_io, mimetype="image/png")

    @bp.route("/assets/css/<filename>")
    def serve_css(filename: str):
        return send_from_directory(_asset_path("assets", "css"), filename)

    @bp.route("/assets/js/<filename>")
    def serve_js(filename: str):
        return send_from_directory(_asset_path("assets", "js"), filename)

    @bp.route("/backgrounds/<filename>")
    def serve_background(filename: str):
        return send_from_directory(_asset_path("data", "backgrounds"), filename)

    return bp
