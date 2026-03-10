import argparse
import json
import pathlib
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple, Literal, cast


THINK_PATTERN = re.compile(r"<think>\s*(.*?)\s*</think>", re.DOTALL)
POINT_PATTERN = re.compile(
    r"<point>\s*([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)\s*</point>"
)
RELATIVE_POINT_PATTERN = re.compile(
    r"<relative-point>\s*([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)\s*</relative-point>"
)
POINT_KEYS = {"point", "start_point", "end_point"}

CoordinateMode = Literal["relative", "absolute"]
ActionFormat = Literal["ui-tars", "qwen3"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert run conversations to ShareGPT multi-modal format."
    )
    parser.add_argument(
        "--input",
        type=pathlib.Path,
        required=True,
        help="Path to the generated conversations.json file.",
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        help=(
            "Destination for the ShareGPT formatted dataset. "
            "Defaults to a suffix based on format settings "
            "(_sharegpt_qwen3, _sharegpt_ui_tars_relative, or _sharegpt_ui_tars_absolute)."
        ),
    )
    parser.add_argument(
        "--coordinate-mode",
        choices=("relative", "absolute"),
        default="relative",
        help=(
            "How to represent action coordinates: "
            "'relative' normalizes to 0-1; 'absolute' keeps original values."
        ),
    )
    parser.add_argument(
        "--action-format",
        choices=("ui-tars", "qwen3"),
        default="ui-tars",
        help=(
            "Assistant action emission format. "
            "'ui-tars' emits Action: click(...), "
            "'qwen3' emits <tool_call>{...}</tool_call> blocks."
        ),
    )
    return parser.parse_args()


