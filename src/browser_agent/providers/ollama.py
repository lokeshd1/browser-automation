"""
Ollama LLM provider for local models.
"""

import os
from typing import Optional

import httpx

from .base import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """Provider for local Ollama models."""

    # Models known to support vision
    VISION_MODELS = {
        "llava",
        "llava-llama3",
        "llava:7b",
        "llava:13b",
        "llava:34b",
        "bakllava",
        "moondream",
        "minicpm-v",
    }

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize Ollama provider.

        Args:
            model: Model name (default: llava for vision support)
            base_url: Ollama server URL (default: http://localhost:11434)
        """
        self.model = model or os.environ.get("OLLAMA_MODEL", "llava")
        self.base_url = base_url or os.environ.get(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        )

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def supports_vision(self) -> bool:
        # Check if model name contains a known vision model
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
        """Send request to Ollama."""
        # Build prompt from messages
        prompt_parts = [system_prompt, ""]

        for msg in messages:
            role = msg["role"].upper()
            content = msg["content"]
            prompt_parts.append(f"{role}: {content}")

        # Adjust prompt based on vision mode
        if use_vision and self.supports_vision and screenshot_b64:
            prompt_parts.append("What action should I take next based on this screenshot?")
        else:
            prompt_parts.append("What action should I take next based on the page context provided above?")

        prompt = "\n".join(prompt_parts)

        # Build request
        request_data = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
            },
        }

        # Add image only if vision mode is enabled and model supports it
        if use_vision and self.supports_vision and screenshot_b64:
            request_data["images"] = [screenshot_b64]

        response = httpx.post(
            f"{self.base_url}/api/generate",
            json=request_data,
            timeout=120.0,  # Longer timeout for local models
        )
        response.raise_for_status()
        data = response.json()
        return data["response"]
