"""
Configuration management for Browser Agent.
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    """Configuration for the browser agent."""

    # API Configuration
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    auth_token: Optional[str] = None
    model: str = "claude-sonnet-4-20250514"

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
    def from_env(cls) -> "Config":
        """Create configuration from environment variables."""
        base_url = os.environ.get("ANTHROPIC_BEDROCK_BASE_URL")
        auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN")
        api_key = os.environ.get("ANTHROPIC_API_KEY")

        # Determine model based on environment
        if base_url and auth_token:
            model = os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL", "claude-sonnet-4-20250514")
        else:
            model = "claude-sonnet-4-20250514"

        return cls(
            api_key=api_key,
            base_url=base_url,
            auth_token=auth_token,
            model=model,
        )

    @property
    def use_enterprise(self) -> bool:
        """Check if using enterprise Bedrock endpoint."""
        return bool(self.base_url and self.auth_token)

    @property
    def viewport(self) -> dict:
        """Get viewport as dict."""
        return {"width": self.viewport_width, "height": self.viewport_height}

    def validate(self) -> None:
        """Validate configuration."""
        if not self.use_enterprise and not self.api_key:
            raise ValueError(
                "No API credentials found. Set ANTHROPIC_API_KEY or "
                "ANTHROPIC_BEDROCK_BASE_URL + ANTHROPIC_AUTH_TOKEN"
            )
