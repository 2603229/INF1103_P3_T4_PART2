import re
from difflib import SequenceMatcher

from .text_matcher import TextMatcher


class FuzzyMatcher(TextMatcher):
    """
    Tolerates typos and spacing differences ("Libary" ~ "Library",
    "Air con" ~ "Aircon").

    Numbers must match exactly, so "Lab 1" never matches "Lab 10" or "Lab 2",
    which are different places even though the text is very similar.
    """

    def __init__(self, threshold: float = 0.85) -> None:
        if not 0.0 < threshold <= 1.0:
            raise ValueError("threshold must be in (0, 1]")
        self._threshold = threshold

    @staticmethod
    def _numbers(text: str) -> list[str]:
        return re.findall(r"\d+", text)

    def matches(self, a, b) -> bool:
        x, y = self.normalise(a), self.normalise(b)
        if x == y:
            return True
        if not x or not y:
            return False
        if self._numbers(x) != self._numbers(y):
            return False
        x, y = x.replace(" ", ""), y.replace(" ", "")
        return SequenceMatcher(None, x, y).ratio() >= self._threshold
