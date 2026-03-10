import math
import os
import re
from typing import List, Dict, Tuple, Optional

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import Page


def ensure_directories(run_id: str) -> str:
    """Create output directories for the current run."""
    run_dir = os.path.join("runs", run_id)
    img_dir = os.path.join(run_dir, "img")
    os.makedirs(img_dir, exist_ok=True)
    return img_dir


def format_point(x: float, y: float) -> str:
    """Format a point using the required <point>x y</point> syntax."""
    return f"<point>{x:.1f} {y:.1f}</point>"


def parse_point(point_str: str) -> Tuple[float, float]:
    """Extract x, y from <point>x y</point> string."""
    match = re.search(r"<point>([\d.]+) ([\d.]+)</point>", point_str)
    if match:
        return float(match.group(1)), float(match.group(2))
    return 0.0, 0.0

def annotate_image(image_path: str, actions: List[Dict], output_path: str) -> None:
    """
    Annotate image with actions.
    - Click: Red dot with number.
    - Drag: Blue arrow with number.
    - Type: Green text with number near last click.
    """
    try:
        with Image.open(image_path) as img:
            draw = ImageDraw.Draw(img)
            
            # Try to load a larger font, fallback to default if not found
            try:
                # Try common system fonts
                font = ImageFont.truetype("DejaVuSans-Bold.ttf", 24)
            except OSError:
                try:
                    font = ImageFont.truetype("arial.ttf", 24)
                except OSError:
                    # Fallback to default but it might be small
                    font = ImageFont.load_default()

            last_click_point = None
            
            for i, action in enumerate(actions):
                step_num = i + 1
                act_type = action.get("action")
                
                if act_type == "click":
                    point = parse_point(action.get("point", ""))
                    last_click_point = point
                    
                    # Draw red dot with number
                    x, y = point
                    radius = 15
                    draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill="red", outline="white", width=2)
                    
                    # Draw number centered
                    text = str(step_num)
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    draw.text((x - text_width / 2, y - text_height / 2 - 2), text, fill="white", font=font)
                    
                elif act_type == "drag":
                    start = parse_point(action.get("start_point", ""))
                    end = parse_point(action.get("end_point", ""))
                    last_click_point = None # Reset last click after drag
                    
                    # Draw blue arrow
                    draw.line([start, end], fill="blue", width=4)
                    
                    # Draw arrowhead
                    angle = math.atan2(end[1] - start[1], end[0] - start[0])
                    arrow_len = 20
                    arrow_angle = math.pi / 6  # 30 degrees
                    
                    x1 = end[0] - arrow_len * math.cos(angle - arrow_angle)
                    y1 = end[1] - arrow_len * math.sin(angle - arrow_angle)
                    x2 = end[0] - arrow_len * math.cos(angle + arrow_angle)
                    y2 = end[1] - arrow_len * math.sin(angle + arrow_angle)
                    
                    draw.polygon([end, (x1, y1), (x2, y2)], fill="blue")
                    
                    # Draw number at start
                    x, y = start
                    radius = 15
                    draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill="blue", outline="white", width=2)
                    
                    text = str(step_num)
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    draw.text((x - text_width / 2, y - text_height / 2 - 2), text, fill="white", font=font)

                elif act_type == "type":
                    content = action.get("content", "")
                    if last_click_point:
                        x, y = last_click_point
                        # Offset slightly to not cover the click dot
                        text_x = x + 25
                        text_y = y
                        
                        # Draw number circle
                        radius = 15
                        draw.ellipse([text_x, text_y - radius, text_x + 2 * radius, text_y + radius], fill="green", outline="white", width=2)
                        
                        text = str(step_num)
                        bbox = draw.textbbox((0, 0), text, font=font)
                        text_width = bbox[2] - bbox[0]
                        text_height = bbox[3] - bbox[1]
                        # Center number in circle
                        center_x = text_x + radius
                        center_y = text_y
                        draw.text((center_x - text_width / 2, center_y - text_height / 2 - 2), text, fill="white", font=font)
                        
                        # Draw content text next to circle
                        draw.text((text_x + 2 * radius + 5, text_y - 12), f'"{content}"', fill="green", font=font, stroke_width=1, stroke_fill="white")

            img.save(output_path)
            
    except Exception as e:
        print(f"Error annotating image {image_path}: {e}")


def wait_for_success_message(page: Page, selector: str = "#message") -> None:
    """Give the UI a moment to show success feedback if available."""
    try:
        page.wait_for_selector(selector, timeout=1500)
    except Exception:
        pass
    finally:
        page.wait_for_timeout(500)


def image_dimensions(image_path: str) -> Tuple[int, int]:
    """Return (width, height) for a screenshot on disk."""
    with Image.open(image_path) as img:
        return img.width, img.height
