# FILE GUIDE: Facade for the Logic Manager component: applies business rules to AI-enriched records.
# Delegates to focused collaborators, which are injected (defaults provided) so they can be replaced.

"""Logic Manager."""
from typing import Any, Optional

from campus_safety.domain.facility_summary_report import FacilitySummaryReport

from .incident_history import IncidentHistory
from .incident_reporter import IncidentReporter
from .priority_evaluator import PriorityEvaluator
from .text_matcher import TextMatcher


class LogicManager:
    """Evaluate records, calculate scores, and route/classify outcomes."""

    def __init__(
        self,
        evaluator: Optional[PriorityEvaluator] = None,
        matcher: Optional[TextMatcher] = None,
        reporter: Optional[IncidentReporter] = None,
    ) -> None:
        self.__evaluator = evaluator if evaluator is not None else PriorityEvaluator()
        self.__matcher = matcher  # None -> IncidentHistory uses its default TextMatcher
        self.__reporter = reporter if reporter is not None else IncidentReporter()

    # Scoring, evaluation and routing
    def calculate_score_breakdown(self, record: dict[str, Any]) -> dict[str, int]:
        return self.__evaluator.score_breakdown(record)

    def score(self, record: dict[str, Any]) -> int:
        """Numerical priority score (higher means more urgent)."""
        return self.__evaluator.score(record)

    def evaluate(self, record: dict[str, Any]) -> dict[str, Any]:
        return self.__evaluator.evaluate(record)

    def route(self, record: dict[str, Any]) -> str:
        return self.__evaluator.route(str(record.get("priority", "Normal")))

    # History and ordering
    def calculate_historical_frequency(
        self, record: dict[str, Any], existing_records: list[dict[str, Any]]
    ) -> int:
        return IncidentHistory(existing_records, self.__matcher).frequency(record)

    def check_duplicate(
        self, new_record: dict[str, Any], existing_records: list[dict[str, Any]]
    ) -> str:
        return IncidentHistory(existing_records, self.__matcher).find_duplicate(new_record)

    def sort_incidents_by_severity(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return self.__reporter.sort_by_severity(records)

    # Facilities reporting
    def generate_facilities_summary(
        self, records: list[dict[str, Any]]
    ) -> FacilitySummaryReport:
        """Active-hazard workload metrics for facilities management."""
        return self.__reporter.build_summary(records)
