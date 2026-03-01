import random
from pathlib import Path
from typing import Any, Dict, Tuple

from .common import COLOR_PALETTES, BG_VARIATIONS, CHALLENGE_BG_VARIATIONS

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "assets" / "template"


def generate_text_captcha_css_variables() -> str:
    """Generate dynamic CSS variables for standard text CAPTCHA styling."""
    palette = random.choice(COLOR_PALETTES)

    gradients = [
        f"linear-gradient(135deg, {palette['primary']} 0%, {palette['secondary']} 100%)",
        f"linear-gradient(45deg, {palette['primary']}, {palette['accent']})",
        f"linear-gradient(90deg, {palette['primary']}, {palette['secondary']}, {palette['accent']})",
        f"linear-gradient(180deg, {palette['primary']}, {palette['secondary']})",
        f"linear-gradient(225deg, {palette['accent']}, {palette['primary']})",
        f"radial-gradient(circle, {palette['primary']}, {palette['secondary']})",
        f"conic-gradient(from 0deg, {palette['primary']}, {palette['accent']}, {palette['secondary']})",
    ]

    selected_gradient = random.choice(gradients)
    selected_bg = random.choice(BG_VARIATIONS)
    selected_challenge_bg = random.choice(CHALLENGE_BG_VARIATIONS)

    container_padding = random.randint(25, 50)
    container_max_width = random.randint(450, 600)
    container_radius = random.randint(12, 24)

    title_size = random.randint(24, 32)
    title_weight = random.choice([600, 700, 800])

    input_padding_v = random.randint(12, 20)
    input_padding_h = random.randint(16, 24)
    input_font_size = random.randint(16, 20)
    input_radius = random.randint(8, 16)
    input_max_width = random.randint(250, 350)

    button_padding_v = random.randint(12, 20)
    button_padding_h = random.randint(30, 50)
    button_font_size = random.randint(16, 20)
    button_radius = random.randint(8, 16)
    button_min_width = random.randint(100, 140)
    button_max_width = random.randint(160, 220)

    challenge_padding = random.randint(20, 35)
    challenge_radius = random.randint(8, 16)
    challenge_min_height = random.randint(180, 250)

    image_width = random.randint(280, 350)
    image_height = random.randint(100, 140)

    css_vars = f"""
        --primary-color: {palette['primary']};
        --secondary-color: {palette['secondary']};
        --accent-color: {palette['accent']};
        --success-color: {palette['success']};
        --error-color: {palette['error']};
        --neutral-color: {palette['neutral']};
        --gradient-bg: {selected_gradient};
        --container-bg: {selected_bg};
        --challenge-bg: {selected_challenge_bg};
        --title-gradient: {selected_gradient};
        --top-bar-gradient: {selected_gradient};
        --border-radius: {random.randint(8, 20)}px;
        --shadow-intensity: {random.uniform(0.1, 0.4)};

        --container-padding: {container_padding}px;
        --container-max-width: {container_max_width}px;
        --container-radius: {container_radius}px;
        --top-bar-height: {random.randint(3, 6)}px;

        --title-size: {title_size}px;
        --title-weight: {title_weight};
        --title-color: {random.choice(['#2d3748', '#1a202c', '#4a5568'])};
        --title-margin-bottom: {random.randint(8, 15)}px;

        --input-padding: {input_padding_v}px {input_padding_h}px;
        --input-font-size: {input_font_size}px;
        --input-font-weight: {random.choice([400, 500, 600])};
        --input-radius: {input_radius}px;
        --input-max-width: {input_max_width}px;
        --input-letter-spacing: {random.randint(1, 3)}px;
        --input-border: {random.randint(1, 3)}px solid {palette['neutral']};
        --input-bg: {random.choice(['#ffffff', '#f8f9fa', '#f1f3f4'])};
        --input-color: {random.choice(['#2d3748', '#1a202c', '#4a5568'])};

        --button-padding: {button_padding_v}px {button_padding_h}px;
        --button-font-size: {button_font_size}px;
        --button-font-weight: {random.choice([500, 600, 700])};
        --button-radius: {button_radius}px;
        --button-min-width: {button_min_width}px;
        --button-max-width: {button_max_width}px;
        --button-gradient: {selected_gradient};
        --button-color: {random.choice(['white', '#ffffff', '#f8f9fa'])};
        --button-shadow: 0 {random.randint(3, 6)}px {random.randint(10, 20)}px {palette['primary']}{random.randint(20, 40)}%;

        --challenge-padding: {challenge_padding}px;
        --challenge-radius: {challenge_radius}px;
        --challenge-min-height: {challenge_min_height}px;
        --challenge-margin-bottom: {random.randint(20, 35)}px;
        --challenge-border: {random.randint(1, 3)}px solid {palette['neutral']};
        --instruction-bg: {random.choice(['#f7fafc', '#f8f9fa', '#f1f3f4', '#e8f4f8', '#fff5f5'])};
        --image-width: {image_width}px;
        --image-height: {image_height}px;
    """

    return css_vars


