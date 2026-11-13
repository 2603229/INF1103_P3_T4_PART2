from typing import Any


class SeveritySorter:
    """Sorts incidents Critical -> High -> Medium -> Low"""

    _ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    _UNKNOWN_RANK = 4

    def sort(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(records, key=self._rank)

    def _rank(self, record: dict[str, Any]) -> int:
        severity = str(record.get("severity", "Low")).strip().lower()
        return self._ORDER.get(severity, self._UNKNOWN_RANK)