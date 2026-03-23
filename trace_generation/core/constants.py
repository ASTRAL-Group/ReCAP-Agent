import os


BASE_URL = os.getenv(
    "DYNAMIC_PROVIDER_URL",
    os.getenv("DYNAMIC_CAPTCHA_BASE_URL", "http://localhost:5000"),
).rstrip("/")

CHALLENGE_ROUTES = {
    "text": "/challenge/text",
    "compact_text": "/challenge/compact",
    "icon_selection": "/challenge/icon",
    "paged": "/challenge/paged",
    "icon_match": "/challenge/icon-match",
    "slider": "/challenge/slider",
    "image_grid": "/challenge/image_grid",
}

SUPPORTED_CHALLENGE_TYPES = tuple(CHALLENGE_ROUTES.keys())

CLI_CHALLENGE_OPTIONS = [
    ("Mixed rotation (all challenge types)", None),
    ("Text CAPTCHA", "text"),
    ("Compact Text CAPTCHA", "compact_text"),
    ("Icon Selection CAPTCHA", "icon_selection"),
    ("Paged CAPTCHA", "paged"),
    ("Icon Match CAPTCHA", "icon_match"),
    ("Slider CAPTCHA", "slider"),
    ("Image Grid CAPTCHA", "image_grid"),
]

SYSTEM_PROMPT = f"""
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
type(content='xxx') # Use escape characters \\', \\\", and \\n in content part to ensure we can parse the content in normal python string format. If you want to submit your input, use \\n at the end of content. 
scroll(point='<relative-point>x1 y1</relative-point>', direction='down or up or right or left') # Show more information on the `direction` side.
wait() #Sleep for 5s and take a screenshot to check for any changes.
finished(content='xxx') # Use escape characters \\', \\", and \\n in content part to ensure we can parse the content in normal python string format.


## Note:
- Use English in `Thought` part.
- Write a small plan and finally summarize your next action(s) in `Thought` part.
"""

DEFAULT_PROMPT1 = """
Solve the CAPTCHA as per the given instructions. You may need to interact with various elements such as checkboxes, image grids, sliders, or text inputs to complete the CAPTCHA challenge.
"""

DEFAULT_PROMPT2 = """
Solve the CAPTCHA by observing the screenshots and taking appropriate actions. Make sure to follow the instructions provided in the CAPTCHA challenge carefully.
"""

DEFAULT_PROMPT3 = """
Complete the CAPTCHA challenge by analyzing the screenshots and performing the necessary actions. Pay attention to any specific requirements or instructions given in the CAPTCHA.
"""

DEFAULT_PROMPTS = (DEFAULT_PROMPT1, DEFAULT_PROMPT2, DEFAULT_PROMPT3)

FOLLOWUP_PROMPT1 = """
Continue solving the CAPTCHA. Observe the current state and take the next actions.
"""

FOLLOWUP_PROMPT2 = """
Proceed with solving the CAPTCHA based on the latest screenshots. Determine the next steps needed to complete the challenge.
"""

FOLLOWUP_PROMPT3 = """
Continue working on the CAPTCHA challenge. Analyze the recent screenshots and decide on the subsequent actions to take.
"""

FOLLOWUP_PROMPTS = (FOLLOWUP_PROMPT1, FOLLOWUP_PROMPT2, FOLLOWUP_PROMPT3)

PUZZLE_MASK_LABELS = {
    "PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCAxMjAgMTIwJz4KICA8cGF0aCBkPSdNMjQgMGg0OGExMiAxMiAwIDAgMSAxMiAxMnYxMmExMiAxMiAwIDAgMCAxMiAxMmgxMmExMiAxMiAwIDAgMSAxMiAxMnYxMmExMiAxMiAwIDAgMS0xMiAxMmgtMTJhMTIgMTIgMCAwIDAtMTIgMTJ2MTJhMTIgMTIgMCAwIDEtMTIgMTJIMjRhMTIgMTIgMCAwIDEtMTItMTJWODRhMTIgMTIgMCAwIDAtMTItMTJIMGExMiAxMiAwIDAgMSAwLTI0aDEyYTEyIDEyIDAgMCAwIDEyLTEyVjEyQTEyIDEyIDAgMCAxIDI0IDB6JyBmaWxsPSdibGFjaycvPgo8L3N2Zz4=":
        "classic jigsaw tab",
    "PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCAxMjAgMTIwJz4KICA8cGF0aCBkPSdNMjggMGgzNmExMiAxMiAwIDAgMSAxMiAxMnY4YTE4IDE4IDAgMCAwIDE4IDE4aDhhMTIgMTIgMCAwIDEgMTIgMTJ2MjBhMTIgMTIgMCAwIDEtMTIgMTJoLThhMTggMTggMCAwIDAtMTggMTh2OGExMiAxMiAwIDAgMS0xMiAxMkgyOGExMiAxMiAwIDAgMS0xMi0xMlY5MmExOCAxOCAwIDAgMC0xOC0xOEg4YTEyIDEyIDAgMCAxIDAtMjRoMGExOCAxOCAwIDAgMCAxOC0xOFYxMkExMiAxMiAwIDAgMSAyOCAweicgZmlsbD0nYmxhY2snLz4KICA8Y2lyY2xlIGN4PSczMicgY3k9JzQ4JyByPScxMCcgZmlsbD0nd2hpdGUnLz4KICA8Y2lyY2xlIGN4PSc4OCcgY3k9JzcyJyByPScxMCcgZmlsbD0nd2hpdGUnLz4KPC9zdmc+":
        "double-tab silhouette",
    "PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCAxMjAgMTIwJz4KICA8cGF0aCBkPSdNMjAgMGg0NGExMiAxMiAwIDAgMSAxMiAxMnYxMGExNiAxNiAwIDAgMCAxNiAxNmgxOGExMCAxMCAwIDAgMSAwIDIwSDkyYTE2IDE2IDAgMCAwLTE2IDE2djE4YTEwIDEwIDAgMCAxLTIwIDBWNzRhMTYgMTYgMCAwIDAtMTYtMTZIMTJhMTIgMTIgMCAwIDEtMTItMTJWMTJBMTIgMTIgMCAwIDEgMjAgMHonIGZpbGw9J2JsYWNrJy8+Cjwvc3ZnPg==":
        "rounded block cutout",
}
