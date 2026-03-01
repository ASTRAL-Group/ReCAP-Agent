import glob
import random
from pathlib import Path
from typing import Any, Dict, Tuple

from .common import COLOR_PALETTES, count_for_scope

PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMAGE_GRID_DATASET_DIR = PROJECT_ROOT / "data" / "recaptchav2" / "images"
IMAGE_GRID_TEMPLATE_PATH = PROJECT_ROOT / "assets" / "template" / "image_grid.html"

# Mapping of user-facing instructions to dataset category folders
CHALLENGE_CATEGORIES = {
    "traffic lights": "Traffic Light",
    "crosswalks": "Crosswalk",
    "bicycles": "Bicycle",
    "fire hydrants": "Hydrant",
    "cars": "Car",
    "buses": "Bus",
    "motorcycles": "Motorcycle",
    "bridges": "Bridge",
    "palm trees": "Palm",
    "stairs": "Stair",
    "chimneys": "Chimney",
}


def get_category_image_count(category: str, dataset_scope: str = "dynamic") -> int:
    """Get the number of available images for a given category."""
    base_path = IMAGE_GRID_DATASET_DIR / category

    if not base_path.exists():
        return 100  # Default fallback if directory doesn't exist

    image_files = glob.glob(str(base_path / "*.png"))
    if not image_files:
        return 100
    return count_for_scope(len(image_files), dataset_scope)


def generate_image_grid_captcha_css_variables() -> str:
    """Generate CSS variables for image grid CAPTCHA."""
    palette = random.choice(COLOR_PALETTES)
    selected_gradient = f"linear-gradient(135deg, {palette['primary']} 0%, {palette['secondary']} 100%)"

    container_max_width = random.randint(400, 500)
    container_padding = random.randint(20, 40)
    container_radius = random.randint(12, 20)

    css_vars = f"""
        --primary-color: {palette['primary']};
        --secondary-color: {palette['secondary']};
        --accent-color: {palette['accent']};
        --gradient-bg: {selected_gradient};
        --container-bg: {random.choice(['#ffffff', '#f8f9fa', '#f1f3f4'])};
        --container-max-width: {container_max_width}px;
        --container-padding: {container_padding}px;
        --container-radius: {container_radius}px;
        --top-bar-height: {random.randint(3, 6)}px;
        --top-bar-gradient: {selected_gradient};
        --container-shadow: 0 {random.randint(15, 25)}px {random.randint(30, 50)}px rgba(0, 0, 0, {random.uniform(0.1, 0.2)});
    """

    return css_vars


def generate_image_grid_captcha_layout(dataset_scope: str = "dynamic") -> Tuple[str, Dict[str, Any]]:
    """Generate image grid CAPTCHA layout."""
    with IMAGE_GRID_TEMPLATE_PATH.open("r", encoding="utf-8") as file:
        template = file.read()

    css_variables = generate_image_grid_captcha_css_variables()

    instruction = random.choice(list(CHALLENGE_CATEGORIES.keys()))
    target_category = CHALLENGE_CATEGORIES[instruction]

    num_correct = random.randint(0, 5)
    correct_tiles = random.sample(range(9), num_correct)

    # Get image counts for all categories
    target_image_count = get_category_image_count(target_category, dataset_scope=dataset_scope)
    other_categories = [cat for cat in CHALLENGE_CATEGORIES.values() if cat != target_category]
    other_image_counts = {
        cat: get_category_image_count(cat, dataset_scope=dataset_scope) for cat in other_categories
    }

    images = []
    for i in range(9):
        if i in correct_tiles:
            # Random index from target category's available images
            random_index = random.randint(0, target_image_count - 1)
            images.append(f"/image-grid-image/{target_category}/{random_index}?scope={dataset_scope}")
        else:
            # Random category and random index from that category's available images
            random_category = random.choice(other_categories)
            random_index = random.randint(0, other_image_counts[random_category] - 1)
            images.append(f"/image-grid-image/{random_category}/{random_index}?scope={dataset_scope}")

    html_content = template.replace("[INSTRUCTION]", instruction)
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
        "type": "image_grid",
        "instruction": instruction,
        "target_category": target_category,
        "correct_tiles": correct_tiles,
        "images": images,
        "css_variables": css_variables,
        "dataset_scope": dataset_scope,
    }

    return html_content, layout_metadata
