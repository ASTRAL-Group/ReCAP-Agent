from typing import Dict, Optional, Sequence, Union, Tuple, List
import os

from .descriptions import describe_actions, describe_challenge
from .model_client import generate_reasoning
from .utils import annotate_image


ScreenshotInputs = Optional[Union[str, Sequence[str]]]


def _normalize_screenshot_inputs(screenshots: ScreenshotInputs) -> Optional[list[str]]:
    if screenshots is None:
        return None
    if isinstance(screenshots, str):
        normalized = [screenshots]
    else:
        normalized = [path for path in screenshots if path]
    return normalized or None


def _ensure_think_wrapped(text: str) -> str:
    content = text.strip()
    if not content:
        return content
    lowered = content.lower()
    if lowered.startswith("<think>") and lowered.endswith("</think>"):
        return content
    if lowered.startswith("thinking:"):
        content = content[len("thinking:"):].strip()
    return f"<think>{content}</think>"


def generate_model_reasoning(
    challenge_type: str,
    solution_data: Dict,
    screenshot_paths: ScreenshotInputs = None,
    actions: Optional[List[Dict]] = None,
) -> Tuple[str, List[str]]:
    """Generate reasoning for a challenge.
    
    Returns:
        Tuple of (reasoning_text, list_of_annotated_image_paths)
    """
    annotated_files = []

    prompt = (
        "You are documenting the internal reasoning for a CAPTCHA-solving assistant before it acts. \n"

        f"Challenge type: {challenge_type}. \n"
        f"Challenge details: {describe_challenge(challenge_type, solution_data)} \n"
        f"Planned actions: {describe_actions(challenge_type, solution_data)}\n"
        f"You are also provided with initial CAPTCHA screenshot and the annotated version of the screenshot with the actions steps the assistant should take. While you can use the annotations to understand the scene, you should not mention the existence of the annotations in your reasoning.\n"

        """
        **REQUIREMENTS**
        1. Output must be wrapped by <think> ... </think>.
        2. Detialed Requirements:
        - You should think base on the provided images.
        - Describe what you **observe** in the CAPTCHA scene (layout, visual cues, objects, etc.).
        - Explain what you **infer** from those observations (what the task requires).
        - Describe what you **plan** to do (actions) step by step. Make sure you exactly follow the order included in planned actions.
        - Example output:
            “I observe that I am currently in a webpage that ask me solve a CAPTCHA. The CAPTCHA asks me to select the icon "book". Below the text instruction of the CAPTCHA, I can see a canvas with several icons of different color in the river background. On top left of the canvas, there's a purple icon that looks like "duck", to the right there's an icon that looks like "car", ...... On the second row I see a blue "book" icon, which may be the icon I should click ..... I need to perform multiple actions to solve this CAPTCHA: I should click on the "book" icon on the second row to finish the task.”
        
        **CAPTCHA-specific Hints**
        - For CAPTCHAs that use the "type" operation, remember to click on the input box first before typing in the answer.
        - For Image Grid, you should describe each image block and make a judgment on whether the required element exists, then click on the correct image blocks.
        - When a submit/verify button is present, end the plan by clicking it. Some slider and icon CAPTCHAs do not have a submit button and generally submit automatically after the main action is completed.
        """
    )

    normalized_paths = _normalize_screenshot_inputs(screenshot_paths)
    
    # Annotate the 'before' image (index 0) if actions are provided
    if actions and normalized_paths and len(normalized_paths) > 0:
        before_image_path = normalized_paths[0]
        base, ext = os.path.splitext(before_image_path)
        annotated_path = f"{base}_annotated{ext}"
        try:
            annotate_image(before_image_path, actions, annotated_path)
            normalized_paths.append(annotated_path)
            annotated_files.append(annotated_path)
        except Exception as e:
            print(f"Warning: Failed to annotate image {before_image_path}: {e}")

    reasoning: str = generate_reasoning(prompt, normalized_paths)
    reasoning = reasoning.strip()
    if not reasoning:
        raise RuntimeError("Reasoning model returned empty output for direct trace generation.")
    return _ensure_think_wrapped(reasoning), annotated_files

