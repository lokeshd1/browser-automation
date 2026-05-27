"""
Browser action definitions and execution.
"""

import os
from typing import Any, Callable, Optional

from .utils import (
    RetryConfig,
    is_transient_error,
    retry_action,
    try_with_fallback_selectors,
)

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


# System prompt for non-vision mode (DOM context only)
SYSTEM_PROMPT_NO_VISION = """You are a browser automation agent. You receive structured page context (DOM elements) and decide what action to take next.

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
1. Analyze the page_context structure carefully - it contains all interactive elements
2. Use specific CSS selectors (prefer IDs, then data attributes, then classes, then tag names)
3. Take one action at a time
4. Say "done" when the task is complete or impossible
5. Respond ONLY with valid JSON, no other text
6. For form submission, try clicking submit button first; use press Enter as fallback
7. When hovering reveals a menu, follow up with a click on the revealed item

Tips for building selectors from context:
- If element has 'id', use: #element-id
- If element has unique 'data-*' attribute, use: [data-testid="value"]
- If element has 'class', use: .class-name (combine multiple: .class1.class2)
- For buttons/links, combine tag with text: button:has-text("Submit"), a:has-text("Click here")
- For inputs, use: input[name="fieldname"], input[placeholder="Search..."]
- For navigation items, look at 'nav_items' section for menu structure
"""


# Actions that should not be retried
NO_RETRY_ACTIONS = {"done", "screenshot", "sleep"}

# Actions that use selectors (can benefit from fallback selectors)
SELECTOR_ACTIONS = {
    "click", "double_click", "right_click", "hover",
    "fill", "clear", "select", "check", "uncheck", "upload",
    "scroll_to", "extract", "get_attribute", "get_text",
    "wait", "wait_hidden", "focus"
}


