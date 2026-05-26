"""
Example: Navigate Hacker News and extract top story.
"""

from browser_agent import run_agent


def main():
    result = run_agent(
        task="Click on the top story to open it, then take a screenshot named 'top_story.png' and tell me the article title",
        start_url="https://news.ycombinator.com",
        screenshot_dir="./screenshots",
        max_steps=6,
    )

    print("\n" + "=" * 50)
    print(f"Success: {result['success']}")
    print(f"Result: {result['result']}")


if __name__ == "__main__":
    main()
