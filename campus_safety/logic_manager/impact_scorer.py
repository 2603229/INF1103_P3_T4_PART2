from .table_scorer import TableScorer


class ImpactScorer(TableScorer):
    """Points for the AI-generated operational impact."""

    _FIELD = "operational_impact"
    _DEFAULT = "Minor"
    _POINTS = {"minor": 1, "moderate": 2, "severe": 4, "catastrophic": 5}

    @property
    def name(self) -> str:
        return "operational_impact"