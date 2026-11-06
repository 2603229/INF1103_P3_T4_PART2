# FILE GUIDE: Immutable decision outcome: final priority, score, route, rationale and breakdown.
# Keeps risk-policy output explicit rather than passing unrelated dict keys between managers.
# Comments explain responsibilities and design; executable statements are unchanged.

"""Immutable priority decision value object."""
from __future__ import annotations
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


# Value object returned by risk policies with priority, route and scoring detail.
# Allows the workflow to apply decisions without knowing policy implementation internals.
@dataclass(frozen=True)
class Decision:
    priority: str
    score: int
    action: str
    reason: str
    route: str
    score_breakdown: Mapping[str, int]

    # Validate or normalise decision details after dataclass construction.
    def __post_init__(self) -> None:
        # A frozen dataclass is not enough if it contains a mutable dict.
        object.__setattr__(self, "score_breakdown",
                           MappingProxyType(dict(self.score_breakdown)))
