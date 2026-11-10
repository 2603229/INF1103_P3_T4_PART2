from typing import Any


class SeveritySorter:
    """Sorts incidents Critical -> High -> Medium -> Low."""

    _ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    _UNKNOWN_RANK = 4

    def sort(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            records,
            key=lambda r: self._ORDER.get(str(r.get("severity", "Low")), self._UNKNOWN_RANK),
        )
