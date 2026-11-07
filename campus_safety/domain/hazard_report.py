# FILE GUIDE: Core hazard record with validated construction, defensive copies and status-transition rules.
# It preserves legacy Phase 1 fields while protecting new audit-history integrity.

"""Encapsulated hazard report domain entity."""
from __future__ import annotations
from datetime import datetime, timezone
from copy import deepcopy
from typing import Any, Mapping
import re
from campus_safety.ai_manager.ai_assessment import AIAssessment
from campus_safety.domain.incident_audit_entry import IncidentAuditEntry
from campus_safety.domain.ai_review_entry import AIReviewEntry
from campus_safety.domain.decision import Decision
from campus_safety.domain.invalid_record import InvalidRecord
from campus_safety.domain.schema import SCHEMA_FIELDS, VALID_STATUSES


# Encapsulated record model; deepcopy protects its private field dictionary.
# The model validates input, applies AI decisions and enforces status-history invariants.
class HazardReport:
    """Encapsulates one report; exposes copies instead of mutable internal data.

    Phase 1 used dictionaries throughout. Here the record is a domain object,
    while JSON serialization remains compatible with the existing dashboard.
    """

    # Deep-copy input dictionaries to prevent callers changing nested internal state.
    def __init__(self, fields: Mapping[str, Any]) -> None:
        # Defensive copy is essential: caller mutations must never bypass validation.
        self._fields: dict[str, Any] = deepcopy(dict(fields))

    # Normalize and validate reporter, contact, location, headcount, asset and description.
    # Return a report only after all input requirements pass.
    @classmethod
    def from_input(cls, fields: Mapping[str, Any]) -> "HazardReport":
        name = str(fields.get("reporter_name") or "").strip()
        contact = str(fields.get("reporter_contact") or "").strip()
        location = str(fields.get("location") or "").strip()
        asset = str(fields.get("asset_info") or "").strip()
        desc = str(fields.get("description") or "").strip()
        try:
            people = int(fields.get("impact_headcount"))
        except (ValueError, TypeError) as exc:
            raise InvalidRecord("Headcount must be a whole number") from exc
        if not re.fullmatch(r"[A-Za-z\s'.-]+", name):
            raise InvalidRecord("Reporter name contains invalid characters")
        if not (re.fullmatch(r"[A-Za-z0-9]+@sit\.singaporetech\.edu\.sg", contact, re.I)
                or re.fullmatch(r"[689]\d{7}", contact)):
            raise InvalidRecord("Contact must be a SIT email or valid 8-digit number")
        if not location or not 1 <= people <= 1000 or len(asset) < 3 or len(desc) < 15:
            raise InvalidRecord("Location, headcount, asset or description is invalid")
        clean = dict(fields)
        clean.update(reporter_name=name, reporter_contact=contact, location=location,
                     impact_headcount=people, asset_info=asset, description=desc)
        clean["image_path"] = str(clean.pop("image_patch", clean.get("image_path", "")) or "")
        return cls(clean)

    # Reconstruct legacy records without reapplying new-report input validation.
    # Validate any audit history that does exist to avoid accepting corrupt stored data.
    @classmethod
    def from_storage(cls, fields: Mapping[str, Any]) -> "HazardReport":
        # Historical Phase 1 rows may have missing fields; do not reject on load.
        report = cls(fields)
        report.status_history()  # Reject malformed audit history without damaging the database.
        report.ai_review_history()  # Reject malformed human-review history too.
        return report

    # Expose deep copies so callers cannot mutate nested fields without going through domain methods.
    def get(self, name: str, default: Any = None) -> Any:
        """Read a field without exposing references to mutable internal values.

        A nested dict/list obtained through ``get()`` must not let callers
        change a report without using its public domain methods. For missing
        fields, preserve dict.get()'s normal default-value behaviour.
        """
        if name not in self._fields:
            return default
        return deepcopy(self._fields[name])

    # Return the stable incident ID as a string, even for older records.
    @property
    def incident_id(self) -> str:
        return str(self.get("incident_id") or "")

    # Use Pending Review for legacy records that omitted an explicit status.
    @property
    def status(self) -> str:
        return str(self.get("status") or "Pending Review")

    # Expose normalized location for duplicate and frequency logic.
    @property
    def location(self) -> str:
        return str(self.get("location") or "")

    # Expose asset/category text without the caller reaching private storage.
    @property
    def asset_info(self) -> str:
        return str(self.get("asset_info") or "")

    # Apply already-validated AI fields and mark the authentic assessment source.
    def attach_assessment(self, assessment: AIAssessment) -> None:
        self._fields.update(assessment.as_dict())
        self._fields["assessment_source"] = "Gemini AI"

    # Store the risk score, priority, routing decision, historical count and duplicate result.
    def apply_decision(self, decision: Decision, historical_frequency: int,
                       duplicate_check: str) -> None:
        self._fields.update(historical_frequency=historical_frequency,
                            is_duplicate=duplicate_check, priority_score=decision.score,
                            final_priority=decision.priority, recommended_action=decision.action,
                            escalation_reason=decision.reason, assigned_route=decision.route)

    # Store the nonnegative recurrence count used by the risk policy.
    def set_historical_frequency(self, count: int) -> None:
        if count < 0:
            raise InvalidRecord("Historical frequency cannot be negative")
        self._fields["historical_frequency"] = count

    # Keep a resolved image path for Gemini; it is intentionally never serialized.
    def set_runtime_image_path(self, image_path: str) -> None:
        self._fields["visual_evidence_path"] = image_path

    # Assign the incident ID and initial status exactly once, with a creation audit event.
    def assign_identity(self, incident_id: str) -> None:
        if self.incident_id:
            raise InvalidRecord("An existing incident ID cannot be reassigned")
        self._fields["incident_id"] = incident_id
        self._fields["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._fields["status"] = "Pending Review"
        # Create the first entry only for NEW incidents, not imported Phase 1 rows.
        self._append_audit(None, "Pending Review", "Incident created")

    # Build a validated immutable IncidentAuditEntry and append its serialized representation.
    def _append_audit(self, previous_status: str | None,
                      new_status: str, reason: str) -> None:
        entry = IncidentAuditEntry(
            incident_id=self.incident_id,
            previous_status=previous_status,
            new_status=new_status,
            changed_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            reason=reason.strip() if isinstance(reason, str) else reason,
        )
        current_history = self.status_history()  # Validate before modifying.
        self._fields["status_history"] = [
            *[existing.as_dict() for existing in current_history], entry.as_dict()
        ]

    # Parse and validate history entries, including incident-ID ownership.
    def status_history(self) -> list[IncidentAuditEntry]:
        """Return validated immutable audit values; existing Phase 1 rows have none."""
        raw = self._fields.get("status_history", [])
        if not isinstance(raw, list):
            raise InvalidRecord("Incident status_history must be a list")
        entries = [IncidentAuditEntry.from_mapping(item) for item in raw]
        if any(item.incident_id != self.incident_id for item in entries):
            raise InvalidRecord("Audit entry belongs to a different incident")
        # Phase 1 incidents may have no creation event. However, once events
        # exist, every later event must continue from the prior event's status.
        # Otherwise a damaged or manually edited history could look authentic.
        for earlier, later in zip(entries, entries[1:]):
            if later.previous_status != earlier.new_status:
                raise InvalidRecord("Audit status transitions are inconsistent")
        if entries and entries[-1].new_status != self.status:
            raise InvalidRecord("Current incident status does not match audit history")
        return entries

    # Validate and record an actual status transition; unchanged statuses create no new event.
    def change_status(self, new_status: str, reason: str = "Status updated") -> bool:
        """Record a real transition in memory; persistence is the repository's job."""
        if new_status not in VALID_STATUSES:
            raise InvalidRecord("Invalid incident status")
        if self.status == new_status:
            return False  # No change: do not create fake history entries.
        self._append_audit(self.status, new_status, reason)
        self._fields["status"] = new_status
        return True

    # Human review is independent of incident status changes and AI-calculated risk.
    def ai_review_history(self) -> list[AIReviewEntry]:
        """Return validated AI-review entries, oldest first; legacy records have none."""
        raw = self._fields.get("ai_review_history", [])
        if not isinstance(raw, list):
            raise InvalidRecord("AI review history must be a list")
        entries = [AIReviewEntry.from_mapping(item) for item in raw]
        if any(item.incident_id != self.incident_id for item in entries):
            raise InvalidRecord("AI review entry belongs to a different incident")
        return entries

    def add_ai_review(self, reviewer: str, decision: str, reason: str) -> AIReviewEntry:
        """Append a human review without replacing the original Gemini assessment."""
        if not self.incident_id:
            raise InvalidRecord("Save the incident before reviewing its AI assessment")
        if self.get("assessment_source") != "Gemini AI" or any(
            not str(self.get(field) or "").strip()
            for field in ("category", "severity", "risk_summary")
        ):
            raise InvalidRecord("This incident has no saved Gemini assessment to review")
        history = self.ai_review_history()
        entry = AIReviewEntry(
            incident_id=self.incident_id,
            reviewer=reviewer,
            decision=decision,
            reason=reason,
            reviewed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self._fields["ai_review_history"] = [
            *(item.as_dict() for item in history), entry.as_dict()
        ]
        return entry

    # Return a safe storage snapshot, excluding local absolute image paths and retaining legacy fields.
    def as_dict(self) -> dict[str, Any]:
        """Return an independent storage-ready dictionary, retaining extra Phase 1 fields."""
        fields = deepcopy(self._fields)
        fields.pop("visual_evidence_path", None)  # never persist absolute runtime path
        fields["image_path"] = fields.pop("image_patch", fields.get("image_path", "")) or ""
        result = {key: fields.get(key) for key in SCHEMA_FIELDS}
        result.update({key: value for key, value in fields.items() if key not in result})
        return result
