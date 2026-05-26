"""
Browser action definitions and execution.
"""

import os
from typing import Any

# System prompt with all available actions
SYSTEM_PROMPT = """You are a browser automation agent. You can see screenshots of a webpage and decide what action to take next.

Available actions (respond with JSON):

NAVIGATION:
- {"action": "goto", "url": "https://..."}
- {"action": "back"} - Go back in browser history
- {"action": "forward"} - Go forward in browser history
- {"action": "refresh"} - Reload the current page

MOUSE ACTIONS:
- {"action": "click", "selector": "CSS selector"}
- {"action": "double_click", "selector": "CSS selector"}
- {"action": "right_click", "selector": "CSS selector"}
- {"action": "hover", "selector": "CSS selector"} - Hover over element (useful for dropdowns/menus)

FORM INPUTS:
- {"action": "fill", "selector": "CSS selector", "value": "text to type"}
- {"action": "clear", "selector": "CSS selector"} - Clear an input field
- {"action": "select", "selector": "CSS selector", "value": "option value or label"} - Select dropdown option
- {"action": "check", "selector": "CSS selector"} - Check a checkbox
- {"action": "uncheck", "selector": "CSS selector"} - Uncheck a checkbox
- {"action": "upload", "selector": "CSS selector", "filepath": "/path/to/file"} - Upload a file

KEYBOARD:
- {"action": "press", "key": "Enter|Tab|Escape|ArrowDown|ArrowUp|Space|Backspace|Delete|a|b|..."} - Press a key
- {"action": "press", "key": "Control+a"} - Key combination (use Control, Shift, Alt, Meta)
- {"action": "type", "text": "text to type"} - Type text without targeting specific element

SCROLLING:
- {"action": "scroll", "direction": "down|up", "amount": 500} - Scroll by pixels (default 500)
- {"action": "scroll_to", "selector": "CSS selector"} - Scroll element into view

DATA EXTRACTION:
- {"action": "extract", "selector": "CSS selector", "description": "what to extract"}
- {"action": "get_attribute", "selector": "CSS selector", "attribute": "href|src|value|..."}
- {"action": "get_text", "selector": "CSS selector"} - Get text content of element

WAITING:
- {"action": "wait", "selector": "CSS selector", "timeout": 5000} - Wait for element to appear
- {"action": "wait_hidden", "selector": "CSS selector", "timeout": 5000} - Wait for element to disappear
- {"action": "sleep", "ms": 1000} - Wait for specified milliseconds

UTILITIES:
- {"action": "screenshot", "filename": "screenshot.png"} - Save screenshot to file
- {"action": "focus", "selector": "CSS selector"} - Focus on an element

COMPLETION:
- {"action": "done", "result": "summary of what was accomplished"}

Rules:
1. Analyze the screenshot carefully before acting
2. Use specific CSS selectors (prefer IDs, then classes, then tag names)
3. Take one action at a time
4. Say "done" when the task is complete or impossible
5. Respond ONLY with valid JSON, no other text
6. For form submission, try clicking submit button first; use press Enter as fallback
7. When hovering reveals a menu, follow up with a click on the revealed item
"""


