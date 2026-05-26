# Browser Agent

An AI-powered browser automation agent that uses LLM vision capabilities to navigate websites, fill forms, and perform web tasks using natural language instructions.

## Supported LLM Providers

| Provider | Models | Vision Support |
|----------|--------|----------------|
| **Anthropic** | Claude Sonnet, Opus, Haiku | ✓ |
| **OpenAI** | GPT-4o, GPT-4 Turbo | ✓ |
| **Ollama** | LLaVA, Moondream, etc. | ✓ (with vision models) |

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│                      Agent Loop                         │
├─────────────────────────────────────────────────────────┤
│  1. Capture page ────► 2. Send to LLM with task         │
│     (screenshot or        │                             │
│      DOM context)         ▼                             │
│          ▲         3. LLM returns action JSON           │
│          │                │                             │
│  4. Execute action ◄──────┘                             │
│          │                                              │
│          └──────── Repeat until "done" ─────────────────│
└─────────────────────────────────────────────────────────┘
```

### Vision vs Non-Vision Mode

| Mode | How it works | Best for |
|------|--------------|----------|
| **Vision** (default) | Uses screenshots | Complex visual tasks, layout-dependent actions |
| **Non-Vision** | Uses DOM context only | Simple tasks, any LLM, lower cost |

Use `--no-vision` for tasks like clicking buttons, filling forms, or navigation where visual context isn't critical.

## Installation

```bash
# Clone the repository
git clone https://github.com/lokeshd1/browser-automation.git
cd browser-automation

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install
pip install -e .

# Install browser
playwright install chromium
```

## Configuration

Copy `.env.example` to `.env` and configure your preferred provider:

```bash
cp .env.example .env
```

### Anthropic (Claude) - Default

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### OpenAI (GPT-4)

```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4o"  # Optional, defaults to gpt-4o
```

### Ollama (Local)

```bash
# Start Ollama with a vision model
ollama pull llava
ollama serve

# Set environment (optional - these are defaults)
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_MODEL="llava"
```

## Usage

### Command Line

```bash
# Auto-detect provider from environment
browser-agent "Search for Python tutorials" --url https://duckduckgo.com

# Explicitly specify provider
browser-agent "Find the top story" --provider openai --url https://news.ycombinator.com
browser-agent "Take a screenshot" --provider ollama --model llava --url https://example.com

# Non-vision mode (DOM context only - works with any LLM)
browser-agent "Click the login button" --url https://example.com --no-vision

# Non-vision mode with text-only models
browser-agent "Fill the search form" --provider ollama --model llama3 --no-vision

# With options
browser-agent "Fill the contact form" \
  --url https://example.com/contact \
  --provider anthropic \
  --model claude-sonnet-4-20250514 \
  --max-steps 15 \
  --headless \
  --screenshot-dir ./shots
```

### Python API

```python
from browser_agent import run_agent

# Simple usage (auto-detects provider)
result = run_agent(
    task="Find the top story title",
    start_url="https://news.ycombinator.com"
)

# Specify provider
result = run_agent(
    task="Search for Python",
    start_url="https://duckduckgo.com",
    provider="openai",
    model="gpt-4o"
)

# Non-vision mode (DOM context only)
result = run_agent(
    task="Click the login button",
    start_url="https://example.com",
    use_vision=False  # Works with any LLM, lower cost
)

# Using Ollama locally with a text-only model
result = run_agent(
    task="Fill the search form",
    start_url="https://example.com",
    provider="ollama",
    model="llama3",  # Text-only model
    use_vision=False
)
```

### Advanced Usage

```python
from browser_agent import BrowserAgent, Config, get_provider

# Custom configuration
config = Config.from_env(provider="anthropic")
config.max_steps = 15
config.headless = True
config.screenshot_dir = "./screenshots"

agent = BrowserAgent(config)
result = agent.run(
    task="Fill out the registration form",
    start_url="https://example.com/register"
)

# Or use a custom provider
from browser_agent import OpenAIProvider

provider = OpenAIProvider(
    api_key="sk-...",
    model="gpt-4o",
    base_url="https://your-custom-endpoint.com/v1"  # For Azure, etc.
)

config = Config.from_env()
agent = BrowserAgent(config, provider=provider)
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

See the `examples/` directory:

```bash
cd examples
python search_example.py
python news_example.py
python form_example.py
```

## Project Structure

```
browser-automation/
├── src/browser_agent/
│   ├── __init__.py
│   ├── agent.py           # Main BrowserAgent class
│   ├── actions.py         # Browser action execution
│   ├── config.py          # Configuration management
│   ├── cli.py             # Command-line interface
│   └── providers/         # LLM provider implementations
│       ├── __init__.py
│       ├── base.py        # Base provider class
│       ├── anthropic.py   # Claude provider
│       ├── openai.py      # GPT-4 provider
│       └── ollama.py      # Ollama provider
├── examples/
├── pyproject.toml
├── .env.example
└── README.md
```

## Adding Custom Providers

You can add support for other LLM providers by extending `BaseLLMProvider`:

```python
from browser_agent.providers import BaseLLMProvider

class MyProvider(BaseLLMProvider):
    @property
    def name(self) -> str:
        return "my-provider"

    @property
    def supports_vision(self) -> bool:
        return True

    def ask(self, system_prompt, messages, screenshot_b64, max_tokens=1024):
        # Implement your API call here
        return "{'action': 'done', 'result': 'Task completed'}"

# Use it
from browser_agent import BrowserAgent, Config

config = Config.from_env()
agent = BrowserAgent(config, provider=MyProvider())
```

## Non-Vision Mode

Non-vision mode uses structured DOM context instead of screenshots, making the agent work with any LLM while reducing cost and latency.

**Benefits:**
- Works with any LLM (no vision capability required)
- ~80% lower token cost (no image tokens)
- Faster response times
- Good for 80% of tasks (clicking buttons, filling forms, navigation)

**When to use vision mode:**
- Complex visual layouts
- Tasks requiring spatial understanding
- Identifying elements by appearance rather than text

**Environment variable:**
```bash
export BROWSER_AGENT_NO_VISION=true
```

## Limitations

- Cannot solve CAPTCHAs
- Cannot handle 2FA/MFA authentication
- Some sites have bot detection that may block automation
- Non-vision mode may struggle with complex visual layouts

## Requirements

- Python 3.8+
- API key for your chosen provider (or Ollama running locally)
- Chromium browser (installed via Playwright)

## License

MIT
