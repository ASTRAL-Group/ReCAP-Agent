import glob
import logging
import os
import random
from pathlib import Path
from typing import Dict, List, Tuple, TypeVar

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[1]

ICON_COLORS = [
    "#e53e3e",  # Red
    "#3182ce",  # Blue
    "#38a169",  # Green
    "#805ad5",  # Purple
    "#d69e2e",  # Yellow
    "#dd6b20",  # Orange
    "#e53e3e",  # Red variant
    "#2b6cb0",  # Blue variant
    "#2f855a",  # Green variant
    "#553c9a",  # Purple variant
    "#b7791f",  # Yellow variant
    "#c05621",  # Orange variant
    "#c53030",  # Dark red
    "#2c5282",  # Dark blue
    "#276749",  # Dark green
    "#553c9a",  # Dark purple
    "#975a16",  # Dark yellow
    "#9c4221",  # Dark orange
]

COLOR_PALETTES = [
    {
        "primary": "#667eea",
        "secondary": "#764ba2",
        "accent": "#f093fb",
        "success": "#4ecdc4",
        "error": "#f5576c",
        "neutral": "#718096",
    },
    {
        "primary": "#ff6b6b",
        "secondary": "#4ecdc4",
        "accent": "#45b7d1",
        "success": "#96ceb4",
        "error": "#feca57",
        "neutral": "#a0aec0",
    },
    {
        "primary": "#a89dea",
        "secondary": "#fed6e3",
        "accent": "#d299c2",
        "success": "#fad0c4",
        "error": "#ffd1dc",
        "neutral": "#cbd5e0",
    },
    {
        "primary": "#ec72ff",
        "secondary": "#fcb69f",
        "accent": "#ff8a80",
        "success": "#a8e6cf",
        "error": "#ffd3a5",
        "neutral": "#d4a574",
    },
    {
        "primary": "#84fab0",
        "secondary": "#8fd3f4",
        "accent": "#a8edea",
        "success": "#d299c2",
        "error": "#fad0c4",
        "neutral": "#96ceb4",
    },
    {
        "primary": "#fa709a",
        "secondary": "#fee140",
        "accent": "#ff9a9e",
        "success": "#fecfef",
        "error": "#fecfef",
        "neutral": "#f6d365",
    },
    {
        "primary": "#a8c0ff",
        "secondary": "#3f2b96",
        "accent": "#667eea",
        "success": "#764ba2",
        "error": "#f093fb",
        "neutral": "#4ecdc4",
    },
    {
        "primary": "#ff9a8b",
        "secondary": "#a8e6cf",
        "accent": "#d299c2",
        "success": "#fad0c4",
        "error": "#ffd1dc",
        "neutral": "#ffecd2",
    },
]

BG_VARIATIONS = [
    "#ffffff",
    "#f8f9fa",
    "#f1f3f4",
    "#e8f4f8",
    "#fff5f5",
    "#f0fff4",
    "#fffbf0",
    "#faf5ff",
    "#f0f8ff",
    "#f5f5dc",
]

CHALLENGE_BG_VARIATIONS = [
    "#f8f9fa",
    "#e9ecef",
    "#f1f3f4",
    "#e8f4f8",
    "#fff5f5",
    "#f0fff4",
    "#fffbf0",
    "#faf5ff",
    "#f0f8ff",
    "#f5f5dc",
    "#ffe4e1",
    "#e6f3ff",
    "#f0f0f0",
    "#fffacd",
    "#f5fffa",
]

BACKGROUND_IMAGES: List[str] | None = None
STATIC_DATASET_RESERVE_RATIO = 0.10
T = TypeVar("T")


def _reserved_count(total: int, ratio: float = STATIC_DATASET_RESERVE_RATIO) -> int:
    """Calculate how many items should be reserved for static challenges."""
    if total <= 0:
        return 0
    if total == 1:
        return 1

    reserved = int(total * ratio)
    reserved = max(1, reserved)
    return min(total - 1, reserved)


def split_items_by_scope(items: List[T], scope: str) -> List[T]:
    """Return the list slice for static or dynamic scope."""
    if not items:
        return []

    reserved = _reserved_count(len(items))
    static_items = items[:reserved]
    dynamic_items = items[reserved:]

    if scope == "static":
        return static_items or items
    return dynamic_items or items