def execute_action(page: Any, action: dict, screenshot_dir: str = None, timeout: int = 5000) -> str:
    """
    Execute a browser action.

    Args:
        page: Playwright page object
        action: Action dictionary from Claude
        screenshot_dir: Directory to save screenshots
        timeout: Default timeout for actions in ms

    Returns:
        Result message string
    """
    action_type = action.get("action")

    try:
        # NAVIGATION
        if action_type == "goto":
            page.goto(action["url"], wait_until="domcontentloaded")
            return f"Navigated to: {action['url']}"

        elif action_type == "back":
            page.go_back()
            return "Navigated back"

        elif action_type == "forward":
            page.go_forward()
            return "Navigated forward"

        elif action_type == "refresh":
            page.reload()
            return "Page refreshed"

        # MOUSE ACTIONS
        elif action_type == "click":
            page.click(action["selector"], timeout=timeout)
            return f"Clicked: {action['selector']}"

        elif action_type == "double_click":
            page.dblclick(action["selector"], timeout=timeout)
            return f"Double-clicked: {action['selector']}"

        elif action_type == "right_click":
            page.click(action["selector"], button="right", timeout=timeout)
            return f"Right-clicked: {action['selector']}"

        elif action_type == "hover":
            page.hover(action["selector"], timeout=timeout)
            return f"Hovering over: {action['selector']}"

        # FORM INPUTS
        elif action_type == "fill":
            page.fill(action["selector"], action["value"])
            return f"Filled {action['selector']} with: {action['value']}"

        elif action_type == "clear":
            page.fill(action["selector"], "")
            return f"Cleared: {action['selector']}"

        elif action_type == "select":
            try:
                page.select_option(action["selector"], value=action["value"])
            except Exception:
                page.select_option(action["selector"], label=action["value"])
            return f"Selected '{action['value']}' in {action['selector']}"

        elif action_type == "check":
            page.check(action["selector"])
            return f"Checked: {action['selector']}"

        elif action_type == "uncheck":
            page.uncheck(action["selector"])
            return f"Unchecked: {action['selector']}"

        elif action_type == "upload":
            page.set_input_files(action["selector"], action["filepath"])
            return f"Uploaded {action['filepath']} to {action['selector']}"

        # KEYBOARD
        elif action_type == "press":
            page.keyboard.press(action["key"])
            return f"Pressed key: {action['key']}"

        elif action_type == "type":
            page.keyboard.type(action["text"])
            return f"Typed: {action['text']}"

        # SCROLLING
        elif action_type == "scroll":
            direction = action.get("direction", "down")
            amount = action.get("amount", 500)
            scroll_amount = amount if direction == "down" else -amount
            page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            return f"Scrolled {direction} by {amount}px"

        elif action_type == "scroll_to":
            page.locator(action["selector"]).scroll_into_view_if_needed()
            return f"Scrolled to: {action['selector']}"

        # DATA EXTRACTION
        elif action_type == "extract":
            elements = page.locator(action["selector"]).all()
            texts = [el.text_content() for el in elements[:10]]
            return f"Extracted ({action.get('description', 'data')}): {texts}"

        elif action_type == "get_attribute":
            value = page.get_attribute(action["selector"], action["attribute"])
            return f"Attribute {action['attribute']} of {action['selector']}: {value}"

        elif action_type == "get_text":
            text = page.locator(action["selector"]).first.text_content()
            return f"Text content: {text}"

        # WAITING
        elif action_type == "wait":
            wait_timeout = action.get("timeout", timeout)
            page.wait_for_selector(action["selector"], timeout=wait_timeout)
            return f"Element appeared: {action['selector']}"

        elif action_type == "wait_hidden":
            wait_timeout = action.get("timeout", timeout)
            page.wait_for_selector(action["selector"], state="hidden", timeout=wait_timeout)
            return f"Element hidden: {action['selector']}"

        elif action_type == "sleep":
            page.wait_for_timeout(action.get("ms", 1000))
            return f"Waited {action.get('ms', 1000)}ms"

        # UTILITIES
        elif action_type == "screenshot":
            filename = action.get("filename", "screenshot.png")
            if screenshot_dir:
                filepath = os.path.join(screenshot_dir, filename)
            else:
                filepath = filename
            page.screenshot(path=filepath)
            return f"Screenshot saved to: {filepath}"

        elif action_type == "focus":
            page.focus(action["selector"])
            return f"Focused: {action['selector']}"

        # COMPLETION
        elif action_type == "done":
            return f"DONE: {action.get('result', 'Task completed')}"

        else:
            return f"Unknown action: {action_type}"

    except Exception as e:
        return f"Error executing {action_type}: {str(e)}"


def get_page_context(page: Any) -> dict:
    """
    Extract useful context from the page for Claude.

    Args:
        page: Playwright page object

    Returns:
        Dictionary with page context information
    """
    return page.evaluate("""() => {
        return {
            url: window.location.href,
            title: document.title,
            buttons: Array.from(document.querySelectorAll('button, [role="button"]'))
                .slice(0, 10).map(b => ({
                    text: b.textContent?.trim(),
                    id: b.id || null,
                    class: b.className || null
                })).filter(b => b.text),
            links: Array.from(document.querySelectorAll('a'))
                .slice(0, 10).map(a => ({
                    text: a.textContent?.trim(),
                    href: a.href,
                    id: a.id || null
                })).filter(l => l.text),
            inputs: Array.from(document.querySelectorAll('input, textarea'))
                .slice(0, 10).map(i => ({
                    type: i.type,
                    name: i.name || null,
                    id: i.id || null,
                    placeholder: i.placeholder || null,
                    value: i.type !== 'password' ? i.value : '[hidden]'
                })),
            selects: Array.from(document.querySelectorAll('select'))
                .slice(0, 10).map(s => ({
                    name: s.name || null,
                    id: s.id || null,
                    options: Array.from(s.options).slice(0, 5).map(o => o.text),
                    selected: s.options[s.selectedIndex]?.text
                })),
            checkboxes: Array.from(document.querySelectorAll('input[type="checkbox"]'))
                .slice(0, 10).map(c => ({
                    name: c.name || null,
                    id: c.id || null,
                    checked: c.checked,
                    label: document.querySelector(`label[for="${c.id}"]`)?.textContent?.trim()
                })),
            forms: Array.from(document.querySelectorAll('form'))
                .slice(0, 5).map(f => ({
                    id: f.id || null,
                    action: f.action,
                    method: f.method
                }))
        }
    }""")
