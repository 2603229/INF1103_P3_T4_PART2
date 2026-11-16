# FILE GUIDE: Calculates the priority score from severity, operational impact and historical frequency.
# Returns both a per-factor breakdown and the total (higher means more urgent).

"""Score calculator."""
from typing import Any


class ScoreCalculator:
    """Turn a record into points for severity, impact and past failures."""

    _SEVERITY_POINTS = {"low": 1, "medium": 2, "high": 4, "critical": 5}
    _IMPACT_POINTS = {"minor": 1, "moderate": 2, "severe": 4, "catastrophic": 5}
    _UNKNOWN_POINTS = 1
    # (minimum past failures, points), checked highest first
    _FREQUENCY_THRESHOLDS = ((5, 3), (2, 2), (1, 1))

    @staticmethod
    def _lookup(table: dict[str, int], record: dict[str, Any], field: str, default: str) -> int:
        value = str(record.get(field, default)).strip().lower()
        return table.get(value, ScoreCalculator._UNKNOWN_POINTS)

    def _severity_points(self, record: dict[str, Any]) -> int:
        return self._lookup(self._SEVERITY_POINTS, record, "severity", "Low")

    def _impact_points(self, record: dict[str, Any]) -> int:
        return self._lookup(self._IMPACT_POINTS, record, "operational_impact", "Minor")

    def _frequency_points(self, record: dict[str, Any]) -> int:
        try:
            frequency = max(0, int(record.get("historical_frequency", 0)))
        except (TypeError, ValueError):
            frequency = 0
        for minimum, points in self._FREQUENCY_THRESHOLDS:
            if frequency >= minimum:
                return points
        return 0

    def breakdown(self, record: dict[str, Any]) -> dict[str, int]:
        """Points from each factor."""
        return {
            "severity": self._severity_points(record),
            "operational_impact": self._impact_points(record),
            "historical_frequency": self._frequency_points(record),
        }

    def total(self, record: dict[str, Any]) -> int:
        """Sum of all factor points."""
        return sum(self.breakdown(record).values())