def generate_compact_text_captcha_css_variables() -> str:
    """Generate CSS variables for compact CAPTCHA layout."""
    palette = random.choice(COLOR_PALETTES)
    selected_gradient = f"linear-gradient(135deg, {palette['primary']} 0%, {palette['secondary']} 100%)"

    compact_max_width = random.randint(300, 400)
    compact_padding = random.randint(15, 25)
    compact_title_size = random.randint(18, 24)
    compact_image_width = random.randint(180, 250)
    compact_image_height = random.randint(70, 100)
    compact_input_width = random.randint(150, 220)

    css_vars = f"""
        --primary-color: {palette['primary']};
        --secondary-color: {palette['secondary']};
        --accent-color: {palette['accent']};
        --gradient-bg: {selected_gradient};
        --container-bg: {random.choice(['#ffffff', '#f8f9fa', '#f1f3f4'])};
        --challenge-bg: {random.choice(['#f8f9fa', '#e9ecef', '#f1f3f4'])};

        --compact-max-width: {compact_max_width}px;
        --compact-padding: {compact_padding}px;
        --compact-title-size: {compact_title_size}px;
        --compact-image-width: {compact_image_width}px;
        --compact-image-height: {compact_image_height}px;
        --compact-input-width: {compact_input_width}px;
        --compact-input-padding: {random.randint(6, 10)}px {random.randint(10, 16)}px;
        --compact-submit-padding: {random.randint(6, 10)}px {random.randint(15, 25)}px;
        --instruction-bg: {random.choice(['#f7fafc', '#f8f9fa', '#f1f3f4', '#e8f4f8', '#fff5f5'])};
    """

    return css_vars


def generate_text_captcha_layout(image_index: int) -> Tuple[str, Dict[str, Any]]:
    """Generate dynamic HTML/CSS layout for standard text CAPTCHA."""
    with (TEMPLATE_DIR / "text.html").open("r", encoding="utf-8") as file:
        template = file.read()

    css_variables = generate_text_captcha_css_variables()

    html_content = template.replace("[CAPTCHA_INDEX]", str(image_index))
    html_content = html_content.replace("[CHALLENGE_ID]", "PLACEHOLDER_CHALLENGE_ID")

    css_injection = f"""
    <style>
        :root {{
            {css_variables}
        }}
    </style>
    """

    html_content = html_content.replace("</head>", f"{css_injection}</head>")

    layout_metadata = {
        "type": "text",
        "css_variables": css_variables,
        "image_index": image_index,
    }

    return html_content, layout_metadata


def generate_compact_text_captcha_layout(image_index: int) -> Tuple[str, Dict[str, Any]]:
    """Generate compact text CAPTCHA layout."""
    with (TEMPLATE_DIR / "compact_text.html").open("r", encoding="utf-8") as file:
        template = file.read()

    css_variables = generate_compact_text_captcha_css_variables()

    html_content = template.replace("[CAPTCHA_INDEX]", str(image_index))
    html_content = html_content.replace("[CHALLENGE_ID]", "PLACEHOLDER_CHALLENGE_ID")

    css_injection = f"""
    <style>
        :root {{
            {css_variables}
        }}
    </style>
    """

    html_content = html_content.replace("</head>", f"{css_injection}</head>")

    layout_metadata = {
        "type": "compact_text",
        "css_variables": css_variables,
        "image_index": image_index,
    }

    return html_content, layout_metadata
