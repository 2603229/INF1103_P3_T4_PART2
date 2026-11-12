from typing import Any, Optional

from campus_safety.domain.facility_summary_report import FacilitySummaryReport

from .facility_summary_builder import FacilitySummaryBuilder
from .incident_history import IncidentHistory
from .priority_evaluator import PriorityEvaluator
from .severity_sorter import SeveritySorter
from .text_matcher import TextMatcher


class LogicManager:
    def __init__(
        self,
        evaluator: Optional[PriorityEvaluator] = None,
        sorter: Optional[SeveritySorter] = None,
        matcher: Optional[TextMatcher] = None,
        summary_builder: Optional[FacilitySummaryBuilder] = None,
    ) -> None:
        self._evaluator = evaluator if evaluator is not None else PriorityEvaluator()
        self._sorter = sorter if sorter is not None else SeveritySorter()
        self._matcher = matcher
        self._summary_builder = (
            summary_builder if summary_builder is not None else FacilitySummaryBuilder()
        )

    #Scoring, evaluation and routing 
    def calculate_score_breakdown(self, record: dict[str, Any]) -> dict[str, int]:
        return self._evaluator.score_breakdown(record)

    def score(self, record: dict[str, Any]) -> int:
        """Numerical priority score (higher means more urgent)."""
        return self._evaluator.score(record)

    def evaluate(self, record: dict[str, Any]) -> dict[str, Any]:
        return self._evaluator.evaluate(record)

    def route(self, record: dict[str, Any]) -> str:
        return self._evaluator.route(str(record.get("priority", "Normal")))

    # History and ordering 
    def calculate_historical_frequency(
        self, record: dict[str, Any], existing_records: list[dict[str, Any]]
    ) -> int:
        return IncidentHistory(existing_records, self._matcher).frequency(record)

    def check_duplicate(
        self, new_record: dict[str, Any], existing_records: list[dict[str, Any]]
    ) -> str:
        return IncidentHistory(existing_records, self._matcher).find_duplicate(new_record)

    def sort_incidents_by_severity(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return self._sorter.sort(records)

    # Facilities reporting
    def generate_facilities_summary(
        self, records: list[dict[str, Any]]
    ) -> FacilitySummaryReport:
        """Active-hazard workload metrics for facilities management."""
        return self._summary_builder.build(records)
