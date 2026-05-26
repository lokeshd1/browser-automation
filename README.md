# Browser Automation Agent

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

## Features

### Supported Actions

| Category | Actions |
|----------|---------|
| **Navigation** | `goto`, `back`, `forward`, `refresh` |
| **Mouse** | `click`, `double_click`, `right_click`, `hover` |
| **Forms** | `fill`, `clear`, `select` (dropdowns), `check`, `uncheck`, `upload` |
| **Keyboard** | `press` (keys/combos), `type` |
| **Scrolling** | `scroll`, `scroll_to` |
| **Data Extraction** | `extract`, `get_attribute`, `get_text` |
| **Waiting** | `wait`, `wait_hidden`, `sleep` |
| **Utilities** | `screenshot`, `focus` |

## Installation

```bash
# Clone the repository
git clone https://github.com/lokeshd1/browser-automation.git
cd browser-automation

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install browser
playwright install chromium
```

## Configuration

### Standard Anthropic API

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Enterprise Bedrock Endpoint

```bash
export ANTHROPIC_BEDROCK_BASE_URL="https://your-endpoint.com/v1"
export ANTHROPIC_AUTH_TOKEN="your-token"
export ANTHROPIC_DEFAULT_SONNET_MODEL="your-model-id"
```

The agent automatically detects which authentication method to use.

## Usage

### Command Line

```bash
# Activate virtual environment
source venv/bin/activate

# Run with a custom task
python ai_browser_agent.py "Search for Python tutorials on Google"
```

### Python Script

```python
from ai_browser_agent import run_agent

# Simple task
result = run_agent(
    task="Go to Hacker News and find the top story title",
    start_url="https://news.ycombinator.com"
)

print(result["result"])
```

### Advanced Options

```python
result = run_agent(
    task="Fill out the contact form with name 'John Doe' and email 'john@example.com'",
    start_url="https://example.com/contact",
    max_steps=15,              # Maximum actions before stopping
    headless=True,             # Run without visible browser
    screenshot_dir="./shots",  # Save screenshots here
    viewport={"width": 1920, "height": 1080}
)
```

## Examples

### Search and Extract

```python
run_agent(
    task="Search for 'playwright python' and tell me the first result",
    start_url="https://duckduckgo.com"
)
```

### Form Filling

```python
run_agent(
    task="Fill the form with name 'Jane Smith', select 'Support' from the dropdown, and submit",
    start_url="https://example.com/form"
)
```

### Navigation and Screenshots

```python
run_agent(
    task="Click on the first article, scroll down, and take a screenshot named 'article.png'",
    start_url="https://news.ycombinator.com",
    screenshot_dir="./screenshots"
)
```

### Keyboard Shortcuts

```python
run_agent(
    task="Press Ctrl+F to open search, type 'installation', then press Escape",
    start_url="https://docs.python.org"
)
```

## Files

| File | Description |
|------|-------------|
| `ai_browser_agent.py` | Main AI agent with Claude integration |
| `example_browser_automation.py` | Simple Playwright example (no AI) |
| `requirements.txt` | Python dependencies |

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
