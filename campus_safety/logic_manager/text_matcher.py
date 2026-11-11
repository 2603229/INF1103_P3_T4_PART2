from abc import ABC, abstractmethod


class TextMatcher(ABC):
    """
    decides whether two pieces of free text mean the same thing.
    """

    @staticmethod
    def normalise(value) -> str:
        """Lower-case, trim and collapse repeated spaces."""
        return " ".join(str(value or "").strip().lower().split())

    @abstractmethod
    def matches(self, a, b) -> bool:
        pass
