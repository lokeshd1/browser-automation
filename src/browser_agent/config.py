"""
Configuration management for Browser Agent.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Configuration for the browser agent."""

    # Provider Configuration
    provider: str = "anthropic"  # anthropic, openai, ollama
    model: Optional[str] = None  # Model name (provider-specific)

    # API Configuration (provider-specific)
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    auth_token: Optional[str] = None  # For enterprise endpoints

    # Browser Configuration
    headless: bool = False
    viewport_width: int = 1280
    viewport_height: int = 800

    # Agent Configuration
    max_steps: int = 10
    step_delay_ms: int = 1000
    action_timeout_ms: int = 5000

    # Output Configuration
    screenshot_dir: Optional[str] = None
    verbose: bool = True

    @classmethod
    def from_env(cls, provider: Optional[str] = None) -> "Config":
        """
        Create configuration from environment variables.

        Args:
            provider: Override provider detection (anthropic, openai, ollama)
        """
        # Auto-detect provider from environment if not specified
        if provider is None:
            if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_BEDROCK_BASE_URL"):
                provider = "anthropic"
            elif os.environ.get("OPENAI_API_KEY"):
                provider = "openai"
            elif os.environ.get("OLLAMA_MODEL") or os.environ.get("OLLAMA_BASE_URL"):
                provider = "ollama"
            else:
                provider = "anthropic"  # Default

        config = cls(provider=provider)

        # Load provider-specific settings
        if provider == "anthropic":
            config.api_key = os.environ.get("ANTHROPIC_API_KEY")
            config.base_url = os.environ.get("ANTHROPIC_BEDROCK_BASE_URL")
            config.auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN")
            config.model = os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL", "claude-sonnet-4-20250514")

        elif provider == "openai":
            config.api_key = os.environ.get("OPENAI_API_KEY")
            config.base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
            config.model = os.environ.get("OPENAI_MODEL", "gpt-4o")

        elif provider == "ollama":
            config.base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
            config.model = os.environ.get("OLLAMA_MODEL", "llava")

        return config

    @property
    def use_enterprise(self) -> bool:
        """Check if using enterprise Bedrock endpoint (Anthropic only)."""
        return self.provider == "anthropic" and bool(self.base_url and self.auth_token)

    @property
    def viewport(self) -> dict:
        """Get viewport as dict."""
        return {"width": self.viewport_width, "height": self.viewport_height}

    def validate(self) -> None:
        """Validate configuration."""
        if self.provider == "anthropic":
            if not self.use_enterprise and not self.api_key:
                raise ValueError(
                    "Anthropic: Set ANTHROPIC_API_KEY or "
                    "ANTHROPIC_BEDROCK_BASE_URL + ANTHROPIC_AUTH_TOKEN"
                )
        elif self.provider == "openai":
            if not self.api_key:
                raise ValueError("OpenAI: Set OPENAI_API_KEY")
        elif self.provider == "ollama":
            pass  # Ollama doesn't require auth
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def get_provider_kwargs(self) -> dict:
        """Get kwargs for provider initialization."""
        kwargs = {}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.model:
            kwargs["model"] = self.model
        if self.base_url:
            kwargs["base_url"] = self.base_url
        if self.auth_token:
            kwargs["auth_token"] = self.auth_token
        return kwargs
