"""
Simple Playwright example without AI - basic browser automation.
"""

from playwright.sync_api import sync_playwright


def main():
    """Scrape top stories from Hacker News using Playwright directly."""

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        # Navigate to Hacker News
        page.goto("https://news.ycombinator.com")

        # Extract top 5 story titles
        stories = page.locator(".titleline > a").all()[:5]

        print("Top 5 Hacker News stories:")
        print("-" * 40)
        for i, story in enumerate(stories, 1):
            print(f"{i}. {story.text_content()}")

        # Example: Take a screenshot
        page.screenshot(path="hacker_news.png")
        print(f"\nScreenshot saved to: hacker_news.png")

        browser.close()


if __name__ == "__main__":
    main()
