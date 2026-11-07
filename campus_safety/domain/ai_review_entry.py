"""Immutable human-review record for an existing Gemini AI assessment.

A review does not overwrite the original AI assessment or recalculate priority.
Reporter/reviewer names are manually entered; no authentication is implied.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from campus_safety.domain.invalid_record import InvalidRecord

REVIEW_DECISIONS = (
    "Accepted",
    "Flagged as Incorrect",
    "Further Review Requested",
)


@dataclass(frozen=True, slots=True)
class AIReviewEntry:
    """A validated, immutable review and its attribution as supplied by the user."""

    incident_id: str
    reviewer: str
    decision: str
    reason: str
    reviewed_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.incident_id, str) or not self.incident_id.strip():
            raise InvalidRecord("AI review requires an incident ID")
        if not isinstance(self.reviewer, str) or not 2 <= len(self.reviewer.strip()) <= 100:
            raise InvalidRecord("Reviewer name must be 2–100 characters")
        if not isinstance(self.decision, str) or self.decision not in REVIEW_DECISIONS:
            raise InvalidRecord("Invalid AI review decision")
        if not isinstance(self.reason, str) or not 1 <= len(self.reason.strip()) <= 500:
            raise InvalidRecord("AI review reason must be 1–500 characters")
        if any("\x00" in value for value in (self.reviewer, self.reason)):
            raise InvalidRecord("AI review contains an invalid control character")
        if not isinstance(self.reviewed_at, str):
            raise InvalidRecord("AI review requires a timestamp")
        try:
            timestamp = datetime.fromisoformat(self.reviewed_at)
        except ValueError as exc:
            raise InvalidRecord("Invalid AI review timestamp") from exc
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise InvalidRecord("AI review timestamp must include a timezone")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AIReviewEntry":
        if not isinstance(value, Mapping):
            raise InvalidRecord("AI review history must contain objects")
        required = {"incident_id", "reviewer", "decision", "reason", "reviewed_at"}
        if set(value) != required:
            raise InvalidRecord("AI review entry has missing or unexpected fields")
        return cls(**{key: value[key] for key in required})

    def as_dict(self) -> dict[str, str]:
        return {
            "incident_id": self.incident_id,
            "reviewer": self.reviewer.strip(),
            "decision": self.decision,
            "reason": self.reason.strip(),
            "reviewed_at": self.reviewed_at,
        }
