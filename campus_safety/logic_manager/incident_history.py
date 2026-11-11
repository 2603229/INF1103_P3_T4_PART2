from typing import Any, Optional

from .fuzzy_matcher import FuzzyMatcher
from .text_matcher import TextMatcher


class IncidentHistory:
    _CLOSED = ("resolved", "closed")

    def __init__(
        self,
        existing_records: list[dict[str, Any]],
        matcher: Optional[TextMatcher] = None,
    ) -> None:
        self._records = existing_records
        self._matcher = matcher if matcher is not None else FuzzyMatcher()

    def _same_place_and_asset(self, a: dict[str, Any], b: dict[str, Any]) -> bool:
        return (
            self._matcher.matches(a.get("location"), b.get("location"))
            and self._matcher.matches(a.get("asset_info"), b.get("asset_info"))
        )

    def _is_closed(self, record: dict[str, Any]) -> bool:
        return TextMatcher.normalise(record.get("status")) in self._CLOSED

    def frequency(self, record: dict[str, Any]) -> int:
        """Count previous resolved/closed incidents at the same location + asset."""
        return sum(
            1
            for existing in self._records
            if self._same_place_and_asset(record, existing) and self._is_closed(existing)
        )

    def find_duplicate(self, record: dict[str, Any]) -> str:
        """Return 'Unique' or 'Potential Duplicate of <id>'."""
        # Missing fields must not create false matches
        if not TextMatcher.normalise(record.get("location")) or not TextMatcher.normalise(
            record.get("asset_info")
        ):
            return "Unique"

        for existing in self._records:
            if self._same_place_and_asset(record, existing) and not self._is_closed(existing):
                return f"Potential Duplicate of {existing.get('incident_id')}"
        return "Unique"
