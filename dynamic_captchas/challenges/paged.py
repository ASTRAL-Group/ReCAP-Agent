from __future__ import annotations

import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .common import BG_VARIATIONS, COLOR_PALETTES
from .icon import ICON_DEFINITIONS
from .image_grid import CHALLENGE_CATEGORIES, get_category_image_count

PAGED_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "assets" / "template" / "paged.html"


def _adjust_color(hex_color: str, variance: float = 0.18) -> str:
    """Return a slightly lightened or darkened variant of the provided hex color."""
    hex_value = hex_color.lstrip("#")
    if len(hex_value) != 6:
        return f"#{hex_value}"

    try:
        r = int(hex_value[0:2], 16)
        g = int(hex_value[2:4], 16)
        b = int(hex_value[4:6], 16)
    except ValueError:
        return f"#{hex_value}"

    factor = 1 + random.uniform(-variance, variance)
    clamp = lambda x: max(0, min(255, int(x)))  # noqa: E731
    r = clamp(r * factor)
    g = clamp(g * factor)
    b = clamp(b * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def _foreground_for(bg_color: str) -> str:
    """Pick a readable foreground color for the provided background."""
    hex_value = bg_color.lstrip("#")
    if len(hex_value) != 6:
        return "#0f172a"

    try:
        r = int(hex_value[0:2], 16)
        g = int(hex_value[2:4], 16)
        b = int(hex_value[4:6], 16)
    except ValueError:
        return "#0f172a"

    brightness = (r * 299 + g * 587 + b * 114) / 1000
    return "#0f172a" if brightness > 160 else "#ffffff"


def _generate_icon_colors(count: int, palette: Dict[str, str], backgrounds: List[str]) -> List[str]:
    """Generate a list of icon colors with gentle variation while keeping contrast."""

    def contrast_ok(fg: str, bg: str) -> bool:
        fg_hex = fg.lstrip("#")
        bg_hex = bg.lstrip("#")
        try:
            fr, fg_val, fb = int(fg_hex[0:2], 16), int(fg_hex[2:4], 16), int(fg_hex[4:6], 16)
            br, bgv, bb = int(bg_hex[0:2], 16), int(bg_hex[2:4], 16), int(bg_hex[4:6], 16)
        except ValueError:
            return True
        # simple brightness difference check
        fbri = (fr * 299 + fg_val * 587 + fb * 114) / 1000
        bbri = (br * 299 + bgv * 587 + bb * 114) / 1000
        return abs(fbri - bbri) > 60

    base_pool = [
        palette.get("primary", "#667eea"),
        palette.get("secondary", "#764ba2"),
        palette.get("accent", "#f093fb"),
        palette.get("neutral", "#4a5568"),
    ]

    colors: List[str] = []
    for idx in range(count):
        bg_color = backgrounds[idx % len(backgrounds)] if backgrounds else "#ffffff"
        candidate = _adjust_color(random.choice(base_pool), variance=0.25)
        if not contrast_ok(candidate, bg_color):
            candidate = _foreground_for(bg_color)
        colors.append(candidate)
    return colors


def _generate_card_backgrounds(count: int, palette: Dict[str, str]) -> List[str]:
    """Create a set of varied card background colors derived from the palette."""
    base_colors = [
        palette.get("primary", "#667eea"),
        palette.get("secondary", "#764ba2"),
        palette.get("accent", "#f093fb"),
        palette.get("neutral", "#e2e8f0"),
        random.choice(BG_VARIATIONS),
    ]

    backgrounds: List[str] = []
    for _ in range(count):
        base = random.choice(base_colors)
        backgrounds.append(_adjust_color(base))
    return backgrounds


def _slugify(label: str) -> str:
    """Create a lowercase, data-safe key from a human-readable label."""
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in label)
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned or label.lower()


