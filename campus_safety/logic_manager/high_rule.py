from .priority_rule import PriorityRule


class HighRule(PriorityRule):
    """High/critical severity, severe/catastrophic impact, or score >= threshold."""

    def __init__(self, score_threshold: int = 7) -> None:
        super().__init__(
            priority="High",
            action="Priority Maintenance",
            reason=(
                "Hazard severity, operational impact, or "
                "priority score requires urgent attention."
            ),
        )
        self._score_threshold = score_threshold

    def matches(self, severity: str, operational_impact: str, score: int) -> bool:
        return (
            severity in ("high", "critical")
            or operational_impact in ("severe", "catastrophic")
            or score >= self._score_threshold
        )
