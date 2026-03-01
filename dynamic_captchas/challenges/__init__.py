"""Challenge generation module."""

from .dataset import load_text_captcha_dataset, get_random_text_captcha_entry
from .icon import generate_icon_captcha_layout
from .paged import generate_paged_captcha_layout
from .icon_match import generate_icon_match_captcha_layout
from .image_grid import generate_image_grid_captcha_layout
from .slider import generate_slider_captcha_layout
from .text import (
    generate_text_captcha_layout,
    generate_compact_text_captcha_layout,
)
from .common import validate_click_position

__all__ = [
    "load_text_captcha_dataset",
    "get_random_text_captcha_entry",
    "generate_text_captcha_layout",
    "generate_compact_text_captcha_layout",
    "generate_icon_captcha_layout",
    "generate_paged_captcha_layout",
    "generate_icon_match_captcha_layout",
    "generate_slider_captcha_layout",
    "generate_image_grid_captcha_layout",
    "validate_click_position",
]
