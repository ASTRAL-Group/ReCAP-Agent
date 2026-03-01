import random
from pathlib import Path
from typing import Any, Dict, Tuple, Optional

from .common import COLOR_PALETTES, get_random_background_image_for_scope


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SLIDER_TEMPLATE_PATH = PROJECT_ROOT / "assets" / "template" / "slider.html"
PUZZLE_MASKS_BASE64 = [
    (
        "PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCAxMjAgMTIwJz4KICA8cGF0aCBk"
        "PSdNMjQgMGg0OGExMiAxMiAwIDAgMSAxMiAxMnYxMmExMiAxMiAwIDAgMCAxMiAxMmgxMmExMiAxMiAwIDAgMSAxMiAxMnYx"
        "MmExMiAxMiAwIDAgMS0xMiAxMmgtMTJhMTIgMTIgMCAwIDAtMTIgMTJ2MTJhMTIgMTIgMCAwIDEtMTIgMTJIMjRhMTIgMTIg"
        "MCAwIDEtMTItMTJWODRhMTIgMTIgMCAwIDAtMTItMTJIMGExMiAxMiAwIDAgMSAwLTI0aDEyYTEyIDEyIDAgMCAwIDEyLTEy"
        "VjEyQTEyIDEyIDAgMCAxIDI0IDB6JyBmaWxsPSdibGFjaycvPgo8L3N2Zz4="
    ),
    (
        "PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCAxMjAgMTIwJz4KICA8cGF0aCBk"
        "PSdNMjggMGgzNmExMiAxMiAwIDAgMSAxMiAxMnY4YTE4IDE4IDAgMCAwIDE4IDE4aDhhMTIgMTIgMCAwIDEgMTIgMTJ2MjBh"
        "MTIgMTIgMCAwIDEtMTIgMTJoLThhMTggMTggMCAwIDAtMTggMTh2OGExMiAxMiAwIDAgMS0xMiAxMkgyOGExMiAxMiAwIDAg"
        "MS0xMi0xMlY5MmExOCAxOCAwIDAgMC0xOC0xOEg4YTEyIDEyIDAgMCAxIDAtMjRoMGExOCAxOCAwIDAgMCAxOC0xOFYxMkEx"
        "MiAxMiAwIDAgMSAyOCAweicgZmlsbD0nYmxhY2snLz4KICA8Y2lyY2xlIGN4PSczMicgY3k9JzQ4JyByPScxMCcgZmlsbD0n"
        "d2hpdGUnLz4KICA8Y2lyY2xlIGN4PSc4OCcgY3k9JzcyJyByPScxMCcgZmlsbD0nd2hpdGUnLz4KPC9zdmc+"
    ),
    (
        "PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCAxMjAgMTIwJz4KICA8cGF0aCBk"
        "PSdNMjAgMGg0NGExMiAxMiAwIDAgMSAxMiAxMnYxMGExNiAxNiAwIDAgMCAxNiAxNmgxOGExMCAxMCAwIDAgMSAwIDIwSDky"
        "YTE2IDE2IDAgMCAwLTE2IDE2djE4YTEwIDEwIDAgMCAxLTIwIDBWNzRhMTYgMTYgMCAwIDAtMTYtMTZIMTJhMTIgMTIgMCAw"
        "IDEtMTItMTJWMTJBMTIgMTIgMCAwIDEgMjAgMHonIGZpbGw9J2JsYWNrJy8+Cjwvc3ZnPg=="
    ),
]


def _choose_puzzle_mask() -> str:
    """Pick a random puzzle mask encoded as base64 SVG."""
    return random.choice(PUZZLE_MASKS_BASE64)


