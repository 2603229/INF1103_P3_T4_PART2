from abc import ABC, abstractmethod
from typing import Any


class Scorer(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def score(self, record: dict[str, Any]) -> int:
        pass
