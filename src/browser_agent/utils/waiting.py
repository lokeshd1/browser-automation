"""
Smart waiting utilities for browser actions.
"""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class WaitConfig:
    """Configuration for smart waiting behavior."""

    networkidle_timeout_ms: int = 10000
    dom_stability_ms: int = 300
    fallback_delay_ms: int = 1000
    min_wait_ms: int = 100


# Actions that typically trigger network activity
NETWORK_ACTIONS = {"goto", "click", "submit", "fill", "select", "upload"}

# Actions that may trigger DOM changes
DOM_CHANGE_ACTIONS = {"click", "fill", "select", "check", "uncheck", "press", "type", "hover"}

# Actions that don't need waiting
NO_WAIT_ACTIONS = {"done", "screenshot", "sleep", "get_text", "get_attribute", "extract"}


def wait_for_page_stable(page: Any, config: Optional[WaitConfig] = None) -> bool:
    """
    Wait for page to reach a stable state (network idle).

    Falls back to load state if networkidle times out.

    Args:
        page: Playwright page object
        config: Wait configuration

    Returns:
        True if page became stable, False if fell back to timeout
    """
    if config is None:
        config = WaitConfig()

    try:
        # First try to wait for network idle
        page.wait_for_load_state("networkidle", timeout=config.networkidle_timeout_ms)
        return True
    except Exception:
        pass

    try:
        # Fall back to waiting for load state
        page.wait_for_load_state("load", timeout=config.fallback_delay_ms)
        return True
    except Exception:
        pass

    return False


def wait_for_dom_stability(page: Any, config: Optional[WaitConfig] = None) -> bool:
    """
    Wait for DOM to stop changing using MutationObserver.

    Detects when the DOM has been stable for a specified duration.

    Args:
        page: Playwright page object
        config: Wait configuration

    Returns:
        True if DOM became stable, False on timeout
    """
    if config is None:
        config = WaitConfig()

    stability_ms = config.dom_stability_ms
    timeout_ms = config.networkidle_timeout_ms

    # JavaScript to wait for DOM stability
    js_code = f"""
    () => new Promise((resolve) => {{
        let timeout;
        let resolved = false;
        const stabilityPeriod = {stability_ms};
        const maxTimeout = {timeout_ms};

        const resetTimer = () => {{
            if (resolved) return;
            clearTimeout(timeout);
            timeout = setTimeout(() => {{
                resolved = true;
                observer.disconnect();
                resolve(true);
            }}, stabilityPeriod);
        }};

        const observer = new MutationObserver((mutations) => {{
            // Filter out non-significant mutations
            const significantMutations = mutations.filter(m => {{
                // Ignore attribute changes that don't affect layout
                if (m.type === 'attributes') {{
                    const attr = m.attributeName;
                    if (['class', 'style', 'data-', 'aria-'].some(p => attr.startsWith(p))) {{
                        return false;
                    }}
                }}
                return true;
            }});

            if (significantMutations.length > 0) {{
                resetTimer();
            }}
        }});

        observer.observe(document.body, {{
            childList: true,
            subtree: true,
            attributes: true,
            characterData: true
        }});

        // Start initial timer
        resetTimer();

        // Max timeout fallback
        setTimeout(() => {{
            if (!resolved) {{
                resolved = true;
                observer.disconnect();
                resolve(false);
            }}
        }}, maxTimeout);
    }})
    """

    try:
        return page.evaluate(js_code)
    except Exception:
        return False


def smart_wait_after_action(
    page: Any,
    action_type: str,
    config: Optional[WaitConfig] = None,
) -> None:
    """
    Smart wait after an action based on action type.

    Chooses appropriate waiting strategy based on the type of action performed.

    Args:
        page: Playwright page object
        action_type: The type of action that was just performed
        config: Wait configuration
    """
    if config is None:
        config = WaitConfig()

    # No waiting needed for certain actions
    if action_type in NO_WAIT_ACTIONS:
        return

    # Minimum wait to let browser start processing
    try:
        page.wait_for_timeout(config.min_wait_ms)
    except Exception:
        pass

    # Navigation actions: wait for network idle
    if action_type in {"goto", "back", "forward", "refresh"}:
        wait_for_page_stable(page, config)
        return

    # Network-triggering actions: wait for network then DOM stability
    if action_type in NETWORK_ACTIONS:
        wait_for_page_stable(page, config)
        wait_for_dom_stability(page, config)
        return

    # DOM-changing actions: wait for DOM stability
    if action_type in DOM_CHANGE_ACTIONS:
        wait_for_dom_stability(page, config)
        return

    # Default: short fixed delay for any other action
    try:
        page.wait_for_timeout(config.fallback_delay_ms)
    except Exception:
        pass


def wait_for_element_stable(
    page: Any,
    selector: str,
    config: Optional[WaitConfig] = None,
) -> bool:
    """
    Wait for a specific element to be stable (visible and non-animated).

    Args:
        page: Playwright page object
        selector: CSS selector for the element
        config: Wait configuration

    Returns:
        True if element became stable, False on timeout
    """
    if config is None:
        config = WaitConfig()

    try:
        # First wait for element to be visible
        page.wait_for_selector(selector, state="visible", timeout=config.networkidle_timeout_ms)

        # Then check if it's stable (not animating)
        js_code = f"""
        (selector) => new Promise((resolve) => {{
            const el = document.querySelector(selector);
            if (!el) {{
                resolve(false);
                return;
            }}

            let prevRect = el.getBoundingClientRect();
            let stableCount = 0;
            const checkStability = setInterval(() => {{
                const rect = el.getBoundingClientRect();
                if (
                    rect.top === prevRect.top &&
                    rect.left === prevRect.left &&
                    rect.width === prevRect.width &&
                    rect.height === prevRect.height
                ) {{
                    stableCount++;
                    if (stableCount >= 3) {{
                        clearInterval(checkStability);
                        resolve(true);
                    }}
                }} else {{
                    stableCount = 0;
                    prevRect = rect;
                }}
            }}, 100);

            // Timeout
            setTimeout(() => {{
                clearInterval(checkStability);
                resolve(stableCount >= 1);
            }}, {config.networkidle_timeout_ms});
        }})
        """
        return page.evaluate(js_code, selector)
    except Exception:
        return False
