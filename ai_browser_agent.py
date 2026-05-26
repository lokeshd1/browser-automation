# ai_browser_agent.py
"""
AI Browser Agent - Uses Claude to navigate and interact with websites.
Requires: pip install playwright anthropic httpx
Run: python ai_browser_agent.py
"""

import anthropic
import base64
import httpx
import json
import os
import re
from playwright.sync_api import sync_playwright

# Configuration - supports both standard API and enterprise Bedrock endpoints
BASE_URL = os.environ.get("ANTHROPIC_BEDROCK_BASE_URL")
AUTH_TOKEN = os.environ.get("ANTHROPIC_AUTH_TOKEN")
API_KEY = os.environ.get("ANTHROPIC_API_KEY")
USE_ENTERPRISE = bool(BASE_URL and AUTH_TOKEN)

if USE_ENTERPRISE:
    MODEL = os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL", "claude-sonnet-4-20250514")
    print(f"Using enterprise endpoint: {BASE_URL}")
elif API_KEY:
    MODEL = "claude-sonnet-4-20250514"
    client = anthropic.Anthropic()
    print("Using standard Anthropic API")
else:
    raise ValueError("No API credentials found. Set ANTHROPIC_API_KEY or ANTHROPIC_BEDROCK_BASE_URL + ANTHROPIC_AUTH_TOKEN")

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


def screenshot_to_base64(page) -> str:
    """Capture screenshot and convert to base64."""
    screenshot_bytes = page.screenshot()
    return base64.standard_b64encode(screenshot_bytes).decode("utf-8")