def execute_action(
    page: Any,
    action: dict,
    screenshot_dir: str = None,
    timeout: int = 5000,
    page_context: Optional[dict] = None,
) -> str:
    """
    Execute a browser action.

    Args:
        page: Playwright page object
        action: Action dictionary from Claude
        screenshot_dir: Directory to save screenshots
        timeout: Default timeout for actions in ms
        page_context: Optional page context for fallback selector generation

    Returns:
        Result message string
    """
    action_type = action.get("action")

    try:
        # NAVIGATION
        if action_type == "goto":
            page.goto(action["url"], wait_until="load")
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
    Extract useful context from the page for the LLM.

    Args:
        page: Playwright page object

    Returns:
        Dictionary with page context information
    """
    return page.evaluate("""() => {
        const viewportHeight = window.innerHeight;
        const scrollY = window.scrollY;

        // Helper to check if element is above/below fold
        const getPosition = (el) => {
            const rect = el.getBoundingClientRect();
            if (rect.top < 0) return 'above';
            if (rect.top > viewportHeight) return 'below';
            return 'visible';
        };

        // Helper to get ARIA attributes
        const getAria = (el) => {
            const aria = {};
            if (el.getAttribute('aria-label')) aria.label = el.getAttribute('aria-label');
            if (el.getAttribute('aria-describedby')) {
                const desc = document.getElementById(el.getAttribute('aria-describedby'));
                if (desc) aria.description = desc.textContent?.trim();
            }
            if (el.getAttribute('role')) aria.role = el.getAttribute('role');
            if (el.getAttribute('aria-expanded')) aria.expanded = el.getAttribute('aria-expanded');
            if (el.getAttribute('aria-selected')) aria.selected = el.getAttribute('aria-selected');
            if (el.getAttribute('aria-disabled')) aria.disabled = el.getAttribute('aria-disabled');
            return Object.keys(aria).length > 0 ? aria : null;
        };

        // Helper to get useful data attributes
        const getDataAttrs = (el) => {
            const data = {};
            for (const attr of el.attributes) {
                if (attr.name.startsWith('data-') &&
                    ['data-testid', 'data-test', 'data-cy', 'data-id', 'data-action', 'data-value'].some(d => attr.name.startsWith(d.slice(0, -1)))) {
                    data[attr.name] = attr.value;
                }
            }
            return Object.keys(data).length > 0 ? data : null;
        };

        return {
            url: window.location.href,
            title: document.title,

            // Headings hierarchy for page structure understanding
            headings: Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6'))
                .slice(0, 15).map(h => ({
                    level: parseInt(h.tagName[1]),
                    text: h.textContent?.trim().slice(0, 100),
                    id: h.id || null
                })).filter(h => h.text),

            // Buttons with enhanced info
            buttons: Array.from(document.querySelectorAll('button, [role="button"], input[type="submit"], input[type="button"]'))
                .slice(0, 20).map(b => ({
                    text: b.textContent?.trim().slice(0, 50) || b.value || null,
                    id: b.id || null,
                    class: b.className?.split(' ').slice(0, 3).join(' ') || null,
                    type: b.type || null,
                    disabled: b.disabled || null,
                    position: getPosition(b),
                    aria: getAria(b),
                    data: getDataAttrs(b)
                })).filter(b => b.text || b.aria?.label),

            // Links with enhanced info
            links: Array.from(document.querySelectorAll('a[href]'))
                .slice(0, 20).map(a => ({
                    text: a.textContent?.trim().slice(0, 50),
                    href: a.href,
                    id: a.id || null,
                    class: a.className?.split(' ').slice(0, 3).join(' ') || null,
                    position: getPosition(a),
                    aria: getAria(a),
                    data: getDataAttrs(a)
                })).filter(l => l.text || l.aria?.label),

            // Form inputs with enhanced info
            inputs: Array.from(document.querySelectorAll('input:not([type="hidden"]), textarea'))
                .slice(0, 20).map(i => ({
                    type: i.type,
                    name: i.name || null,
                    id: i.id || null,
                    placeholder: i.placeholder || null,
                    value: i.type !== 'password' ? (i.value?.slice(0, 50) || null) : '[hidden]',
                    required: i.required || null,
                    disabled: i.disabled || null,
                    position: getPosition(i),
                    aria: getAria(i),
                    data: getDataAttrs(i),
                    label: i.id ? document.querySelector(`label[for="${i.id}"]`)?.textContent?.trim() : null
                })),

            // Select dropdowns
            selects: Array.from(document.querySelectorAll('select'))
                .slice(0, 15).map(s => ({
                    name: s.name || null,
                    id: s.id || null,
                    options: Array.from(s.options).slice(0, 8).map(o => ({ value: o.value, text: o.text })),
                    selected: s.options[s.selectedIndex]?.text,
                    disabled: s.disabled || null,
                    position: getPosition(s),
                    aria: getAria(s),
                    label: s.id ? document.querySelector(`label[for="${s.id}"]`)?.textContent?.trim() : null
                })),

            // Checkboxes and radios
            checkboxes: Array.from(document.querySelectorAll('input[type="checkbox"], input[type="radio"]'))
                .slice(0, 15).map(c => ({
                    type: c.type,
                    name: c.name || null,
                    id: c.id || null,
                    value: c.value || null,
                    checked: c.checked,
                    disabled: c.disabled || null,
                    label: c.id ? document.querySelector(`label[for="${c.id}"]`)?.textContent?.trim() :
                           c.closest('label')?.textContent?.trim()
                })),

            // Forms
            forms: Array.from(document.querySelectorAll('form'))
                .slice(0, 5).map(f => ({
                    id: f.id || null,
                    name: f.name || null,
                    action: f.action,
                    method: f.method
                })),

            // Navigation elements
            nav_items: Array.from(document.querySelectorAll('nav a, [role="navigation"] a, [role="menuitem"], [role="menu"] a'))
                .slice(0, 15).map(n => ({
                    text: n.textContent?.trim().slice(0, 30),
                    href: n.href || null,
                    aria: getAria(n)
                })).filter(n => n.text),

            // Images with alt text (helpful for understanding page content)
            images: Array.from(document.querySelectorAll('img[alt]'))
                .slice(0, 10).map(img => ({
                    alt: img.alt?.slice(0, 100),
                    id: img.id || null,
                    class: img.className?.split(' ').slice(0, 2).join(' ') || null
                })).filter(img => img.alt),

            // Main content area text (truncated)
            main_text: (() => {
                const main = document.querySelector('main, [role="main"], article, .content, #content');
                if (main) {
                    return main.textContent?.trim().slice(0, 500).replace(/\\s+/g, ' ');
                }
                return null;
            })(),

            // Page scroll info
            scroll: {
                position: scrollY,
                height: document.body.scrollHeight,
                viewport: viewportHeight,
                can_scroll_down: (scrollY + viewportHeight) < document.body.scrollHeight,
                can_scroll_up: scrollY > 0
            }
        }
    }""")


def execute_action_with_retry(
    page: Any,
    action: dict,
    screenshot_dir: str = None,
    timeout: int = 5000,
    page_context: Optional[dict] = None,
    retry_config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> str:
    """
    Execute a browser action with retry logic.

    Wraps execute_action with exponential backoff retry for transient errors.
    Skips retry for non-retryable actions like done, screenshot, and sleep.

    Args:
        page: Playwright page object
        action: Action dictionary from Claude
        screenshot_dir: Directory to save screenshots
        timeout: Default timeout for actions in ms
        page_context: Optional page context for fallback selector generation
        retry_config: Retry configuration (uses defaults if None)
        on_retry: Optional callback called on each retry with (attempt, exception)

    Returns:
        Result message string
    """
    action_type = action.get("action")

    # Skip retry for certain actions
    if action_type in NO_RETRY_ACTIONS:
        return execute_action(page, action, screenshot_dir, timeout, page_context)

    # For selector-based actions, try with fallback selectors first
    selector = action.get("selector")
    if action_type in SELECTOR_ACTIONS and selector and page_context:
        def try_action_with_selector(sel: str) -> str:
            modified_action = {**action, "selector": sel}
            return execute_action(page, modified_action, screenshot_dir, timeout, page_context)

        try:
            return try_with_fallback_selectors(
                page,
                try_action_with_selector,
                selector,
                page_context,
                timeout,
            )
        except Exception as e:
            # If fallback selectors also fail, try with retry logic
            if not is_transient_error(e):
                raise

    # Apply retry logic
    if retry_config is None:
        retry_config = RetryConfig()

    def do_action() -> str:
        return execute_action(page, action, screenshot_dir, timeout, page_context)

    return retry_action(do_action, retry_config, on_retry)
