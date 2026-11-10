from .priority_rule import PriorityRule


class CriticalRule(PriorityRule):
    """Critical severity combined with severe/catastrophic impact."""

    def __init__(self) -> None:
        super().__init__(
            priority="Critical",
            action="Immediate Emergency Dispatch",
            reason=(
                "Critical severity combined with severe "
                "or catastrophic operational impact."
            ),
        )

    def matches(self, severity: str, operational_impact: str, score: int) -> bool:
        return severity == "critical" and operational_impact in (
            "severe",
            "catastrophic",
        )
