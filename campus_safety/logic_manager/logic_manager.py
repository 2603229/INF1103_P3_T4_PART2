from typing import Any, Optional

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
    ) -> None:
        self._evaluator = evaluator if evaluator is not None else PriorityEvaluator()
        self._sorter = sorter if sorter is not None else SeveritySorter()
        self._matcher = matcher

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
