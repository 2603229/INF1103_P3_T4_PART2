# FILE GUIDE: Looks through existing incidents to count past failures and spot open duplicates.
# The TextMatcher is injected, so matching strictness can change without editing this class.

"""Incident history."""
from typing import Any, Optional

from .text_matcher import TextMatcher


class IncidentHistory:
    """Historical frequency and duplicate detection over existing records."""

    _CLOSED = ("resolved", "closed")

    def __init__(
        self,
        existing_records: list[dict[str, Any]],
        matcher: Optional[TextMatcher] = None,
    ) -> None:
        """Create a history view.

        Args:
            existing_records: Previously saved incident records.
            matcher: Decides whether two locations/assets match; defaults to TextMatcher().
        """
        self.__records = existing_records
        self.__matcher = matcher if matcher is not None else TextMatcher()

    @staticmethod
    def _has_identity(record: dict[str, Any]) -> bool:
        """Location and asset must both be present, or blanks would match each other."""
        return bool(TextMatcher.normalise(record.get("location"))) and bool(
            TextMatcher.normalise(record.get("asset_info"))
        )

    @staticmethod
    def _is_same_incident(a: dict[str, Any], b: dict[str, Any]) -> bool:
        incident_id = a.get("incident_id")
        return incident_id is not None and incident_id == b.get("incident_id")

    def _same_place_and_asset(self, a: dict[str, Any], b: dict[str, Any]) -> bool:
        return self.__matcher.matches(
            a.get("location"), b.get("location")
        ) and self.__matcher.matches(a.get("asset_info"), b.get("asset_info"))

    def _is_closed(self, record: dict[str, Any]) -> bool:
        return TextMatcher.normalise(record.get("status")) in self._CLOSED

    def frequency(self, record: dict[str, Any]) -> int:
        """Count previous resolved/closed incidents at the same location + asset."""
        if not self._has_identity(record):
            return 0
        return sum(
            1
            for existing in self.__records
            if not self._is_same_incident(record, existing)
            and self._same_place_and_asset(record, existing)
            and self._is_closed(existing)
        )

    def find_duplicate(self, record: dict[str, Any]) -> str:
        """Return 'Unique' or 'Potential Duplicate of <id>'."""
        if not self._has_identity(record):
            return "Unique"
        for existing in self.__records:
            if self._is_same_incident(record, existing):
                continue  # never flag a record as a duplicate of itself
            if self._same_place_and_asset(record, existing) and not self._is_closed(existing):
                return f"Potential Duplicate of {existing.get('incident_id')}"
        return "Unique"