def _build_icon_mode_cards(card_count: int, palette: Dict[str, str]) -> Dict[str, Any]:
    """Construct card data for the classic icon mode."""
    available_icons = list(ICON_DEFINITIONS.keys())
    target_icon = random.choice(available_icons)

    distractor_pool = [icon for icon in available_icons if icon != target_icon]
    distractors = random.sample(distractor_pool, k=card_count - 1)

    card_icons = [target_icon] + distractors
    random.shuffle(card_icons)

    card_backgrounds = _generate_card_backgrounds(len(card_icons), palette)
    icon_colors = _generate_icon_colors(len(card_icons), palette, card_backgrounds)

    cards: List[Dict[str, Any]] = []
    for idx, icon_key in enumerate(card_icons):
        icon_data = ICON_DEFINITIONS[icon_key]
        cards.append(
            {
                "key": icon_key,
                "label": icon_data["name"],
                "icon_class": icon_data["icon"],
                "background": card_backgrounds[idx],
                "color": icon_colors[idx],
                "type": "icon",
            }
        )

    return {
        "mode": "icon",
        "data_source": "icons",
        "target_key": target_icon,
        "target_label": ICON_DEFINITIONS[target_icon]["name"],
        "card_icons": card_icons,
        "card_backgrounds": card_backgrounds,
        "card_images": [],
        "cards": cards,
    }


def _build_category_mode_cards(
    card_count: int, palette: Dict[str, str], dataset_scope: str = "dynamic"
) -> Dict[str, Any]:
    """Construct card data for the image-grid-inspired category image mode."""
    instruction = random.choice(list(CHALLENGE_CATEGORIES.keys()))
    target_category = CHALLENGE_CATEGORIES[instruction]
    target_key = _slugify(target_category)

    other_categories = [cat for cat in CHALLENGE_CATEGORIES.values() if cat != target_category]
    sample_size = min(card_count - 1, len(other_categories))
    distractors = random.sample(other_categories, k=sample_size)

    card_categories = [target_category] + distractors
    random.shuffle(card_categories)

    card_backgrounds = _generate_card_backgrounds(len(card_categories), palette)
    icon_colors = _generate_icon_colors(len(card_categories), palette, card_backgrounds)

    cards: List[Dict[str, Any]] = []
    card_icons: List[str] = []
    card_images: List[Dict[str, str]] = []

    for idx, category in enumerate(card_categories):
        image_count = max(1, get_category_image_count(category, dataset_scope=dataset_scope))
        image_index = random.randint(0, image_count - 1)
        image_url = f"/image-grid-image/{category}/{image_index}?scope={dataset_scope}"
        key = _slugify(category)
        card_icons.append(key)
        card_images.append({"key": key, "category": category, "url": image_url})
        cards.append(
            {
                "key": key,
                "label": category,
                "background": card_backgrounds[idx],
                "color": icon_colors[idx],
                "image_url": image_url,
                "type": "category_image",
            }
        )

    return {
        "mode": "category_image",
        "data_source": "image_grid",
        "target_key": target_key,
        "target_label": target_category,
        "target_category": target_category,
        "instruction": instruction,
        "card_icons": card_icons,
        "card_backgrounds": card_backgrounds,
        "card_images": card_images,
        "cards": cards,
    }


def _render_card_content(card: Dict[str, Any]) -> str:
    """Return HTML content for a single card based on its type."""
    if card.get("type") == "category_image" and card.get("image_url"):
        alt_text = card.get("label", "Category image")
        return f"""
            <div class="card-visual card-visual-image" aria-hidden="true">
                <img src="{card['image_url']}" alt="{alt_text}" loading="lazy" />
            </div>
        """

    icon_class = card.get("icon_class")
    if icon_class:
        return f"""
            <div class="card-visual card-visual-icon" aria-hidden="true">
                <i class="{icon_class}"></i>
            </div>
        """

    return """
        <div class="card-visual card-visual-icon" aria-hidden="true">
            <span>?</span>
        </div>
    """


