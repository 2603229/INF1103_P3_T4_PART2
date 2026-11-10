from typing import Any

from .scorer import Scorer


class TableScorer(Scorer):
    """
    ABSTRACT BASE CLASS for scorers that map a text field to points via a
    lookup table.
    """

    _FIELD: str = ""
    _DEFAULT: str = ""
    _POINTS: dict[str, int] = {}
    _UNKNOWN_POINTS = 1

    def score(self, record: dict[str, Any]) -> int:
        value = str(record.get(self._FIELD, self._DEFAULT)).strip().lower()
        return self._POINTS.get(value, self._UNKNOWN_POINTS)