"""
Utility modules for browser agent reliability and error handling.
"""

from .reliability import (
    RetryConfig,
    is_transient_error,
    is_fatal_error,
    retry_with_backoff,
    retry_action,
    calculate_delay,
)

from .waiting import (
    WaitConfig,
    wait_for_page_stable,
    wait_for_dom_stability,
    smart_wait_after_action,
    wait_for_element_stable,
)

from .selectors import (
    generate_fallback_selectors,
    try_with_fallback_selectors,
    find_best_selector,
)

__all__ = [
    # Reliability
    "RetryConfig",
    "is_transient_error",
    "is_fatal_error",
    "retry_with_backoff",
    "retry_action",
    "calculate_delay",
    # Waiting
    "WaitConfig",
    "wait_for_page_stable",
    "wait_for_dom_stability",
    "smart_wait_after_action",
    "wait_for_element_stable",
    # Selectors
    "generate_fallback_selectors",
    "try_with_fallback_selectors",
    "find_best_selector",
]
