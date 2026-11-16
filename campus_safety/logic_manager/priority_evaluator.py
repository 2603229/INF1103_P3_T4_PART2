# FILE GUIDE: Decides the final priority, action, reason and dispatch queue for one record.
# Rules are checked in order (Critical -> High -> Normal); the last rule is the fallback.

"""Priority evaluator."""
from typing import Any, Optional

from .score_calculator import ScoreCalculator


class PriorityEvaluator:
    """Score a record, pick its priority rule and route it to a queue."""

    _DEFAULT_QUEUES = {
        "critical": "Urgent Emergency Dispatch",
        "high": "Priority Maintenance Queue",
    }
    _DEFAULT_QUEUE = "Standard Maintenance Queue"

    def __init__(
        self,
        calculator: Optional[ScoreCalculator] = None,
        high_score_threshold: int = 7,
        queues: Optional[dict[str, str]] = None,
        default_queue: Optional[str] = None,
    ) -> None:
        """Create an evaluator.

        Args:
            calculator: Produces the score and its breakdown (injected).
            high_score_threshold: Score at or above which a record is High.
            queues: Priority -> queue mapping; keys are case-insensitive.
            default_queue: Queue for any priority not in the mapping.
        """
        self.__calculator = calculator if calculator is not None else ScoreCalculator()
        self.__high_score_threshold = high_score_threshold
        source = queues if queues is not None else self._DEFAULT_QUEUES
        self.__queues = {self._key(k): v for k, v in source.items()}
        self.__default_queue = default_queue or self._DEFAULT_QUEUE
        # (priority, action, reason, test) in the order they are checked.
        self.__rules = (
            (
                "Critical",
                "Immediate Emergency Dispatch",
                "Critical severity combined with severe or catastrophic operational impact.",
                self._is_critical,
            ),
            (
                "High",
                "Priority Maintenance",
                "Hazard severity, operational impact, or priority score requires urgent attention.",
                self._is_high,
            ),
            (
                "Normal",
                "Standard Maintenance",
                "Hazard does not meet the criteria for urgent escalation.",
                self._is_standard,
            ),
        )

    @staticmethod
    def _key(priority: str) -> str:
        return str(priority).strip().lower()

    @staticmethod
    def _is_critical(severity: str, impact: str, score: int) -> bool:
        return severity == "critical" and impact in ("severe", "catastrophic")

    def _is_high(self, severity: str, impact: str, score: int) -> bool:
        return (
            severity in ("high", "critical")
            or impact in ("severe", "catastrophic")
            or score >= self.__high_score_threshold
        )

    @staticmethod
    def _is_standard(severity: str, impact: str, score: int) -> bool:
        return True  # fallback: matches anything not escalated earlier

    def score_breakdown(self, record: dict[str, Any]) -> dict[str, int]:
        return self.__calculator.breakdown(record)

    def score(self, record: dict[str, Any]) -> int:
        return self.__calculator.total(record)

    def route(self, priority: str) -> str:
        """Return the dispatch queue for a priority label."""
        return self.__queues.get(self._key(priority), self.__default_queue)

    def evaluate(self, record: dict[str, Any]) -> dict[str, Any]:
        """Return priority, score, action, reason, route and score breakdown."""
        severity = self._key(record.get("severity", "Low"))
        impact = self._key(record.get("operational_impact", "Minor"))

        breakdown = self.__calculator.breakdown(record)
        total = sum(breakdown.values())

        priority, action, reason, _ = next(
            (rule for rule in self.__rules if rule[3](severity, impact, total)),
            self.__rules[-1],
        )
        return {
            "priority": priority,
            "score": total,
            "action": action,
            "reason": reason,
            "route": self.route(priority),
            "score_breakdown": breakdown,
        }