def generate_slider_captcha_css_variables(
    track_width: int,
    track_height: int,
    slider_size: int,
    target_position: float,
    tolerance: int,
    puzzle_width: int,
    puzzle_height: int,
    piece_size: int,
    piece_top: int,
    hole_left: float,
    puzzle_mask_base64: str,
) -> Tuple[str, Dict[str, str], str, str, str]:
    """Generate CSS variables and palette data for the slider CAPTCHA."""
    palette = random.choice(COLOR_PALETTES)
    selected_gradient = f"linear-gradient(135deg, {palette['primary']} 0%, {palette['secondary']} 100%)"
    accessible_title = "#1f2937"
    accessible_subtitle = "#334155"
    accessible_text = "#1e293b"

    container_max_width = max(puzzle_width + 160, random.randint(520, 640))
    container_padding = random.randint(28, 40)
    container_radius = random.randint(16, 24)

    background_body = random.choice(["#f1f5f9", "#eef2ff", "#f8fafc", "#ecfeff"])
    background_challenge = random.choice(["#ffffff", "#f8fafc", "#f1f5f9"])
    puzzle_mask = f"url(\"data:image/svg+xml;base64,{puzzle_mask_base64}\")"

    css_vars = f"""
        --primary-color: {palette['primary']};
        --secondary-color: {palette['secondary']};
        --accent-color: {palette['accent']};
        --success-color: {palette['success']};
        --error-color: {palette['error']};
        --neutral-color: {palette['neutral']};
        --background-gradient: linear-gradient(135deg, {palette['primary']} 0%, {palette['accent']} 100%);
        --button-gradient: {selected_gradient};
        --container-max-width: {container_max_width}px;
        --container-padding: {container_padding}px;
        --container-radius: {container_radius}px;
        --track-width: {track_width}px;
        --track-height: {track_height}px;
        --slider-size: {slider_size}px;
        --target-position: {target_position}px;
        --tolerance: {tolerance}px;
        --puzzle-width: {puzzle_width}px;
        --puzzle-height: {puzzle_height}px;
        --piece-size: {piece_size}px;
        --piece-top: {piece_top}px;
        --hole-left: {hole_left}px;
        --puzzle-mask: {puzzle_mask};
        --title-color: {accessible_title};
        --subtitle-color: {accessible_subtitle};
        --instruction-color: {accessible_text};
        --body-background: {background_body};
        --challenge-background: {background_challenge};
    """

    return css_vars, palette, selected_gradient, background_body, background_challenge


