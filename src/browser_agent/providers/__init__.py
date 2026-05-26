"""
LLM Provider implementations for Browser Agent.
"""

from .base import BaseLLMProvider
from .anthropic import AnthropicProvider
from .openai import OpenAIProvider
from .ollama import OllamaProvider

__all__ = [
    "BaseLLMProvider",
    "AnthropicProvider",
    "OpenAIProvider",
    "OllamaProvider",
    "get_provider",
]


def get_provider(provider_name: str, **kwargs) -> BaseLLMProvider:
    """
    Get an LLM provider by name.

    Args:
        provider_name: Name of the provider ('anthropic', 'openai', 'ollama', 'openai-compatible')
        **kwargs: Provider-specific configuration

    Returns:
        Configured LLM provider instance
    """
    providers = {
        "anthropic": AnthropicProvider,
        "claude": AnthropicProvider,  # Alias
        "openai": OpenAIProvider,
        "gpt": OpenAIProvider,  # Alias
        "ollama": OllamaProvider,
        "openai-compatible": OpenAIProvider,  # For any OpenAI-compatible API
    }

    provider_name = provider_name.lower()
    if provider_name not in providers:
        available = ", ".join(sorted(set(providers.keys())))
        raise ValueError(f"Unknown provider '{provider_name}'. Available: {available}")

    return providers[provider_name](**kwargs)
