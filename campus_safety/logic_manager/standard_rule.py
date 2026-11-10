from .priority_rule import PriorityRule


class StandardRule(PriorityRule):
    """Default rule: matches anything not escalated by an earlier rule."""

    def __init__(self) -> None:
        super().__init__(
            priority="Normal",
            action="Standard Maintenance",
            reason="Hazard does not meet the criteria for urgent escalation.",
        )

    def matches(self, severity: str, operational_impact: str, score: int) -> bool:
        return True
