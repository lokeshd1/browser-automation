"""
Browser Agent - AI-powered browser automation using Claude.
"""

from .agent import BrowserAgent, run_agent
from .config import Config

__version__ = "0.1.0"
__all__ = ["BrowserAgent", "run_agent", "Config"]
