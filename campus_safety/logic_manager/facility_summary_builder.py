from collections import Counter
from typing import Any

from campus_safety.domain.facility_summary_report import FacilitySummaryReport

from .text_matcher import TextMatcher


class FacilitySummaryBuilder:
    """
    Aggregates incident records into facilities-management metrics.

    Only active incidents count: Resolved/Closed hazards are no longer part of
    the maintenance workload.
    """

    _CLOSED = ("resolved", "closed")
    _PENDING = "pending review"
    _IN_PROGRESS = "in progress"
    _URGENT_PRIORITIES = ("critical", "high", "urgent")

    def build(self, records: list[dict[str, Any]]) -> FacilitySummaryReport:
        active = [r for r in records if self._status(r) not in self._CLOSED]
        return FacilitySummaryReport(
            total_active_hazards=len(active),
            pending_repair_count=sum(1 for r in active if self._status(r) == self._PENDING),
            in_progress_count=sum(1 for r in active if self._status(r) == self._IN_PROGRESS),
            urgent_hazard_count=sum(1 for r in active if self._is_urgent(r)),
            hazards_by_location=self._count(active, "location"),
            hazards_by_category=self._count(active, "category"),
        )

    @staticmethod
    def _status(record: dict[str, Any]) -> str:
        # Legacy records without a status are treated as Pending Review.
        return TextMatcher.normalise(record.get("status") or "Pending Review")

    def _is_urgent(self, record: dict[str, Any]) -> bool:
        # Saved incidents store "final_priority"; simpler records may use "priority".
        priority = record.get("final_priority") or record.get("priority")
        return TextMatcher.normalise(priority) in self._URGENT_PRIORITIES

    @staticmethod
    def _count(records: list[dict[str, Any]], field: str) -> dict[str, int]:
        return dict(Counter(str(r.get(field) or "Unknown").strip() or "Unknown" for r in records))
