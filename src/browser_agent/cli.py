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
        description="AI-powered browser automation using Claude",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  browser-agent "Search for Python tutorials on DuckDuckGo"
  browser-agent "Find the top story" --url https://news.ycombinator.com
  browser-agent "Fill the form with name John" --url https://example.com --headless
  browser-agent "Take a screenshot" --screenshot-dir ./shots
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
        "--max-steps", "-m",
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
        config = Config.from_env()
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    config.max_steps = args.max_steps
    config.headless = args.headless
    config.screenshot_dir = args.screenshot_dir
    config.verbose = not args.quiet

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
