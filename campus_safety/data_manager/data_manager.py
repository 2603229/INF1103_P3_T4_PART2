# FILE GUIDE: Storage-facing facade responsible for CRUD, audit persistence, query and export operations.
# It talks to the IncidentRepository ABC rather than branching on SQLite versus JSON.
# Comments explain responsibilities and design; executable statements are unchanged.

"""Data Manager: application-facing persistence operations."""
from __future__ import annotations
import csv
from pathlib import Path
from typing import Any, Callable, Dict, List
from campus_safety.data_manager.incident_repository import IncidentRepository
from campus_safety.data_manager.json_incident_repository import JsonIncidentRepository
from campus_safety.data_manager.data_store_error import DataStoreError
from campus_safety.domain.hazard_report import HazardReport
from campus_safety.domain.invalid_record import InvalidRecord
from campus_safety.domain.schema import VALID_STATUSES
from campus_safety.domain.incident_audit_entry import IncidentAuditEntry
from campus_safety.domain.ai_review_entry import AIReviewEntry


# Coordinates persistence, audit updates and exports through an abstract repository.
# Backend details are intentionally hidden from the CLI and Streamlit.
class DataManager:
    """Application-facing data operations; repository can be substituted for tests."""

    # Receive a repository instance instead of hard-coding JSON or SQLite.
    def __init__(self, repository: IncidentRepository) -> None:
        self._repository: IncidentRepository = repository  # aggregation: repository also usable independently

    # Ask the configured repository to return validated report objects.
    def load(self) -> list[HazardReport]:
        return self._repository.load()

    # Persist a fully assessed report through the common repository interface.
    def save(self, report: HazardReport) -> None:
        self._repository.save(report)

    # Filter incidents against supplied field conditions without accessing backend internals.
    def query(self, predicate: Callable[[HazardReport], bool]) -> list[HazardReport]:
        return [row for row in self.load() if predicate(row)]

    # Find an incident by its stable public identifier; return None if absent.
    def get_by_id(self, incident_id: str) -> HazardReport | None:
        return next((r for r in self.load() if r.incident_id == incident_id), None)

    # Return the audited transitions for an incident, or an empty history if missing.
    def status_history(self, incident_id: str) -> list[IncidentAuditEntry]:
        """Retrieve an incident's persistent, chronological audit entries."""
        report = self.get_by_id(incident_id)
        return report.status_history() if report else []

    # Change a report status and persist the corresponding audit event together.
    # A no-op status change does not append a misleading history entry.
    def update_status(self, incident_id: str, status: str,
                      reason: str = "Status updated") -> bool:
        if status not in VALID_STATUSES:
            raise InvalidRecord("Invalid incident status")
        rows = self.load()
        for row in rows:
            if row.incident_id == incident_id:
                if row.change_status(status, reason):
                    # Status and audit entry are persisted together by the
                    # selected JSON or SQLite repository.
                    self._repository.replace_all(rows, "before-status-update")
                return True  # Existing ID, including unchanged status.
        return False

    # Persist human review without changing the model result, risk score or incident status.
    def record_ai_review(self, incident_id: str, reviewer: str,
                         decision: str, reason: str) -> bool:
        """Return False if the incident no longer exists; otherwise persist a review."""
        rows = self.load()
        for report in rows:
            if report.incident_id == incident_id:
                report.add_ai_review(reviewer, decision, reason)
                self._repository.replace_all(rows, "before-ai-review")
                return True
        return False

    def ai_review_history(self, incident_id: str) -> list[AIReviewEntry]:
        """Read persisted human reviews, oldest first, for one incident."""
        report = self.get_by_id(incident_id)
        return report.ai_review_history() if report is not None else []

    # Remove an identified incident while retaining a pre-change backup where supported.
    def delete(self, incident_id: str) -> bool:
        rows = self.load()
        updated = [r for r in rows if r.incident_id != incident_id]
        if len(rows) == len(updated):
            return False
        self._repository.replace_all(updated, "before-delete")
        return True

    # Remove active records through validated repository replacement and backup handling.
    def clear(self) -> None:
        self._repository.replace_all([], "before-clear")

    # List available database snapshots through the chosen persistence adapter.
    def backups(self) -> list[str]:
        return self._repository.list_backups()

    # Ask the repository to validate and restore a selected known snapshot.
    def restore(self, path: str | None = None) -> None:
        self._repository.restore_backup(path)

    # Write all report fields with a stable union of headers as UTF-8-with-BOM CSV.
    def export_csv(self, destination: str | Path) -> Path:
        rows = [r.as_dict() for r in self.load()]
        if not rows:
            raise DataStoreError("No records to export")
        fields = list(dict.fromkeys(key for row in rows for key in row))
        path = Path(destination)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            return path
        except OSError as exc:
            raise DataStoreError("Cannot export CSV") from exc

    # Produce an easy-to-read incident report; reject empty datasets consistently.
    def export_txt(self, destination: str | Path) -> Path:
        rows = [r.as_dict() for r in self.load()]
        if not rows:
            raise DataStoreError("No records to export")
        path = Path(destination)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as stream:
                stream.write("CAMPUS SAFETY HAZARD REPORTING SYSTEM\nINCIDENT MANAGEMENT REPORT\n")
                stream.write(f"Total Incidents: {len(rows)}\n\n")
                for row in rows:
                    stream.write("-" * 50 + "\n")
                    for key, value in row.items():
                        stream.write(f"{key.replace('_',' ').title()}: {value if value is not None else 'N/A'}\n")
            return path
        except OSError as exc:
            raise DataStoreError("Cannot export TXT") from exc
        
    # Filter incidents by location, status, category, and severity threshold.
    def search(
        self,
        location_query: str = "",
        status_filter: str = "",
        category_filter: str = "",
        min_severity: int = 1
    ) -> List[Dict[str, Any]]:
        """Filters stored records based on facilities-specific criteria."""
        all_records = self.load()
        results = []

        for record in all_records:
            # Match location keyword (case-insensitive)
            loc = record.get("location", "").lower()
            if location_query and location_query.lower() not in loc:
                continue

            # Match status
            st = record.get("status", "")
            if status_filter and st != status_filter:
                continue

            # Match category (e.g. Electrical, Infrastructure, Plumbing)
            cat = record.get("category", "")
            if category_filter and cat.lower() != category_filter.lower():
                continue

            # Match severity threshold
            sev = record.get("severity", 1)
            if sev < min_severity:
                continue

            results.append(record)

        return results