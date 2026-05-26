"""
Browser Agent - AI-powered browser automation using LLMs.

Supports multiple LLM providers:
- Anthropic (Claude)
- OpenAI (GPT-4)
- Ollama (local models)
"""

from .agent import BrowserAgent, run_agent
from .config import Config
from .providers import get_provider, BaseLLMProvider, AnthropicProvider, OpenAIProvider, OllamaProvider

__version__ = "0.2.0"
__all__ = [
    "BrowserAgent",
    "run_agent",
    "Config",
    "get_provider",
    "BaseLLMProvider",
    "AnthropicProvider",
    "OpenAIProvider",
    "OllamaProvider",
]
