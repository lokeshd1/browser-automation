# example_browser_automation.py
"""
Simple Playwright example - scrapes top stories from Hacker News.
Run: python example_browser_automation.py
"""
from playwright.sync_api import sync_playwright


def automate_search():
    with sync_playwright() as p:
        # Launch browser (headless=False to watch it run)
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        # Navigate to a page
        page.goto("https://news.ycombinator.com")

        # Extract data - get top 5 story titles
        stories = page.locator(".titleline > a").all()[:5]

        print("Top 5 Hacker News stories:")
        for i, story in enumerate(stories, 1):
            print(f"{i}. {story.text_content()}")

        # Example: clicking and form filling
        # page.click("button#submit")
        # page.fill("input[name='username']", "myuser")
        # page.fill("input[name='password']", "mypass")

        browser.close()


if __name__ == "__main__":
    automate_search()
