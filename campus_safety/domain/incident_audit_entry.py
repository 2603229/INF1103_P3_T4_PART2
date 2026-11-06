# FILE GUIDE: Immutable status-change value object recording incident ID, old/new status, reason and time.
# Validation prevents malformed or unrelated history entries from entering storage.
# Comments explain responsibilities and design; executable statements are unchanged.

"""Immutable domain value for a single incident status change.

Each class is declared in its own file to follow the lecturer's requirement.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping
from campus_safety.domain.invalid_record import InvalidRecord
from campus_safety.domain.schema import VALID_STATUSES


# Validated, immutable representation of one status transition.
# Serialized values persist with the incident record across application restarts.
@dataclass(frozen=True, slots=True)
class IncidentAuditEntry:
    """An append-only snapshot of one status transition, not a mutable incident.

    The timestamp is timezone-aware ISO 8601; a missing previous status means
    that the incident has just been created. Attribution is intentionally not
    claimed because the current dashboard has no login/authentication.
    """

    incident_id: str
    previous_status: str | None
    new_status: str
    changed_at: str
    reason: str

    # Validate required values and status changes immediately after constructing an immutable event.
    def __post_init__(self) -> None:
        if not isinstance(self.incident_id, str) or not self.incident_id.strip():
            raise InvalidRecord("Audit entry requires an incident ID")
        if self.previous_status is not None and self.previous_status not in VALID_STATUSES:
            raise InvalidRecord("Audit entry has an invalid previous status")
        if self.new_status not in VALID_STATUSES:
            raise InvalidRecord("Audit entry has an invalid new status")
        if self.previous_status == self.new_status:
            raise InvalidRecord("An audit entry must describe an actual status change")
        if not isinstance(self.reason, str) or not (1 <= len(self.reason.strip()) <= 500):
            raise InvalidRecord("Status-change reason must be 1–500 characters")
        if not isinstance(self.changed_at, str):
            raise InvalidRecord("Audit entry requires a timestamp")
        try:
            moment = datetime.fromisoformat(self.changed_at)
        except ValueError as exc:
            raise InvalidRecord("Audit timestamp is invalid") from exc
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise InvalidRecord("Audit timestamp must include a timezone")

    # Reconstruct an audit value from stored JSON/SQLite mapping and validate its shape.
    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "IncidentAuditEntry":
        if not isinstance(data, Mapping):
            raise InvalidRecord("Audit history contains a non-object entry")
        fields = ("incident_id", "previous_status", "new_status", "changed_at", "reason")
        if set(data) != set(fields):
            raise InvalidRecord("Audit history entry has missing or unexpected fields")
        return cls(**{field: data[field] for field in fields})

    # Export a plain dictionary suitable for JSON and SQLite persistence.
    def as_dict(self) -> dict[str, str | None]:
        return {
            "incident_id": self.incident_id,
            "previous_status": self.previous_status,
            "new_status": self.new_status,
            "changed_at": self.changed_at,
            "reason": self.reason,
        }
