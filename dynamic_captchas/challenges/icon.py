import logging
import random
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .common import (
    COLOR_PALETTES,
    calculate_random_positions,
    generate_random_icon_style,
    get_random_background_image_for_scope,
)

logger = logging.getLogger(__name__)
ICON_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "assets" / "template" / "icon.html"

ICON_DEFINITIONS: Dict[str, Dict[str, str]] = {
    "star": {"name": "Star", "icon": "fas fa-star"},
    "heart": {"name": "Heart", "icon": "fas fa-heart"},
    "home": {"name": "Home", "icon": "fas fa-home"},
    "car": {"name": "Car", "icon": "fas fa-car"},
    "plane": {"name": "Plane", "icon": "fas fa-plane"},
    "tree": {"name": "Tree", "icon": "fas fa-tree"},
    "sun": {"name": "Sun", "icon": "fas fa-sun"},
    "moon": {"name": "Moon", "icon": "fas fa-moon"},
    "cat": {"name": "Cat", "icon": "fas fa-cat"},
    "dog": {"name": "Dog", "icon": "fas fa-dog"},
    "fish": {"name": "Fish", "icon": "fas fa-fish"},
    "bird": {"name": "Bird", "icon": "fas fa-dove"},
    "apple": {"name": "Apple", "icon": "fas fa-apple-alt"},
    "coffee": {"name": "Coffee", "icon": "fas fa-coffee"},
    "book": {"name": "Book", "icon": "fas fa-book"},
    "music": {"name": "Music", "icon": "fas fa-music"},
    "camera": {"name": "Camera", "icon": "fas fa-camera"},
    "phone": {"name": "Phone", "icon": "fas fa-phone"},
    "envelope": {"name": "Envelope", "icon": "fas fa-envelope"},
    "key": {"name": "Key", "icon": "fas fa-key"},
    "truck": {"name": "Truck", "icon": "fas fa-truck"},
    "globe": {"name": "Globe", "icon": "fas fa-globe"},
    "cloud": {"name": "Cloud", "icon": "fas fa-cloud"},
    "bolt": {"name": "Lightning", "icon": "fas fa-bolt"},
    "fire": {"name": "Fire", "icon": "fas fa-fire"},
    "gift": {"name": "Gift", "icon": "fas fa-gift"},
    "rocket": {"name": "Rocket", "icon": "fas fa-rocket"},
    "trophy": {"name": "Trophy", "icon": "fas fa-trophy"},
    "shield": {"name": "Shield", "icon": "fas fa-shield-alt"},
    "bell": {"name": "Bell", "icon": "fas fa-bell"},
    "anchor": {"name": "Anchor", "icon": "fas fa-anchor"},
    "leaf": {"name": "Leaf", "icon": "fas fa-leaf"},
    "paw": {"name": "Paw", "icon": "fas fa-paw"},
    "basketball": {"name": "Basketball", "icon": "fas fa-basketball-ball"},
    "paint": {"name": "Paint Brush", "icon": "fas fa-paint-brush"},
    "medkit": {"name": "First Aid", "icon": "fas fa-medkit"},
}


def generate_icon_captcha_css_variables(dataset_scope: str = "dynamic") -> str:
    """Generate CSS variables for icon CAPTCHA."""
    palette = random.choice(COLOR_PALETTES)
    selected_gradient = f"linear-gradient(135deg, {palette['primary']} 0%, {palette['secondary']} 100%)"

    background_image = get_random_background_image_for_scope(dataset_scope) or "none"

    base_icon_size = random.randint(45, 56)
    base_canvas_width = random.randint(285, 338)
    base_canvas_height = random.randint(240, 300)

    adjustment = random.randint(-22, 22)
    canvas_width = max(base_canvas_width + adjustment, 240)
    canvas_height = max(base_canvas_height + adjustment, 210)

    container_width = max(int(canvas_width * 1.2), canvas_width + 20)

    css_vars = f"""
        --primary-color: {palette['primary']};
        --secondary-color: {palette['secondary']};
        --accent-color: {palette['accent']};
        --gradient-bg: {selected_gradient};
        --container-bg: {random.choice(['#ffffff', '#f8f9fa', '#f1f3f4'])};
        --challenge-bg: {random.choice(['#f8f9fa', '#e9ecef', '#f1f3f4'])};

        --icon-max-width: {container_width}px;
        --icon-canvas-width: {canvas_width}px;
        --icon-canvas-height: {canvas_height}px;
        --icon-size: {base_icon_size}px;
        --icon-font-size: {random.randint(15, 21)}px;
        --icon-selected-bg: {palette['primary']};
        --target-icon-color: {palette['primary']};
        --instruction-bg: {random.choice(['#f7fafc', '#f8f9fa', '#f1f3f4', '#e8f4f8', '#fff5f5'])};
        --background-image: url('{background_image}');
    """

    return css_vars


