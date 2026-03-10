from typing import Dict, List, Optional, Tuple

import requests
from playwright.sync_api import Page # pyright: ignore[reportMissingImports]

from .constants import BASE_URL
from .utils import format_point, wait_for_success_message


def _active_paged_state(page: Page, card_icons: List[str]) -> Tuple[int, str]:
    active_locator = page.locator(".icon-card.active").first
    if active_locator.count() == 0:
        active_locator = page.locator(".icon-card").first
    idx_str = active_locator.get_attribute("data-index") or "0"
    try:
        idx = int(idx_str)
    except (TypeError, ValueError):
        idx = 0
    icon_key = (
        active_locator.get_attribute("data-icon")
        or active_locator.get_attribute("data-card-key")
        or ""
    )
    if not icon_key and card_icons and 0 <= idx < len(card_icons):
        icon_key = card_icons[idx]
    return idx, icon_key


def solve_text_like(page: Page, solution: str, execute: bool = True) -> List[Dict[str, str]]:
    input_locator = page.locator("#captcha-input")
    submit_locator = page.locator("#submit-btn")

    input_box = input_locator.bounding_box()
    submit_box = submit_locator.bounding_box()

    if not input_box or not submit_box:
        raise RuntimeError("Unable to locate text CAPTCHA elements.")

    click_point = format_point(
        input_box["x"] + input_box["width"] / 2,
        input_box["y"] + input_box["height"] / 2,
    )
    submit_point = format_point(
        submit_box["x"] + submit_box["width"] / 2,
        submit_box["y"] + submit_box["height"] / 2,
    )

    actions: List[Dict[str, str]] = [
        {"action": "click", "point": click_point},
        {"action": "type", "content": solution},
        {"action": "click", "point": submit_point},
    ]

    if not execute:
        return actions
    
    input_locator.click()
    page.wait_for_timeout(200)
    input_locator.fill("")
    input_locator.type(solution, delay=50)
    page.wait_for_timeout(200)
    submit_locator.click()
    wait_for_success_message(page)

    return actions


def solve_icon(page: Page, solution_data: dict, execute: bool = True) -> List[Dict[str, str]]:
    target_icon = solution_data.get("solution") or solution_data.get("target_icon")
    if not target_icon:
        raise RuntimeError("Icon solution data missing target identifier.")

    submit_locator = page.locator("#submit-btn")
    has_submit_element = submit_locator.count() > 0
    requires_submit_meta = solution_data.get("requires_submit")
    if requires_submit_meta is None:
        requires_submit = has_submit_element
    else:
        requires_submit = bool(requires_submit_meta)
    if requires_submit and not has_submit_element:
        requires_submit = False
    submit_box = submit_locator.bounding_box() if requires_submit else None
    if requires_submit and not submit_box:
        raise RuntimeError("Unable to locate icon CAPTCHA submit button.")

    click_x = click_y = None
    positions = solution_data.get("positions")
    all_icons = solution_data.get("all_icons")
    icon_size = solution_data.get("icon_size")

    if isinstance(all_icons, list) and isinstance(positions, list) and icon_size:
        try:
            icon_index = all_icons.index(target_icon)
            icon_x, icon_y = positions[icon_index]
            canvas_box = page.locator(".icon-grid").bounding_box()
            if canvas_box:
                click_x = canvas_box["x"] + icon_x + icon_size / 2
                click_y = canvas_box["y"] + icon_y + icon_size / 2
        except (ValueError, TypeError):
            click_x = click_y = None

    actions: List[Dict[str, str]] = []

    if click_x is not None and click_y is not None:
        actions.append({"action": "click", "point": format_point(click_x, click_y)})
        if execute:
            page.mouse.move(click_x, click_y)
            page.mouse.click(click_x, click_y, delay=30)
    else:
        icon_locator = page.locator(f".icon-option[data-icon='{target_icon}']")
        icon_box = icon_locator.bounding_box()
        if not icon_box:
            raise RuntimeError("Unable to locate icon element for target icon.")
        click_x = icon_box["x"] + icon_box["width"] / 2
        click_y = icon_box["y"] + icon_box["height"] / 2
        actions.append({"action": "click", "point": format_point(click_x, click_y)})
        icon_locator.click()

    page.wait_for_timeout(250)

    if requires_submit and submit_box:
        submit_point = format_point(
            submit_box["x"] + submit_box["width"] / 2,
            submit_box["y"] + submit_box["height"] / 2,
        )
        actions.append({"action": "click", "point": submit_point})
        if execute: 
            submit_locator.click()
    else:
        page.wait_for_timeout(100)
    
    if execute:
        wait_for_success_message(page)

    return actions


