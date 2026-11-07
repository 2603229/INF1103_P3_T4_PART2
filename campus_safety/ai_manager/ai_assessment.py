# FILE GUIDE: Validated five-field AI result value object; only expected category/severity/impact labels are accepted.
# Reject invalid provider output before the Logic Manager uses it in routing decisions.

"""Validated AI assessment value object."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
from campus_safety.domain.invalid_record import InvalidRecord
from campus_safety.domain.schema import AI_FIELDS, VALID_CATEGORIES, VALID_SEVERITIES, VALID_IMPACTS


# Typed and validated AI output that may be used by risk scoring.
# Never allow arbitrary model JSON keys or unrecognised risk enums into the domain.
@dataclass(frozen=True)
class AIAssessment:
    risk_summary: str
    category: str
    severity: str
    operational_impact: str
    contextual_insights: str

    # Validate every assessment, including directly constructed objects.
    # This prevents invalid AI values from bypassing from_mapping().
    def __post_init__(self) -> None:
        for field in AI_FIELDS:
            value = getattr(self, field)

            if not isinstance(value, str):
                raise InvalidRecord("AI response fields must be strings")

            normalized = value.strip()

            if not normalized:
                raise InvalidRecord(
                    "AI response fields must contain nonempty text"
                )

            # Normalize fields in the frozen dataclass during initialization.
            object.__setattr__(self, field, normalized)

        if self.category not in VALID_CATEGORIES:
            raise InvalidRecord("Invalid AI hazard category")

        if self.severity not in VALID_SEVERITIES:
            raise InvalidRecord("Invalid AI severity")

        if self.operational_impact not in VALID_IMPACTS:
            raise InvalidRecord("Invalid AI operational impact")

    # Verify the model response is an object with exactly five expected fields.
    # Field validation is handled by __post_init__().
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AIAssessment":
        if not isinstance(value, Mapping):
            raise InvalidRecord("AI response must be a JSON object")

        # Reject missing or unexpected fields.
        if set(value) != set(AI_FIELDS):
            raise InvalidRecord("AI response has missing or unexpected fields")

        # Creating an AIAssessment automatically calls __post_init__().
        return cls(*(value[key] for key in AI_FIELDS))

    # Convert an immutable validated assessment to the Phase 1-compatible field mapping.
    def as_dict(self) -> dict[str, str]:
        return {key: getattr(self, key) for key in AI_FIELDS}