def count_for_scope(total: int, scope: str) -> int:
    """Return item count for static/dynamic subset."""
    if total <= 0:
        return 0
    reserved = _reserved_count(total)
    if scope == "static":
        return reserved if reserved > 0 else total
    dynamic_count = total - reserved
    return dynamic_count if dynamic_count > 0 else total


def discover_background_images() -> List[str]:
    """Discover all available background images in the data/backgrounds directory."""
    background_dir = PROJECT_ROOT / "data" / "backgrounds"
    if not background_dir.exists():
        logger.warning("Background directory not found: %s", background_dir)
        return []

    image_patterns = [
        str(background_dir / "*.jpg"),
        str(background_dir / "*.jpeg"),
        str(background_dir / "*.png"),
    ]

    image_files: List[str] = []
    for pattern in image_patterns:
        image_files.extend(glob.glob(pattern))

    background_urls = []
    for image_file in image_files:
        filename = os.path.basename(image_file)
        background_urls.append(f"/backgrounds/{filename}")

    if background_urls:
        logger.info("Discovered %d background images", len(background_urls))

    return background_urls


def get_random_background_image() -> str | None:
    """Select a random background image from the available options."""
    global BACKGROUND_IMAGES

    if BACKGROUND_IMAGES is None:
        BACKGROUND_IMAGES = sorted(discover_background_images())

    if not BACKGROUND_IMAGES:
        return None

    return random.choice(BACKGROUND_IMAGES)


def get_random_background_image_for_scope(scope: str = "dynamic") -> str | None:
    """Select a random background image from static/dynamic subset."""
    global BACKGROUND_IMAGES

    if BACKGROUND_IMAGES is None:
        BACKGROUND_IMAGES = sorted(discover_background_images())

    if not BACKGROUND_IMAGES:
        return None

    scoped_images = split_items_by_scope(BACKGROUND_IMAGES, scope)
    if not scoped_images:
        return None
    return random.choice(scoped_images)


def calculate_random_positions(
    canvas_width: int,
    canvas_height: int,
    icon_size: int,
    num_icons: int,
    min_spacing: int = 15,
    margin: int = 20,
) -> List[Tuple[int, int]]:
    """Calculate random positions for icons without overlap and away from edges."""
    positions: List[Tuple[int, int]] = []
    max_attempts = num_icons * 50
    attempts = 0

    min_x = margin
    min_y = margin
    max_x = canvas_width - icon_size - margin
    max_y = canvas_height - icon_size - margin

    if max_x <= min_x or max_y <= min_y:
        raise ValueError(
            "Canvas too small for icons with margins. "
            f"Canvas: {canvas_width}x{canvas_height}, Icon: {icon_size}, Margin: {margin}"
        )

    while len(positions) < num_icons and attempts < max_attempts:
        x = random.randint(min_x, max_x)
        y = random.randint(min_y, max_y)

        overlap = False
        for existing_x, existing_y in positions:
            if (
                abs(x - existing_x) < icon_size + min_spacing
                and abs(y - existing_y) < icon_size + min_spacing
            ):
                overlap = True
                break

        if not overlap:
            positions.append((x, y))

        attempts += 1

    if len(positions) < num_icons:
        raise ValueError(
            f"Couldn't place all {num_icons} icons without overlap. "
            "Consider increasing canvas size or reducing icon size."
        )

    return positions


def generate_random_icon_style() -> Dict[str, str]:
    """Generate random styling for an icon (color and rotation)."""
    color = random.choice(ICON_COLORS)
    rotation = random.randint(-30, 30)

    return {"color": color, "rotation": f"{rotation}deg"}


def validate_click_position(
    click_x: float,
    click_y: float,
    icon_x: int,
    icon_y: int,
    icon_size: int,
    tolerance: int = 20,
) -> bool:
    """Validate if a click position is within the icon area with error tolerance."""
    icon_center_x = icon_x + icon_size / 2
    icon_center_y = icon_y + icon_size / 2
    distance = ((click_x - icon_center_x) ** 2 + (click_y - icon_center_y) ** 2) ** 0.5
    return distance <= tolerance
