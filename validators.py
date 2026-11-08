from __future__ import annotations
import re

class InputValidator:
    """Provides pure validation functions for user-submitted hazard report data."""

    # This function validates personal or entity names to ensure they only contain permitted typographic 
    # characters (alphabets, spaces, quotes, hyphens, percent signs, or periods).
    @staticmethod
    def validate_name(name: str) -> bool:
        """Check if name contains only alphabets, spaces, quotes, hyphens, or periods."""
        return bool(re.fullmatch(r"[A-Za-z\s'.-]+", name))

