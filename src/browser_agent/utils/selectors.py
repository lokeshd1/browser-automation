"""
Fallback selector strategies for browser actions.
"""

import re
from typing import Any, Callable, List, Optional, TypeVar


T = TypeVar("T")


def generate_fallback_selectors(selector: str, page_context: Optional[dict] = None) -> List[str]:
    """
    Generate fallback selectors from the original selector and page context.

    Priority order:
    1. ID selector
    2. data-testid selector
    3. aria-label selector
    4. Class selector
    5. Text content selector

    Args:
        selector: The original CSS selector
        page_context: Optional page context with element information

    Returns:
        List of selectors to try, starting with the original
    """
    selectors = [selector]

    if not page_context:
        return selectors

    # Extract identifier from selector for matching
    identifier = _extract_identifier(selector)
    if not identifier:
        return selectors

    identifier_lower = identifier.lower()

    # Search in buttons
    for btn in page_context.get("buttons", []):
        fallbacks = _generate_element_fallbacks(btn, identifier_lower, "button")
        selectors.extend(fallbacks)

    # Search in links
    for link in page_context.get("links", []):
        fallbacks = _generate_element_fallbacks(link, identifier_lower, "a")
        selectors.extend(fallbacks)

    # Search in inputs
    for inp in page_context.get("inputs", []):
        fallbacks = _generate_element_fallbacks(inp, identifier_lower, "input")
        selectors.extend(fallbacks)

    # Search in selects
    for sel in page_context.get("selects", []):
        fallbacks = _generate_element_fallbacks(sel, identifier_lower, "select")
        selectors.extend(fallbacks)

    # Deduplicate while preserving order
    seen = set()
    unique_selectors = []
    for s in selectors:
        if s not in seen:
            seen.add(s)
            unique_selectors.append(s)

    return unique_selectors


def _extract_identifier(selector: str) -> Optional[str]:
    """Extract the main identifier from a selector for matching."""
    # Try to extract ID
    id_match = re.search(r"#([\w-]+)", selector)
    if id_match:
        return id_match.group(1)

    # Try to extract class
    class_match = re.search(r"\.([\w-]+)", selector)
    if class_match:
        return class_match.group(1)

    # Try to extract text content
    text_match = re.search(r':has-text\(["\']?([^"\']+)["\']?\)', selector)
    if text_match:
        return text_match.group(1)

    # Try data attribute
    data_match = re.search(r'\[data-[\w-]+=["\']?([^"\']+)["\']?\]', selector)
    if data_match:
        return data_match.group(1)

    return None


def _generate_element_fallbacks(
    element: dict, identifier: str, tag: str
) -> List[str]:
    """Generate fallback selectors for a matched element."""
    fallbacks = []

    # Check if element matches the identifier
    matches = False

    # Match by ID
    if element.get("id") and identifier in element["id"].lower():
        matches = True

    # Match by text content
    text = element.get("text", "")
    if text and identifier in text.lower():
        matches = True

    # Match by class
    classes = element.get("class", "")
    if classes and identifier in classes.lower():
        matches = True

    # Match by aria-label
    aria = element.get("aria", {})
    if aria and aria.get("label") and identifier in aria["label"].lower():
        matches = True

    # Match by label (for inputs)
    if element.get("label") and identifier in element["label"].lower():
        matches = True

    if not matches:
        return fallbacks

    # Generate fallback selectors in priority order

    # 1. ID selector (highest priority)
    if element.get("id"):
        fallbacks.append(f"#{element['id']}")

    # 2. data-testid or similar data attributes
    data = element.get("data", {})
    for attr, value in (data or {}).items():
        fallbacks.append(f'[{attr}="{value}"]')

    # 3. aria-label selector
    if aria and aria.get("label"):
        fallbacks.append(f'[aria-label="{aria["label"]}"]')

    # 4. Role-based selector
    if aria and aria.get("role"):
        if element.get("id"):
            fallbacks.append(f'[role="{aria["role"]}"]#{element["id"]}')
        elif text:
            fallbacks.append(f'[role="{aria["role"]}"]:has-text("{text}")')

    # 5. Class selector (with tag for specificity)
    if classes:
        primary_class = classes.split()[0]
        fallbacks.append(f"{tag}.{primary_class}")

    # 6. Text content selector (lowest priority)
    if text and len(text) < 50:
        fallbacks.append(f'{tag}:has-text("{text}")')

    # 7. For inputs, try name or placeholder
    if tag == "input":
        if element.get("name"):
            fallbacks.append(f'input[name="{element["name"]}"]')
        if element.get("placeholder"):
            fallbacks.append(f'input[placeholder="{element["placeholder"]}"]')

    return fallbacks


def try_with_fallback_selectors(
    page: Any,
    action_func: Callable[[str], T],
    selector: str,
    page_context: Optional[dict] = None,
    timeout: int = 5000,
) -> T:
    """
    Try an action with fallback selectors if the primary fails.

    Args:
        page: Playwright page object
        action_func: Function that takes selector and performs action
        selector: Primary CSS selector
        page_context: Optional page context for generating fallbacks
        timeout: Timeout for each selector attempt in ms

    Returns:
        Result from the action function

    Raises:
        Last exception if all selectors fail
    """
    selectors = generate_fallback_selectors(selector, page_context)

    last_error: Optional[Exception] = None

    for sel in selectors:
        try:
            # First check if element exists (quick check)
            locator = page.locator(sel)
            if locator.count() > 0:
                return action_func(sel)
        except Exception as e:
            last_error = e
            continue

    # If no selector worked, raise the last error
    if last_error:
        raise last_error

    raise Exception(f"No matching element found for selector: {selector}")


def find_best_selector(page: Any, selector: str, page_context: Optional[dict] = None) -> Optional[str]:
    """
    Find the best working selector from fallback options.

    Args:
        page: Playwright page object
        selector: Primary CSS selector
        page_context: Optional page context for generating fallbacks

    Returns:
        The first working selector, or None if none work
    """
    selectors = generate_fallback_selectors(selector, page_context)

    for sel in selectors:
        try:
            locator = page.locator(sel)
            if locator.count() > 0:
                # Verify it's visible
                if locator.first.is_visible():
                    return sel
        except Exception:
            continue

    return None
