from typing import Any

from .frequency_scorer import FrequencyScorer
from .impact_scorer import ImpactScorer
from .scorer import Scorer
from .severity_scorer import SeverityScorer


class ScoreCalculator:
    """
    Combines the individual scorers into a total score.
    """

    def __init__(self) -> None:
        self._scorers: list[Scorer] = [
            SeverityScorer(),
            ImpactScorer(),
            FrequencyScorer(),
        ]

    def breakdown(self, record: dict[str, Any]) -> dict[str, int]:
        return {scorer.name: scorer.score(record) for scorer in self._scorers}

    def total(self, record: dict[str, Any]) -> int:
        return sum(self.breakdown(record).values())