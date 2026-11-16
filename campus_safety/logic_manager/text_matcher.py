# FILE GUIDE: Decides whether two free-text values mean the same thing (used for duplicate/history checks).
# Typo tolerant, but numbers and single letters must match exactly ("Lab 1" != "Lab 10", "Block A" != "Block B").

"""Text matcher."""
import re
from difflib import SequenceMatcher
from typing import Any


class TextMatcher:
    """Fuzzy text matching with a validated similarity threshold.

    threshold=0.85 tolerates typos ("Libary" ~ "Library", "Air con" ~ "Aircon");
    threshold=1.0 makes the matcher strict (only identical text matches).
    """

    def __init__(self, threshold: float = 0.85) -> None:
        """Create a matcher.

        Args:
            threshold: Minimum similarity ratio, in (0, 1].

        Raises:
            ValueError: If threshold is outside (0, 1].
        """
        self.threshold = threshold  # goes through the validating setter

    @property
    def threshold(self) -> float:
        """Minimum similarity ratio needed for a match."""
        return self.__threshold

    @threshold.setter
    def threshold(self, value: float) -> None:
        if not 0.0 < value <= 1.0:
            raise ValueError("threshold must be in (0, 1]")
        self.__threshold = value

    @staticmethod
    def normalise(value: Any) -> str:
        """Lower-case, trim and collapse repeated spaces (None -> '')."""
        return " ".join(str(value or "").strip().lower().split())

    @staticmethod
    def _identifiers(text: str) -> list[str]:
        """Numbers and standalone single letters found in the text."""
        return re.findall(r"\d+|\b[a-z]\b", text)

    def matches(self, a: Any, b: Any) -> bool:
        """Return True if a and b are considered the same text."""
        x, y = self.normalise(a), self.normalise(b)
        if x == y:
            return True
        if not x or not y:
            return False
        if self._identifiers(x) != self._identifiers(y):
            return False
        x, y = x.replace(" ", ""), y.replace(" ", "")
        return SequenceMatcher(None, x, y).ratio() >= self.__threshold