def solve_paged(page: Page, solution_data: dict, execute: bool = True) -> List[Dict[str, str]]:
    target_icon = solution_data.get("solution") or solution_data.get("target_icon")
    card_icons = solution_data.get("card_icons") or []
    if not target_icon:
        raise RuntimeError("Icon slider solution data missing target identifier.")

    nav_right = page.locator(".nav-right")
    submit_locator = page.locator("#submit-btn")
    try:
        total_cards = int(solution_data.get("total_cards") or 0)
    except (TypeError, ValueError):
        total_cards = 0
    if total_cards <= 0:
        total_cards = len(card_icons) if card_icons else page.locator(".icon-card").count()
    total_cards = max(total_cards, 1)

    actions: List[Dict[str, str]] = []
    current_index, current_icon = _active_paged_state(page, card_icons)

    max_steps = total_cards + 2
    for _ in range(max_steps):
        if current_icon == target_icon:
            break
        nav_box = nav_right.bounding_box()
        if not nav_box:
            raise RuntimeError("Unable to locate icon slider navigation button.")
        click_point = format_point(
            nav_box["x"] + nav_box["width"] / 2,
            nav_box["y"] + nav_box["height"] / 2,
        )
        step_action = {"action": "click", "point": click_point}
        actions.append(step_action)
        if execute:
            nav_right.click()
            page.wait_for_timeout(200)
        current_index, current_icon = _active_paged_state(page, card_icons)

    submit_box = submit_locator.bounding_box()
    if not submit_box:
        raise RuntimeError("Unable to locate icon slider submit button.")
    submit_point = format_point(
        submit_box["x"] + submit_box["width"] / 2,
        submit_box["y"] + submit_box["height"] / 2,
    )
    actions.append({"action": "click", "point": submit_point})
    if execute:
        submit_locator.click()

    if execute:
        wait_for_success_message(page)

    return actions


def solve_icon_match(page: Page, solution_data: dict, execute: bool = True) -> List[Dict[str, str]]:
    match_pair_ids = solution_data.get("solution") or solution_data.get("match_pair_ids")
    if not isinstance(match_pair_ids, list) or len(match_pair_ids) < 2:
        raise RuntimeError("Icon match solution data missing pair identifiers.")

    source_id, target_id = match_pair_ids[:2]
    source_locator = page.locator(f".icon-piece[data-icon-id='{source_id}']")
    target_locator = page.locator(f".icon-piece[data-icon-id='{target_id}']")

    source_box = source_locator.bounding_box()
    target_box = target_locator.bounding_box()
    if not source_box or not target_box:
        raise RuntimeError("Unable to locate icon match pieces on the canvas.")

    start_x = source_box["x"] + source_box["width"] / 2
    start_y = source_box["y"] + source_box["height"] / 2
    end_x = target_box["x"] + target_box["width"] / 2
    end_y = target_box["y"] + target_box["height"] / 2

    actions: List[Dict[str, str]] = [
        {
            "action": "drag",
            "start_point": format_point(start_x, start_y),
            "end_point": format_point(end_x, end_y),
        }
    ]

    if execute:
        source_locator.drag_to(
            target_locator,
            target_position={
                "x": float(target_box["width"] / 2),
                "y": float(target_box["height"] / 2),
            },
            timeout=1000,
        )
        # page.mouse.move(start_x, start_y)
        # page.mouse.down()
        # page.mouse.move(end_x, end_y, steps=20)
        # page.mouse.up()
        page.wait_for_timeout(250)
        wait_for_success_message(page)
    
    return actions