def generate_slider_captcha_layout(
    requires_submit: Optional[bool] = None, dataset_scope: str = "dynamic"
) -> Tuple[str, Dict[str, Any]]:
    """Generate a complete slider CAPTCHA layout with puzzle-style interaction."""
    try:
        with SLIDER_TEMPLATE_PATH.open("r", encoding="utf-8") as file:
            html_content = file.read()
    except FileNotFoundError:
        return "Error: Slider template not found", {}

    puzzle_width = random.randint(300, 380)
    puzzle_height = random.randint(180, 240)

    min_piece_size = max(56, int(puzzle_height * 0.28))
    max_piece_size = min(int(puzzle_height * 0.58), puzzle_width - 36)
    if max_piece_size <= min_piece_size:
        max_piece_size = min_piece_size + 8
    max_piece_size = min(max_piece_size, puzzle_width - 24)
    if max_piece_size <= min_piece_size:
        max_piece_size = min_piece_size + 4
    piece_size = random.randint(min_piece_size, max_piece_size)

    piece_vertical_margin = max(18, int(piece_size * 0.3))
    available_vertical = puzzle_height - piece_size - 2 * piece_vertical_margin
    if available_vertical <= 0:
        piece_top = max(0, (puzzle_height - piece_size) // 2)
    else:
        piece_top = random.randint(piece_vertical_margin, piece_vertical_margin + available_vertical)

    track_width = puzzle_width
    track_height = random.randint(52, 60)
    slider_size = random.randint(50, 60)

    horizontal_margin = max(18, int(piece_size * 0.4))
    min_target = piece_size // 2 + horizontal_margin
    max_target = puzzle_width - (piece_size // 2 + horizontal_margin)
    if max_target <= min_target:
        target_position = puzzle_width // 2
    else:
        target_position = random.randint(int(min_target), int(max_target))
    hole_left = target_position - piece_size / 2.0

    tolerance = max(10, int(piece_size * 0.22))
    # Use provided value or default to random choice
    if requires_submit is None:
        requires_submit = random.choice([True, False])


    puzzle_mask_base64 = _choose_puzzle_mask()

    css_variables, palette, _gradient, _body_bg, _challenge_bg = generate_slider_captcha_css_variables(
        track_width,
        track_height,
        slider_size,
        target_position,
        tolerance,
        puzzle_width,
        puzzle_height,
        piece_size,
        piece_top,
        hole_left,
        puzzle_mask_base64,
    )

    background_url_or_none = get_random_background_image_for_scope(dataset_scope)
    background_filename = background_url_or_none.removeprefix("/backgrounds/") if background_url_or_none else ""
    background_url = f"/backgrounds/{background_filename}" if background_filename else ""

    css_injection = f"""
    <style>
        :root {{
            {css_variables}
        }}

        body {{
            background: var(--body-background) !important;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
            color: #0f172a !important;
        }}

        .slider-captcha .captcha-title {{
            color: var(--title-color, #1f2937) !important;
            background: none !important;
            -webkit-text-fill-color: initial !important;
            letter-spacing: -0.01em !important;
        }}

        .slider-captcha .captcha-subtitle {{
            color: var(--subtitle-color, #334155) !important;
            font-weight: 500 !important;
        }}

        .slider-captcha .captcha-instruction {{
            background: rgba(255, 255, 255, 0.92) !important;
            border: 1px solid rgba(148, 163, 184, 0.3) !important;
            box-shadow: 0 6px 16px rgba(148, 163, 184, 0.22) !important;
        }}

        .slider-captcha .captcha-instruction-text {{
            color: var(--instruction-color, #1e293b) !important;
            font-size: 18px !important;
            line-height: 1.6 !important;
        }}

        .puzzle-captcha-area {{
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
            gap: 28px !important;
            background: rgba(255, 255, 255, 0.85) !important;
            border-radius: 22px !important;
            padding: 28px !important;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.45), 0 18px 45px rgba(15, 23, 42, 0.12) !important;
        }}

        .puzzle-wrapper {{
            position: relative !important;
            width: var(--puzzle-width) !important;
            height: var(--puzzle-height) !important;
        }}

        .puzzle-scene {{
            position: relative !important;
            width: 100% !important;
            height: 100% !important;
            background-image: var(--puzzle-image, var(--background-gradient)) !important;
            background-size: cover !important;
            background-position: center !important;
            border-radius: 26px !important;
            overflow: hidden !important;
            box-shadow: 0 22px 40px rgba(15, 23, 42, 0.25) !important;
        }}

        .puzzle-scene::after {{
            content: '' !important;
            position: absolute !important;
            inset: 0 !important;
            background: linear-gradient(180deg, rgba(15, 23, 42, 0.08), transparent 45%, rgba(15, 23, 42, 0.14)) !important;
            pointer-events: none !important;
        }}

        .puzzle-piece,
        .puzzle-hole,
        .puzzle-hole::before,
        .puzzle-hole-highlight {{
            -webkit-mask-image: var(--puzzle-mask);
            mask-image: var(--puzzle-mask);
            -webkit-mask-size: 100% 100%;
            mask-size: 100% 100%;
            -webkit-mask-repeat: no-repeat;
            mask-repeat: no-repeat;
        }}

        .puzzle-piece {{
            position: absolute !important;
            top: var(--piece-top) !important;
            left: 0 !important;
            width: var(--piece-size) !important;
            height: var(--piece-size) !important;
            background-image: var(--puzzle-image, var(--background-gradient)) !important;
            background-size: var(--puzzle-width) var(--puzzle-height) !important;
            background-position: calc(-1 * var(--hole-left)) calc(-1 * var(--piece-top)) !important;
            box-shadow: 0 20px 46px rgba(15, 23, 42, 0.35) !important;
            border-radius: 26px !important;
            transition: box-shadow 0.2s ease !important;
            will-change: transform;
        }}

        .puzzle-piece::after {{
            content: '' !important;
            position: absolute !important;
            inset: 0 !important;
            border: 2px solid rgba(255, 255, 255, 0.85) !important;
            mix-blend-mode: screen !important;
        }}

        .puzzle-piece.dragging {{
            box-shadow: 0 26px 56px rgba(15, 23, 42, 0.45) !important;
        }}

        .puzzle-piece.aligned {{
            box-shadow: 0 26px 56px rgba(34, 197, 94, 0.45) !important;
        }}

        .puzzle-hole {{
            position: absolute !important;
            width: var(--piece-size) !important;
            height: var(--piece-size) !important;
            top: var(--piece-top) !important;
            left: var(--hole-left) !important;
            background: rgba(255, 255, 255, 0.94) !important;
            box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.55) !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            transition: box-shadow 0.3s ease, background 0.3s ease !important;
            border-radius: 26px !important;
            overflow: hidden !important;
        }}

        .puzzle-hole::before {{
            content: '' !important;
            position: absolute !important;
            inset: 0 !important;
            border: 2px dashed rgba(148, 163, 184, 0.7) !important;
            mix-blend-mode: multiply !important;
        }}

        .puzzle-hole.glow {{
            background: rgba(219, 234, 254, 0.9) !important;
            box-shadow: inset 0 0 0 3px rgba(59, 130, 246, 0.65), 0 0 30px rgba(59, 130, 246, 0.45) !important;
        }}

        .puzzle-hole-highlight {{
            width: 100% !important;
            height: 100% !important;
            border-radius: inherit !important;
            background: radial-gradient(circle at center, rgba(59, 130, 246, 0.4), transparent 70%) !important;
            opacity: 0 !important;
            transition: opacity 0.3s ease !important;
        }}

        .puzzle-hole-highlight.active {{
            opacity: 1 !important;
        }}

        .slider-container.puzzle-slider {{
            width: 100% !important;
            display: flex !important;
            justify-content: center !important;
        }}

        .slider-track {{
            position: relative !important;
            width: var(--track-width) !important;
            height: var(--track-height) !important;
            background: rgba(241, 245, 249, 0.95) !important;
            border-radius: 999px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: flex-start !important;
            padding: 0 !important;
            box-shadow: inset 0 2px 6px rgba(148, 163, 184, 0.25) !important;
            overflow: hidden !important;
        }}

        .slider-progress {{
            position: absolute !important;
            left: 0 !important;
            top: 0 !important;
            height: 100% !important;
            width: 0 !important;
            background: linear-gradient(135deg, {palette['primary']} 0%, {palette['accent']} 100%) !important;
            border-radius: inherit !important;
            opacity: 0.9 !important;
            z-index: 0 !important;
            pointer-events: none !important;
            transition: width 0.2s ease !important;
        }}

        .slider-handle {{
            width: var(--slider-size) !important;
            height: var(--slider-size) !important;
            border-radius: 50% !important;
            background: linear-gradient(135deg, {palette['primary']} 0%, {palette['secondary']} 100%) !important;
            border: 3px solid rgba(255, 255, 255, 0.9) !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            color: #fff !important;
            position: absolute !important;
            top: calc(50% - var(--slider-size) / 2) !important;
            left: 0;
            box-shadow: 0 10px 24px rgba(59, 130, 246, 0.35) !important;
            cursor: grab !important;
            z-index: 2 !important;
            touch-action: none !important;
            transition: transform 0.2s ease, box-shadow 0.2s ease !important;
        }}

        .slider-handle .handle-icon {{
            font-size: 22px !important;
            pointer-events: none !important;
        }}

        .slider-handle.dragging {{
            cursor: grabbing !important;
            transform: scale(1.04) !important;
            box-shadow: 0 16px 32px rgba(59, 130, 246, 0.45) !important;
            transition: none !important;
        }}

        .captcha-submit-section {{
            margin-top: 12px !important;
        }}

        @media (max-width: 640px) {{
            .puzzle-wrapper {{
                width: min(var(--puzzle-width), 90vw) !important;
            }}

            .slider-track {{
                width: min(var(--track-width), 90vw) !important;
            }}
        }}
    </style>
    """

    html_content = html_content.replace("</head>", f"{css_injection}</head>")

    if requires_submit:
        submit_section_html = """
            <div class="captcha-submit-section">
                <button type="button" id="submit-btn" class="captcha-submit-btn" disabled>
                    Submit
                </button>
            </div>
        """
    else:
        submit_section_html = ""

    replacements = {
        "PLACEHOLDER_BACKGROUND_URL": background_url,
        "PLACEHOLDER_PIECE_SIZE": f"{piece_size}",
        "PLACEHOLDER_PIECE_TOP": f"{piece_top}",
        "PLACEHOLDER_HOLE_LEFT": f"{hole_left:.2f}",
        "PLACEHOLDER_PUZZLE_WIDTH": f"{puzzle_width}",
        "PLACEHOLDER_PUZZLE_HEIGHT": f"{puzzle_height}",
        "PLACEHOLDER_TARGET_POSITION": f"{target_position}",
        "PLACEHOLDER_TOLERANCE": f"{tolerance}",
        "PLACEHOLDER_TRACK_WIDTH": f"{track_width}",
        "PLACEHOLDER_SLIDER_SIZE": f"{slider_size}",
        "PLACEHOLDER_REQUIRES_SUBMIT": "true" if requires_submit else "false",
        "PLACEHOLDER_SUBMIT_SECTION": submit_section_html,
    }
    for placeholder, value in replacements.items():
        html_content = html_content.replace(placeholder, value)

    layout_metadata: Dict[str, Any] = {
        "type": "slider",
        "target_position": target_position,
        "tolerance": tolerance,
        "track_width": track_width,
        "track_height": track_height,
        "slider_size": slider_size,
        "puzzle_width": puzzle_width,
        "puzzle_height": puzzle_height,
        "piece_size": piece_size,
        "piece_top": piece_top,
        "hole_left": round(hole_left, 2),
        "background_image": background_filename,
        "puzzle_mask": puzzle_mask_base64,
        "css_variables": css_variables,
        "requires_submit": requires_submit,
        "dataset_scope": dataset_scope,
    }

    return html_content, layout_metadata
