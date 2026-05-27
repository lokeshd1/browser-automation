"""
Retry logic and error classification utilities for browser actions.
"""

import functools
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar

from playwright.sync_api import TimeoutError as PlaywrightTimeout


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay_ms: int = 500
    max_delay_ms: int = 5000
    exponential_base: float = 2.0


# Error messages that indicate transient/retryable failures
TRANSIENT_ERROR_PATTERNS = [
    "timeout",
    "waiting for",
    "navigation failed",
    "net::err_",
    "connection refused",
    "connection reset",
    "connection closed",
    "network error",
    "temporarily unavailable",
    "socket hang up",
    "econnreset",
    "econnrefused",
    "etimedout",
    "element is not visible",
    "element is not attached",
    "element was detached",
    "element is outside of the viewport",
    "intercept",  # Request interception issues
    "frame was detached",
    "target closed",
    "page crashed",
]

# Error messages that indicate non-retryable failures
FATAL_ERROR_PATTERNS = [
    "invalid selector",
    "selector syntax",
    "unsupported selector",
    "missing required",
    "unknown action",
    "invalid url",
    "protocol error",
    "illegal character",
    "unexpected token",
]


def is_transient_error(error: Exception) -> bool:
    """
    Check if an error is transient and worth retrying.

    Args:
        error: The exception to classify

    Returns:
        True if the error is likely transient and retrying may succeed
    """
    # Playwright timeout is always retryable
    if isinstance(error, PlaywrightTimeout):
        return True

    error_msg = str(error).lower()

    # Check for fatal patterns first (they take precedence)
    for pattern in FATAL_ERROR_PATTERNS:
        if pattern in error_msg:
            return False

    # Check for transient patterns
    for pattern in TRANSIENT_ERROR_PATTERNS:
        if pattern in error_msg:
            return True

    # Default: consider unknown errors as potentially transient for resilience
    return False


def is_fatal_error(error: Exception) -> bool:
    """
    Check if an error is fatal and should not be retried.

    Args:
        error: The exception to classify

    Returns:
        True if the error is fatal and retrying will not help
    """
    error_msg = str(error).lower()

    for pattern in FATAL_ERROR_PATTERNS:
        if pattern in error_msg:
            return True

    return False


def calculate_delay(attempt: int, config: RetryConfig) -> int:
    """
    Calculate delay for a given retry attempt using exponential backoff.

    Args:
        attempt: The current attempt number (0-indexed)
        config: Retry configuration

    Returns:
        Delay in milliseconds
    """
    delay = config.base_delay_ms * (config.exponential_base ** attempt)
    return min(int(delay), config.max_delay_ms)


T = TypeVar("T")


def retry_with_backoff(
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator that retries a function with exponential backoff.

    Args:
        config: Retry configuration (uses defaults if None)
        on_retry: Optional callback called on each retry with (attempt, exception)

    Returns:
        Decorated function that retries on transient errors

    Example:
        @retry_with_backoff(RetryConfig(max_retries=3))
        def flaky_operation():
            ...
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_error: Optional[Exception] = None

            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e

                    # Don't retry fatal errors
                    if is_fatal_error(e):
                        raise

                    # Don't retry if we've exhausted attempts
                    if attempt >= config.max_retries:
                        raise

                    # Don't retry non-transient errors
                    if not is_transient_error(e):
                        raise

                    # Calculate delay and wait
                    delay_ms = calculate_delay(attempt, config)

                    # Call retry callback if provided
                    if on_retry:
                        on_retry(attempt + 1, e)

                    # Wait before retry
                    time.sleep(delay_ms / 1000.0)

            # Should not reach here, but raise last error if we do
            if last_error:
                raise last_error
            raise RuntimeError("Retry loop exited unexpectedly")

        return wrapper

    return decorator


def retry_action(
    func: Callable[..., T],
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
    *args: Any,
    **kwargs: Any,
) -> T:
    """
    Execute a function with retry logic (non-decorator version).

    Args:
        func: Function to execute
        config: Retry configuration
        on_retry: Optional callback called on each retry
        *args: Arguments to pass to func
        **kwargs: Keyword arguments to pass to func

    Returns:
        Result from func

    Example:
        result = retry_action(page.click, config, None, selector, timeout=5000)
    """
    if config is None:
        config = RetryConfig()

    last_error: Optional[Exception] = None

    for attempt in range(config.max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e

            # Don't retry fatal errors
            if is_fatal_error(e):
                raise

            # Don't retry if we've exhausted attempts
            if attempt >= config.max_retries:
                raise

            # Don't retry non-transient errors
            if not is_transient_error(e):
                raise

            # Calculate delay and wait
            delay_ms = calculate_delay(attempt, config)

            # Call retry callback if provided
            if on_retry:
                on_retry(attempt + 1, e)

            # Wait before retry
            time.sleep(delay_ms / 1000.0)

    # Should not reach here
    if last_error:
        raise last_error
    raise RuntimeError("Retry loop exited unexpectedly")
