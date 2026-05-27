"""
Main browser agent implementation.
"""

import base64
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from playwright.sync_api import sync_playwright

from .actions import (
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_NO_VISION,
    execute_action,
    execute_action_with_retry,
    get_page_context,
)
from .config import Config
from .providers import get_provider, BaseLLMProvider
from .session import SessionConfig, SessionManager
from .utils import (
    RetryConfig,
    WaitConfig,
    smart_wait_after_action,
    retry_action,
    is_transient_error,
)


@dataclass
class AgentResult:
    """Result from running the browser agent."""

    success: bool
    result: Optional[str]
    steps: list = field(default_factory=list)
    error: Optional[str] = None


class BrowserAgent:
    """AI-powered browser automation agent."""

    def __init__(
        self,
        config: Optional[Config] = None,
        provider: Optional[BaseLLMProvider] = None,
    ):
        """
        Initialize the browser agent.

        Args:
            config: Configuration object. If None, loads from environment.
            provider: LLM provider instance. If None, creates from config.
        """
        self.config = config or Config.from_env()
        self.config.validate()

        # Initialize provider
        if provider:
            self._provider = provider
        else:
            self._provider = get_provider(
                self.config.provider,
                **self.config.get_provider_kwargs()
            )

        # Initialize session manager if session features enabled
        self._session_manager = None
        if self.config.save_session or self.config.load_session:
            session_config = SessionConfig(
                session_file=self.config.session_file or ".browser_agent_session.json",
                session_ttl_hours=self.config.session_ttl_hours,
            )
            self._session_manager = SessionManager(session_config)

        # Initialize retry config
        self._retry_config = RetryConfig(
            max_retries=self.config.action_max_retries,
            base_delay_ms=self.config.retry_base_delay_ms,
        )

        # Initialize wait config
        self._wait_config = WaitConfig(
            networkidle_timeout_ms=self.config.smart_wait_timeout_ms,
            dom_stability_ms=self.config.dom_stability_ms,
        )

        # Initialize LLM retry config (for API resilience)
        self._llm_retry_config = RetryConfig(
            max_retries=self.config.llm_max_retries,
            base_delay_ms=1000,  # Longer delay for API retries
            max_delay_ms=10000,
        )

        if self.config.verbose:
            print(f"Using provider: {self._provider.name} (model: {self.config.model})")
            if self.config.use_vision:
                if not self._provider.supports_vision:
                    print("Warning: This model doesn't support vision. Results may be limited.")
            else:
                print("Vision disabled: using DOM context only")
            if self._session_manager:
                if self.config.load_session:
                    print("Session loading enabled")
                if self.config.save_session:
                    print("Session saving enabled")

    def _screenshot_to_base64(self, page: Any) -> str:
        """Capture screenshot and convert to base64."""
        screenshot_bytes = page.screenshot()
        return base64.standard_b64encode(screenshot_bytes).decode("utf-8")

    def _ask_llm(
        self, task: str, screenshot_b64: str, page_context: dict, history: list
    ) -> dict:
        """Ask the LLM what action to take next with retry logic for API resilience."""
        # Build context message
        context_msg = f"Task: {task}\n\nCurrent page context:\n{json.dumps(page_context, indent=2)}"

        # Add context to history
        messages = history + [{"role": "user", "content": context_msg}]

        # Choose system prompt based on vision mode
        system_prompt = SYSTEM_PROMPT if self.config.use_vision else SYSTEM_PROMPT_NO_VISION

        def make_llm_request() -> str:
            return self._provider.ask(
                system_prompt=system_prompt,
                messages=messages,
                screenshot_b64=screenshot_b64,
                max_tokens=1024,
                use_vision=self.config.use_vision,
            )

        def on_llm_retry(attempt: int, error: Exception) -> None:
            if self.config.verbose:
                print(f"  LLM request failed (attempt {attempt}): {error}")

        # Retry LLM requests for resilience against 429, 503, etc.
        try:
            response_text = retry_action(
                make_llm_request,
                self._llm_retry_config,
                on_llm_retry,
            )
        except Exception as e:
            # If all retries fail, return a done action with error
            return {
                "action": "done",
                "result": f"LLM request failed after retries: {str(e)}",
            }

        # Parse JSON from response
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON if there's extra text
            match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if match:
                return json.loads(match.group())
            return {
                "action": "done",
                "result": f"Failed to parse response: {response_text}",
            }

    def run(
        self,
        task: str,
        start_url: Optional[str] = None,
        max_steps: Optional[int] = None,
    ) -> AgentResult:
        """
        Run the browser agent.

        Args:
            task: Natural language description of what to accomplish
            start_url: Optional URL to navigate to first
            max_steps: Override max steps from config

        Returns:
            AgentResult with success status, result, and steps taken
        """
        max_steps = max_steps or self.config.max_steps

        if self.config.screenshot_dir and not os.path.exists(self.config.screenshot_dir):
            os.makedirs(self.config.screenshot_dir)

        if self.config.verbose:
            print(f"Starting agent with task: {task}\n")

        result_data = AgentResult(success=False, result=None, steps=[])

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.config.headless)

            # Create context with session recovery if enabled
            if self._session_manager and self.config.load_session:
                context = self._session_manager.create_context_with_session(
                    browser,
                    self.config.viewport,
                    self.config.session_file,
                )
                if self.config.verbose:
                    session_info = self._session_manager.get_session_info(self.config.session_file)
                    if session_info:
                        print(f"Restored session: {session_info['cookie_count']} cookies, {session_info['remaining_hours']:.1f}h remaining")
            else:
                context = browser.new_context(viewport=self.config.viewport)

            page = context.new_page()

            if start_url:
                page.goto(start_url, wait_until="load")
                # Use smart wait after initial navigation
                if self.config.smart_wait_enabled:
                    smart_wait_after_action(page, "goto", self._wait_config)

            history = []

            try:
                for step in range(max_steps):
                    if self.config.verbose:
                        print(f"--- Step {step + 1} ---")

                    # Use smart wait or fixed delay based on config
                    if not self.config.smart_wait_enabled:
                        try:
                            page.wait_for_timeout(self.config.step_delay_ms)
                        except Exception:
                            pass

                    # Check if page is still valid
                    try:
                        _ = page.url
                    except Exception as e:
                        if self.config.verbose:
                            print(f"Page closed unexpectedly: {e}")
                        break

                    # Capture current state
                    # Skip screenshot capture if vision is disabled (performance optimization)
                    screenshot_b64 = self._screenshot_to_base64(page) if self.config.use_vision else ""
                    page_context = get_page_context(page)

                    if self.config.verbose:
                        print(f"URL: {page_context['url']}")

                    # Ask LLM what to do
                    action = self._ask_llm(task, screenshot_b64, page_context, history)

                    if self.config.verbose:
                        print(f"LLM decided: {json.dumps(action)}")

                    # Retry callback for verbose logging
                    def on_action_retry(attempt: int, error: Exception) -> None:
                        if self.config.verbose:
                            print(f"  Retrying action (attempt {attempt}): {error}")

                    # Execute the action with retry and fallback selectors
                    result = execute_action_with_retry(
                        page,
                        action,
                        self.config.screenshot_dir,
                        self.config.action_timeout_ms,
                        page_context,
                        self._retry_config,
                        on_action_retry,
                    )

                    # Smart wait after action if enabled
                    action_type = action.get("action", "")
                    if self.config.smart_wait_enabled:
                        smart_wait_after_action(page, action_type, self._wait_config)

                    if self.config.verbose:
                        print(f"Result: {result}\n")

                    # Track step
                    result_data.steps.append({"action": action, "result": result})

                    # Update history for context
                    history.append({"role": "assistant", "content": json.dumps(action)})
                    history.append({"role": "user", "content": f"Action result: {result}"})

                    # Check if done
                    if action.get("action") == "done":
                        result_data.success = True
                        result_data.result = action.get("result")
                        if self.config.verbose:
                            print(f"Agent completed: {action.get('result')}")
                        break

            except Exception as e:
                if self.config.verbose:
                    print(f"Agent error: {e}")
                result_data.error = str(e)
            finally:
                # Save session if enabled and task succeeded
                if self._session_manager and self.config.save_session and result_data.success:
                    if self._session_manager.save_session(context, self.config.session_file):
                        if self.config.verbose:
                            print("Session saved successfully")

                try:
                    context.close()
                    browser.close()
                except Exception:
                    pass

        return result_data


