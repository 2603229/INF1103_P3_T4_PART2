from abc import ABC, abstractmethod


class PriorityRule(ABC):
    def __init__(self, priority: str, action: str, reason: str) -> None:
        self._priority = priority
        self._action = action
        self._reason = reason

    @property
    def priority(self) -> str:
        return self._priority

    @property
    def action(self) -> str:
        return self._action

    @property
    def reason(self) -> str:
        return self._reason

    @abstractmethod
    def matches(self, severity: str, operational_impact: str, score: int) -> bool:
        """Inputs are lower-case, stripped strings and the total score."""
        pass
