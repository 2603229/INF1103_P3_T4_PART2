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

    # Verify the model response is an object with exactly the expected five fields and legal enumerations.
    # Strict validation prevents untrusted output from manipulating downstream decisions.
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AIAssessment":
        if not isinstance(value, Mapping):
            raise InvalidRecord("AI response must be a JSON object")
        # The Gemini prompt requests exactly five string keys. Fail closed if the
        # model adds, omits or changes any of them rather than silently accepting
        # an output that violates the requested schema.
        if set(value) != set(AI_FIELDS):
            raise InvalidRecord("AI response has missing or unexpected fields")
        if any(not isinstance(value[key], str) for key in AI_FIELDS):
            raise InvalidRecord("AI response fields must be strings")
        normalized = {key: value[key].strip() for key in AI_FIELDS}
        if any(not text for text in normalized.values()):
            raise InvalidRecord("AI response fields must contain nonempty text")
        if normalized["category"] not in VALID_CATEGORIES:
            raise InvalidRecord("Invalid AI hazard category")
        if normalized["severity"] not in VALID_SEVERITIES:
            raise InvalidRecord("Invalid AI severity")
        if normalized["operational_impact"] not in VALID_IMPACTS:
            raise InvalidRecord("Invalid AI operational impact")
        return cls(*(normalized[key] for key in AI_FIELDS))

    # Convert an immutable validated assessment to the Phase 1-compatible field mapping.
    def as_dict(self) -> dict[str, str]:
        return {key: getattr(self, key) for key in AI_FIELDS}
