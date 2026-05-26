"""
Example: Search on DuckDuckGo and extract results.
"""

from browser_agent import run_agent


def main():
    result = run_agent(
        task='Search for "python web scraping" and tell me the first 3 results',
        start_url="https://duckduckgo.com",
        max_steps=8,
    )

    print("\n" + "=" * 50)
    print(f"Success: {result['success']}")
    print(f"Result: {result['result']}")
    print(f"Steps taken: {len(result['steps'])}")


if __name__ == "__main__":
    main()
