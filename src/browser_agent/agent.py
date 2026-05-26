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

from .actions import SYSTEM_PROMPT, SYSTEM_PROMPT_NO_VISION, execute_action, get_page_context
from .config import Config
from .providers import get_provider, BaseLLMProvider


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

        if self.config.verbose:
            print(f"Using provider: {self._provider.name} (model: {self.config.model})")
            if self.config.use_vision:
                if not self._provider.supports_vision:
                    print("Warning: This model doesn't support vision. Results may be limited.")
            else:
                print("Vision disabled: using DOM context only")

    def _screenshot_to_base64(self, page: Any) -> str:
        """Capture screenshot and convert to base64."""
        screenshot_bytes = page.screenshot()
        return base64.standard_b64encode(screenshot_bytes).decode("utf-8")

    def _ask_llm(
        self, task: str, screenshot_b64: str, page_context: dict, history: list
    ) -> dict:
        """Ask the LLM what action to take next."""
        # Build context message
        context_msg = f"Task: {task}\n\nCurrent page context:\n{json.dumps(page_context, indent=2)}"

        # Add context to history
        messages = history + [{"role": "user", "content": context_msg}]

        # Choose system prompt based on vision mode
        system_prompt = SYSTEM_PROMPT if self.config.use_vision else SYSTEM_PROMPT_NO_VISION

        # Get response from provider
        response_text = self._provider.ask(
            system_prompt=system_prompt,
            messages=messages,
            screenshot_b64=screenshot_b64,
            max_tokens=1024,
            use_vision=self.config.use_vision,
        )

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
            page = browser.new_page(viewport=self.config.viewport)

            if start_url:
                page.goto(start_url, wait_until="domcontentloaded")

            history = []

            try:
                for step in range(max_steps):
                    if self.config.verbose:
                        print(f"--- Step {step + 1} ---")

                    # Give page time to settle
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

                    # Execute the action
                    result = execute_action(
                        page,
                        action,
                        self.config.screenshot_dir,
                        self.config.action_timeout_ms,
                    )

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
                try:
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

    Returns:
        Dictionary with 'success', 'result', 'steps', and optionally 'error'
    """
    config = Config.from_env(provider=provider)
    config.max_steps = max_steps
    config.headless = headless
    config.screenshot_dir = screenshot_dir
    config.verbose = verbose
    config.use_vision = use_vision

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