def run_agent(
    task: str,
    start_url: Optional[str] = None,
    max_steps: int = 10,
    headless: bool = False,
    screenshot_dir: Optional[str] = None,
    viewport: Optional[dict] = None,
    verbose: bool = True,
    provider: str = None,
    model: str = None,
    api_key: str = None,
    use_vision: bool = True,
    max_retries: int = 3,
    smart_wait: bool = True,
    save_session: bool = False,
    load_session: bool = False,
    session_file: str = None,
) -> dict:
    """
    Convenience function to run the browser agent.

    Args:
        task: Natural language description of what to accomplish
        start_url: Optional URL to navigate to first
        max_steps: Maximum number of actions before stopping
        headless: Run browser without GUI
        screenshot_dir: Directory to save screenshots
        viewport: Browser viewport size {"width": int, "height": int}
        verbose: Print progress to stdout
        provider: LLM provider ('anthropic', 'openai', 'ollama')
        model: Model name (provider-specific)
        api_key: API key (overrides environment)
        use_vision: Whether to use vision mode (default: True). Set to False for DOM-only mode.
        max_retries: Maximum retry attempts for failed actions (default: 3)
        smart_wait: Use adaptive waiting instead of fixed delay (default: True)
        save_session: Save browser session on successful completion (default: False)
        load_session: Load browser session from file if available (default: False)
        session_file: Path to session file (default: .browser_agent_session.json)

    Returns:
        Dictionary with 'success', 'result', 'steps', and optionally 'error'
    """
    config = Config.from_env(provider=provider)
    config.max_steps = max_steps
    config.headless = headless
    config.screenshot_dir = screenshot_dir
    config.verbose = verbose
    config.use_vision = use_vision

    # Reliability settings
    config.action_max_retries = max_retries
    config.smart_wait_enabled = smart_wait

    # Session settings
    config.save_session = save_session
    config.load_session = load_session
    if session_file:
        config.session_file = session_file

    if model:
        config.model = model
    if api_key:
        config.api_key = api_key

    if viewport:
        config.viewport_width = viewport.get("width", 1280)
        config.viewport_height = viewport.get("height", 800)

    agent = BrowserAgent(config)
    result = agent.run(task, start_url, max_steps)

    return {
        "success": result.success,
        "result": result.result,
        "steps": result.steps,
        "error": result.error,
    }
