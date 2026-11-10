from typing import Any, Optional

from .critical_rule import CriticalRule
from .high_rule import HighRule
from .priority_rule import PriorityRule
from .router import Router
from .score_calculator import ScoreCalculator
from .standard_rule import StandardRule


class PriorityEvaluator:
    """
    Decides final priority, action and route.
    """

    def __init__(
        self,
        rules: Optional[list[PriorityRule]] = None,
        router: Optional[Router] = None,
    ) -> None:
        self._rules = rules if rules is not None else [
            CriticalRule(),
            HighRule(),
            StandardRule(),
        ]
        if not self._rules:
            raise ValueError("At least one PriorityRule is required")
        self._router = router if router is not None else Router()
        self._calculator = ScoreCalculator()  

    def score_breakdown(self, record: dict[str, Any]) -> dict[str, int]:
        return self._calculator.breakdown(record)

    def score(self, record: dict[str, Any]) -> int:
        return self._calculator.total(record)

    def route(self, priority: str) -> str:
        return self._router.route(priority)

    def evaluate(self, record: dict[str, Any]) -> dict[str, Any]:
        severity = str(record.get("severity", "Low")).strip().lower()
        impact = str(record.get("operational_impact", "Minor")).strip().lower()

        breakdown = self._calculator.breakdown(record)
        total = sum(breakdown.values())

        chosen = next(
            (r for r in self._rules if r.matches(severity, impact, total)),
            self._rules[-1],
        )

        return {
            "priority": chosen.priority,
            "score": total,
            "action": chosen.action,
            "reason": chosen.reason,
            "route": self._router.route(chosen.priority),
            "score_breakdown": breakdown,
        }
