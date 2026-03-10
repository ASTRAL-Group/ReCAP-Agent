#!/usr/bin/env python3
"""
Action executor module for ui-tars benchmark testing.
Handles execution of parsed actions on web pages using Playwright.
"""

from typing import Dict, List, Optional
from playwright.sync_api import Page
from .config import get_logger

logger = get_logger(__name__)


class ActionExecutor:
    """Executes parsed actions on web pages using Playwright."""

    def __init__(self):
        """Initialize the action executor."""
        pass

    def execute_actions(self, page: Page, actions: List[Dict]) -> bool:
        """Execute parsed actions on the page."""
        try:
            for action in actions:
                action_type = action.get("type")
                
                if action_type == "click":
                    x = self._get_coordinate(action.get("x"))
                    y = self._get_coordinate(action.get("y"))
                    page.mouse.click(x, y)
                    logger.debug(f"Clicked at ({x}, {y})")
                    
                elif action_type == "drag":
                    start_x = self._get_coordinate(action.get("x"))
                    start_y = self._get_coordinate(action.get("y"))
                    end_x = self._get_coordinate(action.get("end_x"))
                    end_y = self._get_coordinate(action.get("end_y"))
                    page.mouse.move(start_x, start_y)
                    page.mouse.down()
                    page.mouse.move(end_x, end_y)
                    page.mouse.up()
                    logger.debug(f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})")
                    
                elif action_type == "type":
                    self._execute_type_action(page, action)
                elif action_type == "type_at":
                    self._execute_type_at_action(page, action)
                elif action_type == "left_double":
                    self._execute_double_click(page, action)
                elif action_type == "right_single":
                    self._execute_right_click(page, action)
                elif action_type == "scroll":
                    self._execute_scroll_action(page, action)
                elif action_type == "hotkey":
                    self._execute_hotkey_action(page, action)
                elif action_type == "finished":
                    logger.debug(f"Model indicates task finished: {action.get('text', '')}")
                    return True
                
                # Small delay between actions
                page.wait_for_timeout(500)
                
            return True
            
        except Exception as e:
            logger.error(f"Error executing actions: {e}")
            return False
    
    def _get_coordinate(self, value: Optional[float]) -> int:
        """Helper to safely parse coordinate values."""
        if value is None:
            return 0
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return 0
    
    def _execute_type_action(self, page: Page, action: Dict):
        """Execute a type action by finding and targeting input fields."""
        text = action["text"]
        
        # Try multiple strategies to find input fields
        input_selectors = [
            'input[type="text"]',
            'input[type="password"]', 
            'input:not([type])',  # input without type (defaults to text)
            'textarea',
            'input[id*="captcha"]',
            'input[name*="captcha"]',
            'input[placeholder*="captcha"]',
            'input[class*="captcha"]',
            'input[id*="text"]',
            'input[name*="text"]',
            'input[placeholder*="text"]',
            'input[class*="text"]',
            'input[id*="answer"]',
            'input[name*="answer"]',
            'input[placeholder*="answer"]',
            'input[class*="answer"]',
        ]
        
        input_found = False
        
        # Strategy 1: Try to find input fields within the viewable area
        for selector in input_selectors:
            try:
                inputs = page.locator(selector).all()
                for input_elem in inputs:
                    if not input_elem.is_visible():
                        continue
                    try:
                        input_elem.fill(text)
                        box = input_elem.bounding_box()
                        if box:
                            logger.debug(f"Typed '{text}' into input field at ({box.get('x')}, {box.get('y')})")
                        else:
                            logger.debug(f"Typed '{text}' into input field located by {selector}")
                        input_found = True
                        break
                    except Exception as selector_error:
                        logger.debug(f"Could not type into element for selector {selector}: {selector_error}")
                        continue
                if input_found:
                    break
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {e}")
                continue
        
        # Strategy 2: If no input found via direct fill, try clicking first then typing
        if not input_found:
            try:
                # Look for any visible input field
                for selector in input_selectors:
                    try:
                        input_elem = page.locator(selector).first
                        if input_elem.is_visible():
                            input_elem.click()
                            input_elem.fill(text)
                            logger.debug(f"Clicked and typed '{text}' into input field")
                            input_found = True
                            break
                    except Exception:
                        continue
            except Exception as e:
                logger.debug(f"Error in strategy 2: {e}")
        
        # Strategy 3: Fallback to global typing (original behavior)
        if not input_found:
            logger.warning(f"No input field found, using global typing for: {text}")
            page.keyboard.type(text)
            logger.debug(f"Typed globally: {text}")
    
    def _execute_type_at_action(self, page: Page, action: Dict):
        """Execute a type action at specific coordinates (click first, then type)."""
        text = action["text"]
        x = self._get_coordinate(action.get("x"))
        y = self._get_coordinate(action.get("y"))
        
        try:
            # Click at the specified coordinates first
            page.mouse.click(x, y)
            logger.debug(f"Clicked at ({x}, {y}) before typing")
            
            # Small delay to ensure the input field is focused
            page.wait_for_timeout(100)
            
            # Type the text
            page.keyboard.type(text)
            logger.debug(f"Typed '{text}' at coordinates ({x}, {y})")
            
        except Exception as e:
            logger.error(f"Error typing at coordinates ({x}, {y}): {e}")
            # Fallback to global typing
            page.keyboard.type(text)
            logger.debug(f"Fallback: typed globally: {text}")
    
    def _execute_double_click(self, page: Page, action: Dict):
        """Execute a double-click action."""
        x = self._get_coordinate(action.get("x"))
        y = self._get_coordinate(action.get("y"))
        
        try:
            page.mouse.dblclick(x, y)
            logger.debug(f"Double-clicked at ({x}, {y})")
        except Exception as e:
            logger.error(f"Error double-clicking at ({x}, {y}): {e}")
    
    def _execute_right_click(self, page: Page, action: Dict):
        """Execute a right-click action."""
        x = self._get_coordinate(action.get("x"))
        y = self._get_coordinate(action.get("y"))
        
        try:
            page.mouse.click(x, y, button='right')
            logger.debug(f"Right-clicked at ({x}, {y})")
        except Exception as e:
            logger.error(f"Error right-clicking at ({x}, {y}): {e}")
    
    def _execute_scroll_action(self, page: Page, action: Dict):
        """Execute a scroll action."""
        direction = action["text"]
        x = self._get_coordinate(action.get("x"))
        y = self._get_coordinate(action.get("y"))
        
        try:
            # Map direction to wheel delta
            wheel_delta = {
                'down': 1,
                'up': -1,
                'right': 1,
                'left': -1
            }.get(direction.lower(), 1)

            # Playwright mouse.wheel method - only takes delta_x and delta_y
            if direction.lower() in ['down', 'up']:
                page.mouse.wheel(0, wheel_delta)
            elif direction.lower() in ['right', 'left']:
                page.mouse.wheel(wheel_delta, 0)
            else:
                page.mouse.wheel(0, wheel_delta)
            logger.debug(f"Scrolled {direction} at ({x}, {y})")
        except Exception as e:
            logger.error(f"Error scrolling {direction} at ({x}, {y}): {e}")
    
    def _execute_hotkey_action(self, page: Page, action: Dict):
        """Execute a hotkey action."""
        key_combination = action["text"]
        
        try:
            # Parse key combination (e.g., "ctrl c" -> ["Control", "c"])
            keys = key_combination.split()
            if len(keys) == 1:
                page.keyboard.press(keys[0])
            elif len(keys) == 2:
                page.keyboard.press(f"{keys[0]}+{keys[1]}")
            else:
                logger.warning(f"Complex key combination not supported: {key_combination}")
                return
            
            logger.debug(f"Pressed hotkey: {key_combination}")
        except Exception as e:
            logger.error(f"Error pressing hotkey {key_combination}: {e}")
