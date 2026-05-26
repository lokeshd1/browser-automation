"""
Example: Fill out a form with various input types.
"""

from browser_agent import BrowserAgent, Config


def main():
    # Create custom configuration
    config = Config.from_env()
    config.max_steps = 10
    config.headless = False  # Set True to hide browser
    config.screenshot_dir = "./screenshots"
    config.verbose = True

    # Initialize agent
    agent = BrowserAgent(config)

    # Run task
    result = agent.run(
        task="""
        Fill out the form:
        - First name: John
        - Last name: Doe
        Then click Submit and tell me what happens.
        """,
        start_url="https://www.w3schools.com/html/html_forms.asp",
    )

    print("\n" + "=" * 50)
    print(f"Success: {result.success}")
    print(f"Result: {result.result}")
    print(f"Steps taken: {len(result.steps)}")

    # Print each step
    print("\nSteps:")
    for i, step in enumerate(result.steps, 1):
        print(f"  {i}. {step['action'].get('action')}: {step['result'][:50]}...")


if __name__ == "__main__":
    main()
