from typing import Any

from .scorer import Scorer


class FrequencyScorer(Scorer):
    """Points for how often this location/asset has failed before."""

    # (minimum count, points), checked highest first
    _THRESHOLDS = ((5, 3), (2, 2), (1, 1))

    @property
    def name(self) -> str:
        return "historical_frequency"

    def score(self, record: dict[str, Any]) -> int:
        try:
            frequency = max(0, int(record.get("historical_frequency", 0)))
        except (TypeError, ValueError):
            frequency = 0

        for minimum, points in self._THRESHOLDS:
            if frequency >= minimum:
                return points
        return 0