def get_page_context(page) -> dict:
    """Extract useful context from the page."""
    return page.evaluate("""() => {
        return {
            url: window.location.href,
            title: document.title,
            // Get clickable elements
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


def ask_claude(task: str, screenshot_b64: str, page_context: dict, history: list) -> dict:
    """Ask Claude what action to take next."""

    messages = history + [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"Task: {task}\n\nCurrent page context:\n{json.dumps(page_context, indent=2)}\n\nWhat action should I take next?"
                },
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": screenshot_b64
                    }
                }
            ]
        }
    ]

    if USE_ENTERPRISE:
        # Use httpx directly for enterprise endpoint
        response = httpx.post(
            f"{BASE_URL}/messages",
            headers={
                "Authorization": f"Bearer {AUTH_TOKEN}",
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": MODEL,
                "max_tokens": 1024,
                "system": SYSTEM_PROMPT,
                "messages": messages,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        response_text = data["content"][0]["text"]
    else:
        # Use anthropic library for standard API
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=messages
        )
        response_text = response.content[0].text

    # Parse JSON from response
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        # Try to extract JSON if there's extra text
        match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {"action": "done", "result": f"Failed to parse response: {response_text}"}


def execute_action(page, action: dict, screenshot_dir: str = None) -> str:
    """Execute the action Claude decided on."""
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
            page.click(action["selector"], timeout=5000)
            return f"Clicked: {action['selector']}"

        elif action_type == "double_click":
            page.dblclick(action["selector"], timeout=5000)
            return f"Double-clicked: {action['selector']}"

        elif action_type == "right_click":
            page.click(action["selector"], button="right", timeout=5000)
            return f"Right-clicked: {action['selector']}"

        elif action_type == "hover":
            page.hover(action["selector"], timeout=5000)
            return f"Hovering over: {action['selector']}"

        # FORM INPUTS
        elif action_type == "fill":
            page.fill(action["selector"], action["value"])
            return f"Filled {action['selector']} with: {action['value']}"

        elif action_type == "clear":
            page.fill(action["selector"], "")
            return f"Cleared: {action['selector']}"

        elif action_type == "select":
            # Try by value first, then by label
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
            timeout = action.get("timeout", 5000)
            page.wait_for_selector(action["selector"], timeout=timeout)
            return f"Element appeared: {action['selector']}"

        elif action_type == "wait_hidden":
            timeout = action.get("timeout", 5000)
            page.wait_for_selector(action["selector"], state="hidden", timeout=timeout)
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


def run_agent(
    task: str,
    start_url: str = None,
    max_steps: int = 10,
    headless: bool = False,
    screenshot_dir: str = None,
    viewport: dict = None
):
    """
    Run the AI browser agent.

    Args:
        task: Natural language description of what to accomplish
        start_url: Optional URL to navigate to first
        max_steps: Maximum number of actions before stopping (default 10)
        headless: Run browser without GUI (default False)
        screenshot_dir: Directory to save screenshots (default current dir)
        viewport: Browser viewport size (default {"width": 1280, "height": 800})

    Returns:
        dict with 'success', 'result', and 'steps' taken
    """
    if viewport is None:
        viewport = {"width": 1280, "height": 800}

    if screenshot_dir and not os.path.exists(screenshot_dir):
        os.makedirs(screenshot_dir)

    print(f"Starting agent with task: {task}\n")

    result_data = {"success": False, "result": None, "steps": []}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(viewport=viewport)

        if start_url:
            page.goto(start_url, wait_until="domcontentloaded")

        history = []

        try:
            for step in range(max_steps):
                print(f"--- Step {step + 1} ---")

                # Give page time to settle
                try:
                    page.wait_for_timeout(1000)
                except Exception:
                    # Page might have navigated, give it more time
                    pass

                # Check if page is still valid
                try:
                    _ = page.url
                except Exception as e:
                    print(f"Page closed unexpectedly: {e}")
                    break

                # Capture current state
                screenshot_b64 = screenshot_to_base64(page)
                page_context = get_page_context(page)

                print(f"URL: {page_context['url']}")

                # Ask Claude what to do
                action = ask_claude(task, screenshot_b64, page_context, history)
                print(f"Claude decided: {json.dumps(action)}")

                # Execute the action
                result = execute_action(page, action, screenshot_dir)
                print(f"Result: {result}\n")

                # Track step
                result_data["steps"].append({"action": action, "result": result})

                # Update history for context
                history.append({
                    "role": "assistant",
                    "content": json.dumps(action)
                })
                history.append({
                    "role": "user",
                    "content": f"Action result: {result}"
                })

                # Check if done
                if action.get("action") == "done":
                    result_data["success"] = True
                    result_data["result"] = action.get("result")
                    print(f"Agent completed: {action.get('result')}")
                    break

        except Exception as e:
            print(f"Agent error: {e}")
            result_data["error"] = str(e)
        finally:
            try:
                browser.close()
            except Exception:
                pass

    return result_data


# Example usage
if __name__ == "__main__":
    import sys

    # Check for command line arguments
    if len(sys.argv) > 1:
        # Run with custom task from command line
        task = " ".join(sys.argv[1:])
        run_agent(task=task)
    else:
        # Default demo: Fill out a sample form
        run_agent(
            task="""Fill out the contact form with:
            - Name: John Doe
            - Email: john@example.com
            - Subject: select 'General Inquiry'
            - Message: Hello, this is a test message from the browser agent.
            Then submit the form and report the result.""",
            start_url="https://www.w3schools.com/html/html_forms.asp",
            screenshot_dir="/Users/lokesh.dhakar/Documents/browser-automation/screenshots"
        )


# Additional example tasks you can try:
#
# 1. Navigate and extract:
#    run_agent(
#        task="Go to Hacker News, click on the top story, and summarize what the page is about",
#        start_url="https://news.ycombinator.com"
#    )
#
# 2. Form with dropdown and checkbox:
#    run_agent(
#        task="Select 'Option 2' from the dropdown, check the 'I agree' checkbox, then submit",
#        start_url="https://example-form-site.com"
#    )
#
# 3. Multi-step navigation:
#    run_agent(
#        task="Search for 'Python tutorial', click the first result, then take a screenshot",
#        start_url="https://duckduckgo.com"
#    )
#
# 4. Keyboard shortcuts:
#    run_agent(
#        task="Press Ctrl+F to open find, search for 'example', then press Escape to close",
#        start_url="https://en.wikipedia.org/wiki/Python_(programming_language)"
#    )
