"""
Session management for browser persistence.
"""

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class SessionConfig:
    """Configuration for session management."""

    session_file: str = ".browser_agent_session.json"
    session_ttl_hours: int = 24


class SessionManager:
    """Manages browser session persistence (cookies, localStorage, sessionStorage)."""

    def __init__(self, config: Optional[SessionConfig] = None):
        """
        Initialize the session manager.

        Args:
            config: Session configuration (uses defaults if None)
        """
        self.config = config or SessionConfig()

    def save_session(self, context: Any, filepath: Optional[str] = None) -> bool:
        """
        Save browser context session data to a file.

        Saves cookies, localStorage, and sessionStorage.

        Args:
            context: Playwright browser context
            filepath: Override session file path

        Returns:
            True if session was saved successfully
        """
        filepath = filepath or self.config.session_file

        try:
            # Get cookies from context
            cookies = context.cookies()

            # Get storage state (includes cookies and origins with localStorage)
            storage_state = context.storage_state()

            session_data = {
                "version": 1,
                "timestamp": time.time(),
                "ttl_hours": self.config.session_ttl_hours,
                "cookies": cookies,
                "storage_state": storage_state,
            }

            # Write to file
            with open(filepath, "w") as f:
                json.dump(session_data, f, indent=2)

            return True
        except Exception as e:
            print(f"Warning: Failed to save session: {e}")
            return False

    def load_session(self, filepath: Optional[str] = None) -> Optional[dict]:
        """
        Load session data from file.

        Args:
            filepath: Override session file path

        Returns:
            Session data dict if valid and not expired, None otherwise
        """
        filepath = filepath or self.config.session_file

        if not os.path.exists(filepath):
            return None

        try:
            with open(filepath, "r") as f:
                session_data = json.load(f)

            # Check version compatibility
            if session_data.get("version") != 1:
                return None

            # Check if session has expired
            timestamp = session_data.get("timestamp", 0)
            ttl_hours = session_data.get("ttl_hours", self.config.session_ttl_hours)
            age_hours = (time.time() - timestamp) / 3600

            if age_hours > ttl_hours:
                # Session expired, remove file
                try:
                    os.remove(filepath)
                except Exception:
                    pass
                return None

            return session_data
        except Exception as e:
            print(f"Warning: Failed to load session: {e}")
            return None

    def create_context_with_session(
        self,
        browser: Any,
        viewport: dict,
        filepath: Optional[str] = None,
    ) -> Any:
        """
        Create a browser context, restoring session if available.

        Args:
            browser: Playwright browser instance
            viewport: Viewport dimensions {"width": int, "height": int}
            filepath: Override session file path

        Returns:
            Playwright browser context (with or without restored session)
        """
        filepath = filepath or self.config.session_file

        # Try to load existing session
        session_data = self.load_session(filepath)

        if session_data and session_data.get("storage_state"):
            try:
                # Create context with restored storage state
                context = browser.new_context(
                    viewport=viewport,
                    storage_state=session_data["storage_state"],
                )
                return context
            except Exception as e:
                print(f"Warning: Failed to restore session, creating fresh context: {e}")

        # Create fresh context
        return browser.new_context(viewport=viewport)

    def delete_session(self, filepath: Optional[str] = None) -> bool:
        """
        Delete the session file.

        Args:
            filepath: Override session file path

        Returns:
            True if file was deleted or didn't exist
        """
        filepath = filepath or self.config.session_file

        try:
            if os.path.exists(filepath):
                os.remove(filepath)
            return True
        except Exception:
            return False

    def session_exists(self, filepath: Optional[str] = None) -> bool:
        """
        Check if a valid (non-expired) session exists.

        Args:
            filepath: Override session file path

        Returns:
            True if valid session file exists
        """
        return self.load_session(filepath) is not None

    def get_session_info(self, filepath: Optional[str] = None) -> Optional[dict]:
        """
        Get information about the current session.

        Args:
            filepath: Override session file path

        Returns:
            Dict with session info, or None if no valid session
        """
        session_data = self.load_session(filepath)

        if not session_data:
            return None

        timestamp = session_data.get("timestamp", 0)
        ttl_hours = session_data.get("ttl_hours", self.config.session_ttl_hours)
        age_hours = (time.time() - timestamp) / 3600
        remaining_hours = ttl_hours - age_hours

        cookies = session_data.get("cookies", [])
        origins = session_data.get("storage_state", {}).get("origins", [])

        return {
            "age_hours": round(age_hours, 2),
            "remaining_hours": round(remaining_hours, 2),
            "cookie_count": len(cookies),
            "origin_count": len(origins),
            "domains": list(set(c.get("domain", "") for c in cookies)),
        }
