# Browser Agent

An AI-powered browser automation agent that uses Claude's vision capabilities to navigate websites, fill forms, and perform web tasks using natural language instructions.

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│                      Agent Loop                         │
├─────────────────────────────────────────────────────────┤
│  1. Screenshot page ──► 2. Send to Claude with task     │
│          ▲                        │                     │
│          │                        ▼                     │
│  4. Execute action ◄── 3. Claude returns action JSON    │
│          │                                              │
│          └──────── Repeat until "done" ─────────────────│
└─────────────────────────────────────────────────────────┘
```

The agent takes a screenshot of the current page, sends it to Claude along with your task description, and Claude decides what action to take next. This continues until the task is complete.

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/lokeshd1/browser-automation.git
cd browser-automation

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .

# Install Playwright browser
playwright install chromium
```

### Quick Install

```bash
pip install -e git+https://github.com/lokeshd1/browser-automation.git#egg=browser-agent
playwright install chromium
```

## Configuration

Copy `.env.example` to `.env` and configure your API credentials:

```bash
cp .env.example .env
```

### Option 1: Standard Anthropic API

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Option 2: Enterprise Bedrock Endpoint

```bash
export ANTHROPIC_BEDROCK_BASE_URL="https://your-endpoint.com/v1"
export ANTHROPIC_AUTH_TOKEN="your-token"
export ANTHROPIC_DEFAULT_SONNET_MODEL="your-model-id"
```

## Usage

### Command Line

```bash
# Basic usage
browser-agent "Search for Python tutorials on DuckDuckGo"

# With starting URL
browser-agent "Find the top story" --url https://news.ycombinator.com

# Headless mode (no browser window)
browser-agent "Take a screenshot of the homepage" --url https://example.com --headless

# Save screenshots
browser-agent "Click the first article and screenshot it" --screenshot-dir ./shots

# Custom viewport
browser-agent "Check mobile layout" --url https://example.com --viewport 375x812

# All options
browser-agent "Fill the contact form" \
  --url https://example.com/contact \
  --max-steps 15 \
  --headless \
  --screenshot-dir ./screenshots \
  --viewport 1920x1080
```

### Python API

#### Simple Usage

```python
from browser_agent import run_agent

result = run_agent(
    task="Go to Hacker News and find the top story title",
    start_url="https://news.ycombinator.com"
)

print(result["success"])  # True/False
print(result["result"])   # Task result summary
```

#### Advanced Usage

```python
from browser_agent import BrowserAgent, Config

# Custom configuration
config = Config.from_env()
config.max_steps = 15
config.headless = True
config.screenshot_dir = "./screenshots"
config.viewport_width = 1920
config.viewport_height = 1080

# Initialize agent
agent = BrowserAgent(config)

# Run task
result = agent.run(
    task="Fill the form with name 'John Doe' and submit",
    start_url="https://example.com/form"
)

# Access results
print(f"Success: {result.success}")
print(f"Result: {result.result}")
print(f"Steps: {len(result.steps)}")

# Inspect individual steps
for step in result.steps:
    print(f"  Action: {step['action']}")
    print(f"  Result: {step['result']}")
```

## Supported Actions

| Category | Actions |
|----------|---------|
| **Navigation** | `goto`, `back`, `forward`, `refresh` |
| **Mouse** | `click`, `double_click`, `right_click`, `hover` |
| **Forms** | `fill`, `clear`, `select`, `check`, `uncheck`, `upload` |
| **Keyboard** | `press`, `type` |
| **Scrolling** | `scroll`, `scroll_to` |
| **Data** | `extract`, `get_attribute`, `get_text` |
| **Waiting** | `wait`, `wait_hidden`, `sleep` |
| **Utilities** | `screenshot`, `focus` |

## Examples

See the `examples/` directory for complete examples:

- `search_example.py` - Search and extract results
- `news_example.py` - Navigate and take screenshots
- `form_example.py` - Fill out forms
- `simple_playwright.py` - Basic Playwright without AI

Run an example:

```bash
cd examples
python search_example.py
```

## Project Structure

```
browser-automation/
├── src/
│   └── browser_agent/
│       ├── __init__.py      # Package exports
│       ├── agent.py         # Main BrowserAgent class
│       ├── actions.py       # Action definitions and execution
│       ├── config.py        # Configuration management
│       └── cli.py           # Command-line interface
├── examples/
│   ├── search_example.py
│   ├── news_example.py
│   ├── form_example.py
│   └── simple_playwright.py
├── pyproject.toml           # Package configuration
├── requirements.txt         # Dependencies
├── .env.example             # Example environment config
└── README.md
```

## Limitations

- Cannot solve CAPTCHAs
- Cannot handle 2FA/MFA authentication flows
- Some sites have bot detection that may block automation
- File uploads require the file to exist locally

## Requirements

- Python 3.8+
- Anthropic API key or enterprise Bedrock endpoint
- Chromium browser (installed via Playwright)

## License

MIT
