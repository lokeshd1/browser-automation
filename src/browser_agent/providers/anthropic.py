"""
Anthropic (Claude) LLM provider.
"""

import os
from typing import Optional

import httpx

from .base import BaseLLMProvider


class AnthropicProvider(BaseLLMProvider):
    """Provider for Anthropic Claude models."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        auth_token: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
            model: Model name (default: claude-sonnet-4-20250514)
            base_url: Custom base URL for enterprise endpoints
            auth_token: Auth token for enterprise endpoints
        """
        # Check for enterprise endpoint first
        self.base_url = base_url or os.environ.get("ANTHROPIC_BEDROCK_BASE_URL")
        self.auth_token = auth_token or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        self.use_enterprise = bool(self.base_url and self.auth_token)

        if self.use_enterprise:
            self.model = model or os.environ.get(
                "ANTHROPIC_DEFAULT_SONNET_MODEL", "claude-sonnet-4-20250514"
            )
            self._client = None
        else:
            self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not self.api_key:
                raise ValueError(
                    "Anthropic API key required. Set ANTHROPIC_API_KEY or pass api_key parameter."
                )
            self.model = model or "claude-sonnet-4-20250514"

            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def supports_vision(self) -> bool:
        return True

    def ask(
        self,
        system_prompt: str,
        messages: list,
        screenshot_b64: str,
        max_tokens: int = 1024,
        use_vision: bool = True,
    ) -> str:
        """Send request to Claude."""
        # Build the message - with or without image based on use_vision
        if use_vision and screenshot_b64:
            formatted_messages = messages + [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "What action should I take next based on this screenshot?",
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot_b64,
                            },
                        },
                    ],
                }
            ]
        else:
            # Non-vision mode: use DOM context only
            formatted_messages = messages + [
                {
                    "role": "user",
                    "content": "What action should I take next based on the page context provided above?",
                }
            ]

        if self.use_enterprise:
            response = httpx.post(
                f"{self.base_url}/messages",
                headers={
                    "Authorization": f"Bearer {self.auth_token}",
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": formatted_messages,
                },
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]
        else:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=formatted_messages,
            )
            return response.content[0].text
