import logging
import random
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .common import calculate_random_positions, generate_random_icon_style
from .icon import ICON_DEFINITIONS, generate_icon_captcha_css_variables

logger = logging.getLogger(__name__)
ICON_MATCH_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "assets" / "template" / "icon_match.html"


def _load_template() -> str:
    with ICON_MATCH_TEMPLATE_PATH.open("r", encoding="utf-8") as file:
        return file.read()


def _parse_css_dimension(css_variables: str, var_name: str, fallback: int) -> int:
    pattern = rf"{var_name}:\s*(\d+)px"
    match = re.search(pattern, css_variables)
    return int(match.group(1)) if match else fallback


def generate_icon_match_captcha_layout() -> Tuple[str, Dict[str, Any]]:
    """Generate the drag-to-match icon CAPTCHA layout and metadata."""
    template = _load_template()

    css_variables = generate_icon_captcha_css_variables()

    canvas_width = _parse_css_dimension(css_variables, r"--icon-canvas-width", 420)
    canvas_height = _parse_css_dimension(css_variables, r"--icon-canvas-height", 360)
    icon_size = _parse_css_dimension(css_variables, r"--icon-size", 64)

    available_icons = list(ICON_DEFINITIONS.keys())
    match_icon_key = random.choice(available_icons)

    distractor_count = random.randint(4, 5)
    distractor_icons = random.sample([icon for icon in available_icons if icon != match_icon_key], distractor_count)

    # Build the list of icon entries (two matches + distractors)
    icon_entries: List[Dict[str, Any]] = []

    match_group_id = str(uuid.uuid4())
    match_piece_ids = [str(uuid.uuid4()), str(uuid.uuid4())]

    for idx in range(2):
        icon_entries.append(
            {
                "id": match_piece_ids[idx],
                "icon_key": match_icon_key,
                "is_match": True,
                "match_group_id": match_group_id,
            }
        )

    for icon_key in distractor_icons:
        icon_entries.append(
            {
                "id": str(uuid.uuid4()),
                "icon_key": icon_key,
                "is_match": False,
                "match_group_id": None,
            }
        )

    random.shuffle(icon_entries)

    try:
        positions = calculate_random_positions(
            canvas_width,
            canvas_height,
            icon_size,
            len(icon_entries),
            min_spacing=18,
            margin=30,
        )
    except ValueError as exc:  # fallback to simple grid
        logger.warning("Icon match positioning fallback triggered: %s", exc)
        positions = []
        cols = 3
        spacing = icon_size + 24
        for index in range(len(icon_entries)):
            row = index // cols
            col = index % cols
            x = 30 + col * spacing
            y = 30 + row * spacing
            positions.append((x, y))

    icon_canvas_html = ""
    placed_entries: List[Dict[str, Any]] = []

    for entry, (x, y) in zip(icon_entries, positions):
        icon_meta = ICON_DEFINITIONS[entry["icon_key"]]
        icon_style = generate_random_icon_style()

        entry_with_layout = {
            **entry,
            "x": x,
            "y": y,
            "size": icon_size,
            "rotation": icon_style["rotation"],
            "color": icon_style["color"],
        }
        placed_entries.append(entry_with_layout)

        inline_style = (
            f"left: {x}px; top: {y}px; color: {icon_style['color']}; "
            f"transform: rotate({icon_style['rotation']});"
        )

        extra_attrs = []
        if entry["is_match"]:
            extra_attrs.append(f'data-match-group="{match_group_id}"')

        icon_canvas_html += f"""
            <div class="icon-piece{' match-piece' if entry['is_match'] else ''}" 
                 data-icon-id="{entry['id']}" 
                 data-icon="{entry['icon_key']}" 
                 {' '.join(extra_attrs)} 
                 data-x="{x}" data-y="{y}" data-size="{icon_size}" 
                 style="{inline_style}">
                <i class="{icon_meta['icon']}"></i>
            </div>
        """

    requires_submit = False
    tolerance = random.randint(20, 30)

    html_content = template.replace("[TARGET_ICON]", ICON_DEFINITIONS[match_icon_key]["name"])
    html_content = html_content.replace("[ICON_GRID]", icon_canvas_html)
    html_content = html_content.replace("[CHALLENGE_ID]", "PLACEHOLDER_CHALLENGE_ID")

    html_content = html_content.replace("[REQUIRES_SUBMIT]", "false")

    css_injection = f"""
    <style>
        :root {{
            {css_variables}
        }}
        .icon-match-captcha .icon-grid {{
            position: relative !important;
            width: {canvas_width}px !important;
            height: {canvas_height}px !important;
        }}
    </style>
    """

    html_content = html_content.replace("</head>", f"{css_injection}</head>")

    layout_metadata = {
        "type": "icon_match",
        "pair_icon": match_icon_key,
        "pair_icon_name": ICON_DEFINITIONS[match_icon_key]["name"],
        "pieces": placed_entries,
        "match_pair_ids": match_piece_ids,
        "match_group_id": match_group_id,
        "canvas_dimensions": (canvas_width, canvas_height),
        "icon_size": icon_size,
        "tolerance": tolerance,
        "css_variables": css_variables,
        "requires_submit": requires_submit,
    }

    return html_content, layout_metadata
