"""
OpenAI (GPT-4) LLM provider.
Also works with any OpenAI-compatible API (Azure, local servers, etc.)
"""

import os
from typing import Optional

import httpx

from .base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """Provider for OpenAI GPT models and OpenAI-compatible APIs."""

    # Models that support vision
    VISION_MODELS = {
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4-vision-preview",
        "gpt-4.1",
        "gpt-4.1-mini",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
            model: Model name (default: gpt-4o)
            base_url: Custom base URL for OpenAI-compatible APIs
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY or pass api_key parameter."
            )

        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o")
        self.base_url = base_url or os.environ.get(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        )

    @property
    def name(self) -> str:
        return "openai"

    @property
    def supports_vision(self) -> bool:
        # Check if model supports vision
        model_lower = self.model.lower()
        return any(vm in model_lower for vm in self.VISION_MODELS)

    def ask(
        self,
        system_prompt: str,
        messages: list,
        screenshot_b64: str,
        max_tokens: int = 1024,
        use_vision: bool = True,
    ) -> str:
        """Send request to OpenAI."""
        # Convert messages to OpenAI format
        openai_messages = [{"role": "system", "content": system_prompt}]

        for msg in messages:
            openai_messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        # Add the current request - with or without image based on use_vision
        if use_vision and self.supports_vision and screenshot_b64:
            openai_messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "What action should I take next based on this screenshot?",
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{screenshot_b64}",
                            "detail": "high",
                        },
                    },
                ],
            })
        else:
            # Non-vision mode or model doesn't support vision
            openai_messages.append({
                "role": "user",
                "content": "What action should I take next based on the page context provided above?",
            })

        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": openai_messages,
                "max_tokens": max_tokens,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
