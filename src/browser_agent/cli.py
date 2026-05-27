"""
Command-line interface for Browser Agent.
"""

import argparse
import sys

from .agent import BrowserAgent
from .config import Config


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="AI-powered browser automation using LLMs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using Claude (default)
  browser-agent "Search for Python tutorials on DuckDuckGo"

  # Using OpenAI GPT-4
  browser-agent "Find the top story" --provider openai --url https://news.ycombinator.com

  # Using local Ollama
  browser-agent "Take a screenshot" --provider ollama --model llava

  # Non-vision mode (works with any LLM, lower cost)
  browser-agent "Click the login button" --url https://example.com --no-vision

  # Non-vision mode with text-only Ollama model
  browser-agent "Fill the search form" --provider ollama --model llama3 --no-vision

  # With retry and session persistence
  browser-agent "Login and save credentials" \\
    --url https://example.com/login \\
    --max-retries 5 \\
    --save-session

  # Resume with saved session
  browser-agent "Go to dashboard" \\
    --url https://example.com \\
    --load-session

  # With all options
  browser-agent "Fill the form with name John" \\
    --url https://example.com \\
    --provider anthropic \\
    --model claude-sonnet-4-20250514 \\
    --headless \\
    --screenshot-dir ./shots

Supported Providers:
  anthropic   Claude models (default) - requires ANTHROPIC_API_KEY
  openai      GPT-4 models - requires OPENAI_API_KEY
  ollama      Local models - requires Ollama running locally
        """,
    )

    parser.add_argument(
        "task",
        nargs="?",
        help="Task to perform (natural language description)",
    )

    parser.add_argument(
        "--url", "-u",
        help="Starting URL to navigate to",
    )

    parser.add_argument(
        "--provider", "-p",
        choices=["anthropic", "openai", "ollama"],
        help="LLM provider (default: auto-detect from environment)",
    )

    parser.add_argument(
        "--model", "-m",
        help="Model name (provider-specific)",
    )

    parser.add_argument(
        "--api-key",
        help="API key (overrides environment variable)",
    )

    parser.add_argument(
        "--max-steps",
        type=int,
        default=10,
        help="Maximum number of actions (default: 10)",
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser without GUI",
    )

    parser.add_argument(
        "--screenshot-dir", "-s",
        help="Directory to save screenshots",
    )

    parser.add_argument(
        "--viewport",
        help="Viewport size as WIDTHxHEIGHT (e.g., 1920x1080)",
    )

    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress output",
    )

    parser.add_argument(
        "--no-vision",
        action="store_true",
        help="Disable vision mode, use DOM context only (works with any LLM, reduces cost)",
    )

    # Reliability options
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Max retries for failed actions (default: 3)",
    )

    parser.add_argument(
        "--no-smart-wait",
        action="store_true",
        help="Disable adaptive waiting, use fixed delay",
    )

    # Session options
    parser.add_argument(
        "--save-session",
        action="store_true",
        help="Save browser session on successful completion",
    )

    parser.add_argument(
        "--load-session",
        action="store_true",
        help="Load browser session from file if available",
    )

    parser.add_argument(
        "--session-file",
        help="Path to session file (default: .browser_agent_session.json)",
    )

    parser.add_argument(
        "--version", "-v",
        action="store_true",
        help="Show version and exit",
    )

    args = parser.parse_args()

    if args.version:
        from . import __version__
        print(f"browser-agent {__version__}")
        sys.exit(0)

    if not args.task:
        parser.print_help()
        sys.exit(1)

    # Build configuration
    try:
        config = Config.from_env(provider=args.provider)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    config.max_steps = args.max_steps
    config.headless = args.headless
    config.screenshot_dir = args.screenshot_dir
    config.verbose = not args.quiet

    if args.no_vision:
        config.use_vision = False

    # Reliability settings
    config.action_max_retries = args.max_retries
    config.smart_wait_enabled = not args.no_smart_wait

    # Session settings
    config.save_session = args.save_session
    config.load_session = args.load_session
    if args.session_file:
        config.session_file = args.session_file

    if args.model:
        config.model = args.model
    if args.api_key:
        config.api_key = args.api_key

    if args.viewport:
        try:
            width, height = args.viewport.split("x")
            config.viewport_width = int(width)
            config.viewport_height = int(height)
        except ValueError:
            print(f"Error: Invalid viewport format '{args.viewport}'. Use WIDTHxHEIGHT (e.g., 1920x1080)")
            sys.exit(1)

    # Run agent
    try:
        config.validate()
        agent = BrowserAgent(config)
        result = agent.run(args.task, args.url)

        if result.success:
            print(f"\n✓ Task completed: {result.result}")
            sys.exit(0)
        else:
            print(f"\n✗ Task did not complete. Steps taken: {len(result.steps)}")
            if result.error:
                print(f"  Error: {result.error}")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nAborted by user")
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