def generate_correction_reasoning(
    challenge_type: str,
    conversations: Dict,
    solution_data: Dict,
    screenshot_paths: ScreenshotInputs = None,
) -> Tuple[str, str]:
    """
    Generate correction reasoning from the current failed state.

    Args:
        challenge_type: Type of CAPTCHA (text, icon_selection, etc.)
        conversations: Dictionary containing previous attempt details including:
                      - model's initial reasoning
                      - actions the model took
                      - ground truth actions (in model format with relative coordinates)
                      - solver_actions (optional, raw solver actions for annotation)
        solution_data: Ground truth solution data
        screenshot_paths: Path(s) for the current failed CAPTCHA state screenshot(s)

    Returns:
        Tuple of (prompt, corrected_reasoning)
        The corrected reasoning contains thought only; actions are appended separately.
    """
    # Extract previous attempt details from conversations
    model_reasoning = conversations.get("model_response", "")
    model_actions = conversations.get("model_actions", [])
    solver_actions_formatted = conversations.get("solver_actions_formatted", [])
    solver_actions = conversations.get("solver_actions", [])

    prompt = (
        "You are documenting the corrected internal reasoning for a CAPTCHA-solving assistant after a failed attempt. \n"

        "You are given the current CAPTCHA state after your failed attempt, plus an annotated version of the same current state with action steps to solve it. Although you have access to the correct actions and annotated image, you should pretend to find out the mistakes by yourself from the failed attempt reasoning and current screenshot. You should never mention the correct actions or annotated image in your output."

        f"Challenge type: {challenge_type}."
        f"Challenge details: {describe_challenge(challenge_type, solution_data)}"
        f"Previous reasoning: {model_reasoning}"
        f"Previous actions: {model_actions}"
        f"Correct actions: {solver_actions_formatted}"

        f"""
        **REQUIREMENTS**
        1. Output must be wrapped by <think> ... </think>.
        2. Your output should ONLY contain the thinking part, NOT the action part. The actions will be added separately.
        3. Detailed Requirements:
        - Write one concise paragraph (150-200 words).
        - Describe what you **observe and infer** in the CAPTCHA scene (layout, visual cues, objects, etc.).
        - Analyze what you **did wrong** in your previous attempt and why the correct actions are right.
        - Describe what you **plan** to do (correct actions) step by step. Make sure you exactly follow the order included in correct actions.
        - Example output:
            "<think>I observe that I am currently in a webpage that asks me to solve a CAPTCHA. The CAPTCHA asks me to select the icon "book". Below the text instruction of the CAPTCHA, I can see a canvas with several icons of different color in the river background. On top left of the canvas, there's a purple icon that looks like "duck", to the right there's an icon that looks like "car", ...... On the second row I see a blue "book" icon, which may be the icon I should click. In my previous attempt, I incorrectly clicked on the "car" icon because I misidentified it as a "book". Looking at the second image, I can see that this action was wrong and the CAPTCHA failed. The correct approach is to click on the blue "book" icon on the second row, which clearly represents a book, not a car. I need to perform multiple actions to solve this CAPTCHA: I should click on the "book" icon on the second row to finish the task.</think>"

        **CAPTCHA-specific Hints**
        {correction_speceifc_reasoning_mapping(challenge_type)}
        """
    )

    normalized_paths = _normalize_screenshot_inputs(screenshot_paths)
    
    # Annotate the current image (index 0) if solver_actions are provided.
    if solver_actions and normalized_paths and len(normalized_paths) > 0:
        after_image_path = normalized_paths[0]
        # Create annotated path: filename.png -> filename_annotated.png
        base, ext = os.path.splitext(after_image_path)
        annotated_path = f"{base}_annotated{ext}"
        try:
            annotate_image(after_image_path, solver_actions, annotated_path)
            normalized_paths.append(annotated_path)
        except Exception as e:
            print(f"Warning: Failed to annotate image {after_image_path}: {e}")

    reasoning: str = generate_reasoning(prompt, normalized_paths)
    reasoning = reasoning.strip()
    if not reasoning:
        raise RuntimeError("Reasoning model returned empty output for correction trace.")
    return prompt, _ensure_think_wrapped(reasoning)

def correction_speceifc_reasoning_mapping(challenge_type: str) -> str:
    mapping = {
        "text": "- For CAPTCHAs that use the \"type\" operation, focus on if you recognize the image correctly. Focus on reasoning about the different characters. The answer do not need to be case-sensitive unless specified otherwise.",
        "compact_text": "- For CAPTCHAs that use the \"type\" operation, focus on if you recognize the image correctly. Focus on reasoning about the different characters. The answer do not need to be case-sensitive unless specified otherwise.",
        "image_grid": "- For image-grid CAPTCHAs, the most common error is missing or over-selecting tiles. Compare selected tiles against the target concept and verify all required tiles are clicked before submit.",
        "icon_selection": "- For icon selection CAPTCHAs, if the correct icon location is close to an incorrect one, it's likely your click is a bit off the points. But if the target icon is far from incorrect ones, it's likely you clicked the wrong icon due to misidentification.",
        "paged": "- For paged CAPTCHAs, verify you cycle through cards in order and stop only when the target icon is visible before submitting.",
        "slider": "- If the screenshot or your previous thinking looks good, but the actions were still wrong, consider other potential with inaccurate click positions or missing clicks on submit/verify buttons.",
        "icon_match": "- If the screenshot or your previous thinking looks good, but actions still failed, consider inaccurate drag endpoints or releasing too far from the matching icon."
    }
    return mapping.get(challenge_type, "")