def generate_icon_captcha_layout(
    requires_submit: Optional[bool] = None, dataset_scope: str = "dynamic"
) -> Tuple[str, Dict[str, Any]]:
    """Generate icon selection CAPTCHA layout with random positioning."""
    with ICON_TEMPLATE_PATH.open("r", encoding="utf-8") as file:
        template = file.read()

    available_icons = list(ICON_DEFINITIONS.keys())
    target_icon = random.choice(available_icons)
    distractors = random.sample([icon for icon in available_icons if icon != target_icon], 5)

    css_variables = generate_icon_captcha_css_variables(dataset_scope=dataset_scope)

    canvas_width_match = re.search(r"--icon-canvas-width:\s*(\d+)px", css_variables)
    canvas_height_match = re.search(r"--icon-canvas-height:\s*(\d+)px", css_variables)
    icon_size_match = re.search(r"--icon-size:\s*(\d+)px", css_variables)

    canvas_width = int(canvas_width_match.group(1)) if canvas_width_match else 300
    canvas_height = int(canvas_height_match.group(1)) if canvas_height_match else 260
    icon_size = int(icon_size_match.group(1)) if icon_size_match else 50

    all_icons = [target_icon] + distractors
    random.shuffle(all_icons)

    try:
        positions = calculate_random_positions(canvas_width, canvas_height, icon_size, len(all_icons), margin=25)
    except ValueError as exc:
        logger.warning("Random positioning failed (%s); using fallback grid layout.", exc)
        positions = []
        cols = 3
        margin = 25
        for i, icon_key in enumerate(all_icons):
            row = i // cols
            col = i % cols
            x = col * (icon_size + 20) + margin
            y = row * (icon_size + 20) + margin
            positions.append((x, y))

    icon_canvas_html = ""
    icon_styles = []

    for i, icon_key in enumerate(all_icons):
        icon_data = ICON_DEFINITIONS[icon_key]
        x, y = positions[i]
        icon_style = generate_random_icon_style()
        icon_styles.append(icon_style)

        inline_style = (
            f"left: {x}px; top: {y}px; color: {icon_style['color']}; "
            f"transform: rotate({icon_style['rotation']});"
        )

        icon_canvas_html += f"""
            <div class="icon-option" data-icon="{icon_key}" data-x="{x}" data-y="{y}" data-size="{icon_size}" style="{inline_style}">
                <i class="{icon_data['icon']}"></i>
            </div>
        """

    # Use provided value or default to random choice
    if requires_submit is None:
        requires_submit = random.choice([True, False])
    html_content = template.replace("[TARGET_ICON]", ICON_DEFINITIONS[target_icon]["name"])
    html_content = html_content.replace("[ICON_GRID]", icon_canvas_html)
    html_content = html_content.replace("[CHALLENGE_ID]", "PLACEHOLDER_CHALLENGE_ID")
    submit_section_html = """
            <div class="captcha-submit-section">
                <button type="button" id="submit-btn" class="captcha-submit-btn" disabled>
                    Submit
                </button>
            </div>
    """
    if not requires_submit:
        submit_section_html = ""
    html_content = html_content.replace("[SUBMIT_SECTION]", submit_section_html)
    html_content = html_content.replace("[REQUIRES_SUBMIT]", "true" if requires_submit else "false")

    css_injection = f"""
    <style>
        :root {{
            {css_variables}
        }}
        .icon-option {{
            pointer-events: auto !important;
            cursor: pointer !important;
        }}
        .icon-grid {{
            position: relative !important;
            width: {canvas_width}px !important;
            height: {canvas_height}px !important;
            background-image: var(--background-image) !important;
            background-size: cover !important;
            background-position: center !important;
            background-repeat: no-repeat !important;
            border-radius: 8px !important;
            margin: 0 auto 30px auto !important;
        }}
        .captcha-submit-section {{
            margin-top: 20px !important;
            z-index: 0 !important;
        }}
    </style>
    """

    html_content = html_content.replace("</head>", f"{css_injection}</head>")

    layout_metadata = {
        "type": "icon_selection",
        "target_icon": target_icon,
        "target_icon_name": ICON_DEFINITIONS[target_icon]["name"],
        "all_icons": all_icons,
        "positions": positions,
        "icon_styles": icon_styles,
        "canvas_dimensions": (canvas_width, canvas_height),
        "icon_size": icon_size,
        "css_variables": css_variables,
        "requires_submit": requires_submit,
        "dataset_scope": dataset_scope,
    }

    return html_content, layout_metadata
