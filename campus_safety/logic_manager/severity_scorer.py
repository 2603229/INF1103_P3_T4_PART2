from table_scorer import TableScorer


class SeverityScorer(TableScorer):
    """Points for the AI-supplied severity."""

    _FIELD = "severity"
    _DEFAULT = "Low"
    _POINTS = {"low": 1, "medium": 2, "high": 4, "critical": 5}

    @property
    def name(self) -> str:
        return "severity"