def read_conversations(path: pathlib.Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_sharegpt(data: Iterable[Dict[str, Any]], path: pathlib.Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(list(data), f, ensure_ascii=False, indent=2)


def normalize_image_path(image_path: str) -> str:
    path = pathlib.Path(image_path)
    parts = path.parts
    if len(parts) >= 3 and parts[0] == "runs":
        path = pathlib.Path(*parts[2:])
    return str(path).replace("\\", "/")


def build_image_dimension_map(sample: Dict[str, Any]) -> Dict[str, Tuple[float, float]]:
    mapping: Dict[str, Tuple[float, float]] = {}

    def add_entry(path: Optional[str], dims: Any) -> None:
        if not path or not isinstance(dims, dict):
            return
        width = dims.get("width")
        height = dims.get("height")
        try:
            w = float(width)
            h = float(height)
        except (TypeError, ValueError):
            return
        if w <= 0 or h <= 0:
            return
        normalized = normalize_image_path(path)
        mapping[normalized] = (w, h)
        mapping[path] = (w, h)

    images = sample.get("images") or {}
    image_dimensions = sample.get("image_dimensions") or {}
    for key, path in images.items():
        add_entry(path, image_dimensions.get(key))

    challenge_meta = sample.get("challenge_meta") or {}
    stage_images = challenge_meta.get("stage_images") or {}
    stage_dimensions = challenge_meta.get("stage_image_dimensions") or {}
    for key, path in stage_images.items():
        add_entry(path, stage_dimensions.get(key))

    step_images = challenge_meta.get("step_images") or {}
    step_dimensions = challenge_meta.get("step_image_dimensions") or {}
    for key, path in step_images.items():
        add_entry(path, step_dimensions.get(key))

    return mapping


def extract_thought(response: str) -> str:
    if not response:
        return ""
    match = THINK_PATTERN.search(response)
    if match:
        result = match.group(1).strip()
    else:
        result = response.strip()

    if result.lower().startswith("thought:"):
        result = result[8:].strip()

    return result


def quote_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
        .replace("'", "\\'")
    )
    return f"'{escaped}'"


ACTION_KEY_ORDER = {
    "click": ("point",),
    "left_double": ("point",),
    "right_single": ("point",),
    "drag": ("start_point", "end_point"),
    "type": ("content",),
    "scroll": ("point", "direction"),
    "hotkey": ("key",),
    "finished": ("content",),
}


def convert_point_to_relative(
    value: str, dimensions: Optional[Tuple[float, float]]
) -> str:
    if dimensions is None:
        return value

    match = POINT_PATTERN.fullmatch(value.strip())
    if not match:
        return value

    width, height = dimensions
    if width == 0 or height == 0:
        return value

    try:
        x = float(match.group(1))
        y = float(match.group(2))
    except ValueError:
        return value

    rel_x = x / width
    rel_y = y / height
    return f"<relative-point>{rel_x:.4f} {rel_y:.4f}</relative-point>"


def convert_point(
    value: str,
    dimensions: Optional[Tuple[float, float]],
    coordinate_mode: CoordinateMode,
) -> str:
    if coordinate_mode == "relative":
        return convert_point_to_relative(value, dimensions)
    return value


def _parse_point(
    value: str, dimensions: Optional[Tuple[float, float]]
) -> Optional[Tuple[float, float]]:
    raw = value.strip()
    absolute_match = POINT_PATTERN.fullmatch(raw)
    if absolute_match:
        try:
            return float(absolute_match.group(1)), float(absolute_match.group(2))
        except ValueError:
            return None

    relative_match = RELATIVE_POINT_PATTERN.fullmatch(raw)
    if not relative_match:
        return None
    try:
        rel_x = float(relative_match.group(1))
        rel_y = float(relative_match.group(2))
    except ValueError:
        return None

    if dimensions:
        width, height = dimensions
        if width > 0 and height > 0:
            return rel_x * width, rel_y * height
    # Fallback: interpret relative points directly on a 1000x1000 grid.
    return rel_x * 999.0, rel_y * 999.0


def _to_qwen_grid(point: Tuple[float, float], dimensions: Optional[Tuple[float, float]]) -> List[int]:
    x, y = point
    if dimensions:
        width, height = dimensions
        if width > 0 and height > 0:
            grid_x = int(round((x / width) * 999.0))
            grid_y = int(round((y / height) * 999.0))
            return [max(0, min(999, grid_x)), max(0, min(999, grid_y))]

    return [max(0, min(999, int(round(x)))), max(0, min(999, int(round(y))))]


def _render_tool_call(arguments: Dict[str, Any]) -> str:
    payload = {"name": "computer_use", "arguments": arguments}
    json_payload = json.dumps(payload, ensure_ascii=True)
    return f"<tool_call>{json_payload}</tool_call>"


def format_action(
    action: Dict[str, Any],
    image_dimensions: Optional[Tuple[float, float]],
    coordinate_mode: CoordinateMode,
) -> str:
    name = action.get("action")
    if not name:
        raise ValueError("Action entry without 'action' field.")

    keys = ACTION_KEY_ORDER.get(name, tuple(k for k in action.keys() if k != "action"))
    parts: List[str] = []
    for key in keys:
        if key not in action:
            continue
        value = action[key]
        if isinstance(value, str) and key in POINT_KEYS:
            value = convert_point(value, image_dimensions, coordinate_mode)
        if isinstance(value, str):
            parts.append(f"{key}={quote_string(value)}")
        else:
            parts.append(f"{key}={value}")

    args = ", ".join(parts)
    if args:
        return f"{name}({args})"
    return f"{name}()"


def format_action_qwen3(
    action: Dict[str, Any],
    image_dimensions: Optional[Tuple[float, float]],
) -> List[str]:
    name = action.get("action")
    if not name:
        raise ValueError("Action entry without 'action' field.")

    if name == "click":
        point_raw = action.get("point")
        if not isinstance(point_raw, str):
            return []
        point = _parse_point(point_raw, image_dimensions)
        if point is None:
            return []
        return [
            _render_tool_call(
                {"action": "left_click", "coordinate": _to_qwen_grid(point, image_dimensions)}
            )
        ]

    if name == "left_double":
        point_raw = action.get("point")
        if not isinstance(point_raw, str):
            return []
        point = _parse_point(point_raw, image_dimensions)
        if point is None:
            return []
        return [
            _render_tool_call(
                {"action": "double_click", "coordinate": _to_qwen_grid(point, image_dimensions)}
            )
        ]

    if name == "right_single":
        point_raw = action.get("point")
        if not isinstance(point_raw, str):
            return []
        point = _parse_point(point_raw, image_dimensions)
        if point is None:
            return []
        return [
            _render_tool_call(
                {"action": "right_click", "coordinate": _to_qwen_grid(point, image_dimensions)}
            )
        ]

    if name == "drag":
        start_raw = action.get("start_point")
        end_raw = action.get("end_point")
        if not isinstance(start_raw, str) or not isinstance(end_raw, str):
            return []

        start_point = _parse_point(start_raw, image_dimensions)
        end_point = _parse_point(end_raw, image_dimensions)
        if end_point is None:
            return []

        calls: List[str] = []
        if start_point is not None:
            calls.append(
                _render_tool_call(
                    {"action": "mouse_move", "coordinate": _to_qwen_grid(start_point, image_dimensions)}
                )
            )
        calls.append(
            _render_tool_call(
                {"action": "left_click_drag", "coordinate": _to_qwen_grid(end_point, image_dimensions)}
            )
        )
        return calls

    if name == "type":
        content = str(action.get("content", ""))
        return [_render_tool_call({"action": "type", "text": content})]

    if name == "scroll":
        direction = str(action.get("direction", "down")).lower()
        pixels_by_direction = {
            "down": 600,
            "up": -600,
            "right": 600,
            "left": -600,
        }
        args: Dict[str, Any] = {"action": "scroll", "pixels": pixels_by_direction.get(direction, 600)}
        point_raw = action.get("point")
        if isinstance(point_raw, str):
            point = _parse_point(point_raw, image_dimensions)
            if point is not None:
                args["coordinate"] = _to_qwen_grid(point, image_dimensions)
        return [_render_tool_call(args)]

    if name == "hotkey":
        key_raw = str(action.get("key", "")).strip()
        if not key_raw:
            return []
        keys = [token for token in re.split(r"[+\s]+", key_raw) if token]
        return [_render_tool_call({"action": "key", "keys": keys})]

    if name == "wait":
        return [_render_tool_call({"action": "wait", "time": 5.0})]

    if name == "finished":
        return [_render_tool_call({"action": "terminate", "status": "success"})]

    return []


def build_messages(
    sample: Dict[str, Any],
    coordinate_mode: CoordinateMode,
    action_format: ActionFormat,
) -> Dict[str, Any]:
    messages: List[Dict[str, str]] = []
    image_paths: List[str] = []
    dimension_map = build_image_dimension_map(sample)
    current_dimensions: Optional[Tuple[float, float]] = None

    for turn in sample.get("conversations", []):
        speaker = turn.get("from")
        value = turn.get("value", {})

        if speaker == "system":
            content = (value.get("content") or value.get("input") or "").strip()
            messages.append({"role": "system", "content": content})
            current_dimensions = None
        elif speaker == "human":
            raw_text = (value.get("input") or "").strip()
            image_path = value.get("image")
            content = raw_text

            if image_path:
                rel_path = normalize_image_path(image_path)
                image_paths.append(rel_path)
                content = "<image>" if not raw_text else f"<image>\n{raw_text}"
                current_dimensions = (
                    dimension_map.get(rel_path) or dimension_map.get(image_path)
                )
            else:
                current_dimensions = None

            messages.append({"role": "user", "content": content})
        elif speaker == "gpt":
            response_text = value.get("response") or ""
            thought = extract_thought(response_text)
            actions = value.get("actions") or []
            action_block = ""
            convert_actions = value.get("convert_actions", True)
            if convert_actions and actions:
                if action_format == "qwen3":
                    rendered_blocks: List[str] = []
                    for action in actions:
                        rendered_blocks.extend(
                            format_action_qwen3(action, current_dimensions)
                        )
                    if rendered_blocks:
                        action_block = "\n".join(rendered_blocks)
                else:
                    formatted_actions = [
                        format_action(action, current_dimensions, coordinate_mode)
                        for action in actions
                    ]
                    if formatted_actions:
                        action_block = "\n".join(formatted_actions)

            if action_format == "qwen3":
                content_lines: List[str] = []
                if thought:
                    content_lines.append(f"<think>{thought}</think>")
            else:
                content_lines = [f"Thought: {thought}"]
            if action_block:
                if action_format == "qwen3":
                    content_lines.append(action_block)
                else:
                    content_lines.append(f"Action: {action_block}")
            if not content_lines:
                content_lines.append("")

            messages.append({"role": "assistant", "content": "\n".join(content_lines)})

    return {"messages": messages, "images": image_paths}


def convert(
    input_path: pathlib.Path,
    coordinate_mode: CoordinateMode = "relative",
    action_format: ActionFormat = "ui-tars",
) -> List[Dict[str, Any]]:
    data = read_conversations(input_path)
    return [
        build_messages(sample, coordinate_mode, action_format) for sample in data
    ]


def main() -> None:
    args = parse_args()
    coordinate_mode = cast(CoordinateMode, args.coordinate_mode)
    action_format = cast(ActionFormat, args.action_format)

    output_path = args.output
    if output_path is None:
        if action_format == "qwen3":
            suffix = "_sharegpt_qwen3"
        elif coordinate_mode == "absolute":
            suffix = "_sharegpt_ui_tars_absolute"
        else:
            suffix = "_sharegpt_ui_tars_relative"
        output_path = args.input.with_name(f"{args.input.stem}{suffix}.json")
    sharegpt_data = convert(
        args.input,
        coordinate_mode=coordinate_mode,
        action_format=action_format,
    )
    write_sharegpt(sharegpt_data, output_path)


if __name__ == "__main__":
    main()