def generate_paged_captcha_layout(dataset_scope: str = "dynamic") -> Tuple[str, Dict[str, Any]]:
    """Generate the paged CAPTCHA layout and metadata."""
    try:
        with PAGED_TEMPLATE_PATH.open("r", encoding="utf-8") as file:
            html_content = file.read()
    except FileNotFoundError:
        return "Error: Paged template not found", {}

    palette = random.choice(COLOR_PALETTES)
    card_count = random.randint(4, 8)

    # Randomly choose between the classic icon mode and the image_grid image mode
    builder = random.choice([_build_icon_mode_cards, _build_category_mode_cards])
    if builder is _build_category_mode_cards:
        card_payload = builder(card_count, palette, dataset_scope=dataset_scope)
    else:
        card_payload = builder(card_count, palette)
    cards = card_payload.get("cards", [])

    card_height_range = (160, 200) if card_payload.get("mode") == "category_image" else (140, 175)
    css_variables = f"""
        --primary-color: {palette['primary']};
        --secondary-color: {palette['secondary']};
        --accent-color: {palette['accent']};
        --container-bg: {random.choice(BG_VARIATIONS)};
        --challenge-bg: {random.choice(BG_VARIATIONS)};
        --gradient-bg: linear-gradient(135deg, {palette['primary']} 0%, {palette['secondary']} 100%);
        --button-gradient: linear-gradient(135deg, {palette['primary']} 0%, {palette['accent']} 100%);
        --card-width: {random.randint(220, 250)}px;
        --card-height: {random.randint(*card_height_range)}px;
        --card-radius: {random.randint(14, 18)}px;
        --nav-size: 46px;
        --dot-size: 10px;
        --dot-active-size: 26px;
        --title-size: 27px;
        --container-max-width: 450px;
    """

    card_html_parts = []
    dot_html_parts = []
    for idx, card in enumerate(cards):
        background = card.get("background")
        icon_color = card.get("color")
        active_class = "active" if idx == 0 else ""
        label = card.get("label", f"Card {idx + 1}")
        card_html_parts.append(
            f"""
            <div class="icon-card {active_class}" data-index="{idx}" data-icon="{card.get('key')}" data-card-key="{card.get('key')}" data-card-type="{card.get('type', 'icon')}" aria-label="Card {idx + 1}: {label}" style="background:{background}; color:{icon_color};">
                <div class="icon-card-inner">
                    {_render_card_content(card)}
                </div>
            </div>
            """
        )
        dot_class = "card-dot active" if idx == 0 else "card-dot"
        dot_html_parts.append(
            f'<button class="{dot_class}" data-index="{idx}" aria-label="Go to card {idx + 1}"></button>'
        )

    # Paged challenges always use an explicit submit button
    requires_submit = True

    target_label = card_payload.get("target_label", "target")
    mode = card_payload.get("mode", "icon")
    instruction_key = card_payload.get("instruction", target_label)
    if mode == "category_image":
        title_text = "Paged Image Challenge"
        subtitle_text = "Slide through and pick the image from the right category"
    else:
        title_text = "Paged Icon Challenge"
        subtitle_text = "Browse the cards and submit the correct icon"
    instruction_text = (
        f"Select the card belonging to the <strong class=\"target-icon-name\">{instruction_key}</strong> category."
        if mode == "category_image"
        else f"Please select the card with the <strong class=\"target-icon-name\">{target_label}</strong> icon by sliding through the cards and submitting your choice."
    )

    html_content = html_content.replace("[TARGET_ICON]", target_label)
    html_content = html_content.replace("[CAPTCHA_MODE]", mode)
    html_content = html_content.replace("[CHALLENGE_TITLE]", title_text)
    html_content = html_content.replace("[CHALLENGE_SUBTITLE]", subtitle_text)
    html_content = html_content.replace("[INSTRUCTION_TEXT]", instruction_text)
    html_content = html_content.replace("[CARD_ITEMS]", "\n".join(card_html_parts))
    html_content = html_content.replace("[DOT_ITEMS]", "\n".join(dot_html_parts))
    html_content = html_content.replace("[CHALLENGE_ID]", "PLACEHOLDER_CHALLENGE_ID")
    html_content = html_content.replace("[REQUIRES_SUBMIT]", "true")

    css_injection = f"""
    <style>
        :root {{
            {css_variables}
        }}
    </style>
    """
    html_content = html_content.replace("</head>", f"{css_injection}</head>")

    layout_metadata = {
        "type": "paged",
        "mode": card_payload.get("mode", "icon"),
        "data_source": card_payload.get("data_source"),
        "target_icon": card_payload.get("target_key"),
        "target_icon_name": target_label,
        "target_category": card_payload.get("target_category"),
        "instruction": instruction_key,
        "instruction_text": instruction_text,
        "card_icons": card_payload.get("card_icons", []),
        "card_backgrounds": card_payload.get("card_backgrounds", []),
        "card_images": card_payload.get("card_images", []),
        "challenge_title": title_text,
        "challenge_subtitle": subtitle_text,
        "total_cards": len(cards),
        "requires_submit": True,
        "dataset_scope": dataset_scope,
    }

    return html_content, layout_metadata