def solve_slider(page: Page, solution_data: dict, execute: bool = True) -> List[Dict[str, str]]:
    track_locator = page.locator("#slider-track")
    handle_locator = page.locator("#slider-handle")
    submit_locator = page.locator("#submit-btn")
    has_submit_element = submit_locator.count() > 0
    requires_submit_meta = solution_data.get("requires_submit")
    if requires_submit_meta is None:
        requires_submit = has_submit_element
    else:
        requires_submit = bool(requires_submit_meta)
    if requires_submit and not has_submit_element:
        requires_submit = False

    track_box = track_locator.bounding_box()
    handle_box = handle_locator.bounding_box()
    submit_box = submit_locator.bounding_box() if requires_submit else None

    if not track_box or not handle_box:
        raise RuntimeError("Unable to locate slider CAPTCHA elements.")
    if requires_submit and not submit_box:
        raise RuntimeError("Unable to locate slider CAPTCHA submit button.")

    target_position = solution_data.get("solution")
    track_width = solution_data.get("track_width")
    if target_position is None or track_width is None:
        raise RuntimeError("Slider solution data is incomplete.")

    target_ratio = target_position / track_width if track_width else 0.0
    target_ratio = max(0.0, min(1.0, target_ratio))

    start_x = handle_box["x"] + handle_box["width"] / 2
    start_y = handle_box["y"] + handle_box["height"] / 2
    end_x = track_box["x"] + track_box["width"] * target_ratio
    end_y = track_box["y"] + track_box["height"] / 2

    actions: List[Dict[str, str]] = [
        {
            "action": "drag",
            "start_point": format_point(start_x, start_y),
            "end_point": format_point(end_x, end_y),
        },
    ]
    if requires_submit and submit_box:
        submit_point = format_point(
            submit_box["x"] + submit_box["width"] / 2,
            submit_box["y"] + submit_box["height"] / 2,
        )
        actions.append({"action": "click", "point": submit_point})
    
    if not execute:
        return actions

    target_offset = max(0.0, min(track_box["width"], track_box["width"] * target_ratio))
    try:
        handle_locator.drag_to(
            track_locator,
            target_position={
                "x": float(target_offset),
                "y": float(track_box["height"] / 2),
            },
        )
    except Exception:
        page.mouse.move(start_x, start_y)
        page.mouse.down()
        page.mouse.move(end_x, end_y)
        page.mouse.up()

    try:
        page.wait_for_function(
            "() => {\n"
            "  const el = document.getElementById('slider-position');\n"
            "  if (!el) { return false; }\n"
            "  const val = parseFloat(el.value || '0');\n"
            "  return Math.abs(val - arguments[0]) <= 1;\n"
            "}",
            arg=target_position,
            timeout=2000,
        )
    except Exception:
        pass
    page.wait_for_timeout(250)

    if requires_submit:
        submit_locator.click()
    else:
        page.wait_for_timeout(250)

    wait_for_success_message(page)

    return actions


def solve_image_grid(page: Page, solution_data: dict, execute: bool = True) -> List[Dict[str, str]]:
    checkbox_locator = page.locator("#checkbox")
    verify_locator = page.locator("#verify-btn")
    challenge_wrapper = page.locator("#challenge-wrapper")

    actions: List[Dict[str, str]] = []

    # Open challenge popup if needed.
    wrapper_classes = challenge_wrapper.get_attribute("class") or ""
    is_open = "show" in wrapper_classes
    if not is_open:
        checkbox_box = checkbox_locator.bounding_box()
        if not checkbox_box:
            raise RuntimeError("Unable to locate image-grid checkbox.")
        checkbox_point = format_point(
            checkbox_box["x"] + checkbox_box["width"] / 2,
            checkbox_box["y"] + checkbox_box["height"] / 2,
        )
        actions.append({"action": "click", "point": checkbox_point})
        checkbox_locator.click()
        page.wait_for_selector(".image-tile", state="visible", timeout=5000)

    challenge_id = page.locator("#challenge-id").input_value()
    correct_tiles: List[int] = []
    selected_tiles: List[int] = []

    if challenge_id:
        try:
            status_response = requests.get(f"{BASE_URL}/status/{challenge_id}", timeout=5)
            if status_response.ok:
                status_payload = status_response.json()
                selected_tiles = [int(idx) for idx in status_payload.get("selected_tiles", [])]
        except Exception:
            selected_tiles = []

        try:
            challenge_response = requests.get(f"{BASE_URL}/challenge/image_grid/data/{challenge_id}", timeout=5)
            challenge_response.raise_for_status()
            challenge_payload = challenge_response.json()
            correct_tiles = [int(idx) for idx in challenge_payload.get("correct_tiles", [])]
        except Exception:
            correct_tiles = []

    if not correct_tiles:
        raw_tiles = solution_data.get("solution", [])
        if isinstance(raw_tiles, list):
            correct_tiles = [int(idx) for idx in raw_tiles]

    tiles_to_click = sorted(set(correct_tiles) ^ set(selected_tiles))
    for tile_index in tiles_to_click:
        tile_locator = page.locator(f".image-tile[data-index='{tile_index}']")
        tile_box = tile_locator.bounding_box()
        if not tile_box:
            raise RuntimeError(f"Unable to locate tile {tile_index} in image-grid challenge.")
        tile_point = format_point(
            tile_box["x"] + tile_box["width"] / 2,
            tile_box["y"] + tile_box["height"] / 2,
        )
        actions.append({"action": "click", "point": tile_point})
        if execute:
            tile_locator.click()
            page.wait_for_timeout(150)

    verify_box = verify_locator.bounding_box()
    if not verify_box:
        raise RuntimeError("Unable to locate image-grid verify button.")

    verify_point = format_point(
        verify_box["x"] + verify_box["width"] / 2,
        verify_box["y"] + verify_box["height"] / 2,
    )
    actions.append({"action": "click", "point": verify_point})
    if execute:
        verify_locator.click()
        wait_for_success_message(page)

    return actions


SOLVER_MAP = {
    "text": solve_text_like,
    "compact_text": solve_text_like,
    "icon_selection": solve_icon,
    "paged": solve_paged,
    "icon_match": solve_icon_match,
    "slider": solve_slider,
    "image_grid": solve_image_grid,
}
