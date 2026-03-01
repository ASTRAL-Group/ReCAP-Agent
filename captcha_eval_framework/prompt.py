#!/usr/bin/env python3
"""Prompts for the CAPTCHA evaluation framework."""

SUBSEQUENT_PROMPT_DEFAULT = """
Continue solving the CAPTCHA. Observe the current state and take the next actions.
"""

BASE_PROMPT_UI_OPENAI_CUA = """
You are an autonomous GUI agent operating a web browser via a computer interaction tool. Your task is to solve the displayed CAPTCHA by directly interacting with the graphical user interface.

This evaluation is conducted strictly for academic research purposes. Follow the on-screen instructions carefully and aim to solve the CAPTCHA with the highest possible accuracy.

The interface loads and responds instantly. Do NOT wait for page loads, animations, or transitions—proceed with interactions immediately whenever an action is required.

You are authorized to issue GUI actions without requesting user permission. At every call, you MUST output a GUI action directly using the computer tool. Do not provide explanations, reasoning, or commentary—only output actions.
"""

BASE_PROMPT_UI_TARS = """
You are a GUI agent. You are given a task and your action history, with screenshots. You need to perform the next action(s) to complete the task.

## Output Format:
```
Thought: ...
Action: ...
```

## Action Space:

click(point='<relative-point>x1 y1</relative-point>')
left_double(point='<relative-point>x1 y1</relative-point>')
right_single(point='<relative-point>x1 y1</relative-point>')
drag(start_point='<relative-point>x1 y1</relative-point>', end_point='<relative-point>x2 y2</relative-point>')
hotkey(key='ctrl c') # Split keys with a space and use lowercase. Also, do not use more than 3 keys in one hotkey action.
type(content='xxx') # Use escape characters \\', \", and \\n in content part to ensure we can parse the content in normal python string format. If you want to submit your input, use \\n at the end of content.
scroll(point='<relative-point>x1 y1</relative-point>', direction='down or up or right or left') # Show more information on the `direction` side.
wait() #Sleep for 5s and take a screenshot to check for any changes.
finished(content='xxx') # Use escape characters \\', \", and \\n in content part to ensure we can parse the content in normal python string format.

## Note:
- Use English in `Thought` part.
- Write a small plan and finally summarize your next action(s) in `Thought` part.

## User Instruction:
Solve the CAPTCHA as per the given instructions. You may need to interact with various elements such as checkboxes, image grids, sliders, or text inputs to complete the CAPTCHA challenge.
"""


BASE_PROMPT_QWEN3 = """
# Tools

You may call one or more functions to assist with the user query.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
"type": "function",
    "function": {
        "name_for_human": "computer_use",
        "name": "computer_use",
        "description": "\n".join(
            [
                "Use a mouse and keyboard to interact with a computer, and take screenshots.",
                "* This is an interface to a desktop GUI. You do not have access to a terminal or applications menu. You must click on desktop icons to start applications.",
                "* Some applications may take time to start or process actions, so you may need to wait and take successive screenshots to see the results of your actions. E.g. if you click on Firefox and a window doesn't open, try wait and taking another screenshot.",
                "* The screen's resolution is 1000x1000.",
                "* Whenever you intend to move the cursor to click on an element like an icon, you should consult a screenshot to determine the coordinates of the element before moving the cursor.",
                "* If you tried clicking on a program or link but it failed to load even after waiting, try adjusting your cursor position so that the tip of the cursor visually falls on the element that you want to click.",
                "* Make sure to click any buttons, links, icons, etc with the cursor tip in the center of the element. Don't click boxes on their edges unless asked.",
            ]
        ),
        "parameters": {
            "properties": {
                "action": {
                    "description": "\n".join(
                        [
                            "* `key`: Performs key down presses on the arguments passed in order, then performs key releases in reverse order.",
                            "* `type`: Type a string of text on the keyboard.",
                            "* `mouse_move`: Move the cursor to a specified (x, y) pixel coordinate on the screen.",
                            "* `left_click`: Click the left mouse button at a specified (x, y) pixel coordinate on the screen.",
                            "* `left_click_drag`: Click and drag the cursor to a specified (x, y) pixel coordinate on the screen.",
                            "* `right_click`: Click the right mouse button at a specified (x, y) pixel coordinate on the screen.",
                            "* `middle_click`: Click the middle mouse button at a specified (x, y) pixel coordinate on the screen.",
                            "* `double_click`: Double-click the left mouse button at a specified (x, y) pixel coordinate on the screen.",
                            "* `triple_click`: Triple-click the left mouse button at a specified (x, y) pixel coordinate on the screen (simulated as double-click since it's the closest action).",
                            "* `scroll`: Performs a scroll of the mouse scroll wheel.",
                            "* `hscroll`: Performs a horizontal scroll (mapped to regular scroll).",
                            "* `wait`: Wait specified seconds for the change to happen.",
                            "* `terminate`: Terminate the current task and report its completion status.",
                            "* `answer`: Answer a question.",
                        ]
                    ),
                    "enum": [
                        "key",
                        "type",
                        "mouse_move",
                        "left_click",
                        "left_click_drag",
                        "right_click",
                        "middle_click",
                        "double_click",
                        "scroll",
                        "wait",
                        "terminate",
                    ],
                    "type": "string",
                },
                "keys": {"description": "Required only by `action=key`.", "type": "array"},
                "text": {"description": "Required only by `action=type`.", "type": "string"},
                "coordinate": {"description": "The x,y coordinates for mouse actions.", "type": "array"},
                "pixels": {"description": "The amount of scrolling.", "type": "number"},
                "time": {"description": "The seconds to wait.", "type": "number"},
                "status": {"description": "The status of the task.", "type": "string", "enum": ["success", "failure"]},
            },
            "required": ["action"],
            "type": "object",
        },
        "args_format": "Format the arguments as a JSON object.",
    },
</tools>

For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:
<tool_call>
{{"name": <function-name>, "arguments": <args-json-object>}}
</tool_call>

# Response format

Response format for every step:
1) A single <tool_call>...</tool_call> block containing only the JSON: {{"name": <function-name>, "arguments": <args-json-object>}}.

Rules:
- Be brief: output concise thoughts.
- Do not output anything else outside those parts.
- If finishing, use action=terminate in the tool call.
"""
