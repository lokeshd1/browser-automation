"""
Base class for LLM providers.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name."""
        pass

    @property
    @abstractmethod
    def supports_vision(self) -> bool:
        """Return whether this provider supports vision/image inputs."""
        pass

    @abstractmethod
    def ask(
        self,
        system_prompt: str,
        messages: list,
        screenshot_b64: str,
        max_tokens: int = 1024,
    ) -> str:
        """
        Send a request to the LLM.

        Args:
            system_prompt: System instructions for the model
            messages: Conversation history
            screenshot_b64: Base64-encoded screenshot image
            max_tokens: Maximum tokens in response

        Returns:
            Model's text response
        """
        pass

    def _format_image_for_prompt(self, screenshot_b64: str) -> str:
        """
        Format screenshot as text description for non-vision models.
        This is a fallback for models that don't support images.
        """
        return (
            "[Screenshot provided but this model doesn't support vision. "
            "Please use page_context to understand the page structure.]"
        )
