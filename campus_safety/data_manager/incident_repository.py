# FILE GUIDE: Abstract storage contract shared by JSON and SQLite repositories (LSP/OCP).
# Shared replace_all validation prevents either backend from storing malformed audit history.
# Comments explain responsibilities and design; executable statements are unchanged.

"""Abstract persistence interface."""
from __future__ import annotations
from abc import ABC, abstractmethod
from campus_safety.domain.hazard_report import HazardReport
from campus_safety.data_manager.data_store_error import DataStoreError
from campus_safety.domain.invalid_record import InvalidRecord


# Interface implemented by JSON and SQLite repositories.
# Both backends reuse parent replace_all validation and provide independent storage behavior.
class IncidentRepository(ABC):
    """Storage contract; domain and workflow do not need to know JSON details."""

    # Abstract read operation; concrete implementations reconstruct HazardReport objects.
    @abstractmethod
    def load(self) -> list[HazardReport]:
        raise NotImplementedError

    # Abstract create operation; storage backends allocate/preserve incident identifiers.
    @abstractmethod
    def save(self, report: HazardReport) -> None:
        raise NotImplementedError

    # Reusable parent validation for replacement collections and audit invariants.
    # Concrete classes call super() before their own backend-specific persistence.
    @abstractmethod
    def replace_all(self, reports: list[HazardReport], backup_label: str = "auto") -> None:
        """Validate a replacement collection before a backend persists it.

        Python allows an abstract method to contain reusable behaviour.
        Concrete repositories MUST override this method and call
        ``super().replace_all(reports, backup_label)`` before changing data.
        This illustrates Lab 7's method overriding and parent-code reuse.
        """
        if not isinstance(reports, list):
            raise DataStoreError("Replacement records must be a list")
        seen: set[str] = set()
        for report in reports:
            if not isinstance(report, HazardReport):
                raise DataStoreError("Replacement entries must be HazardReport objects")
            incident_id = report.incident_id
            if not incident_id or incident_id in seen:
                raise DataStoreError("Replacement requires unique nonempty incident IDs")
            seen.add(incident_id)
            try:
                report.status_history()  # No invalid audit event may be persisted.
                report.ai_review_history()  # Human review history uses the same protection.
            except InvalidRecord as exc:
                raise DataStoreError("Invalid incident status audit history") from exc

    # Abstract backup operation; returns the created snapshot path if available.
    @abstractmethod
    def create_backup(self, label: str = "") -> str | None:
        raise NotImplementedError

    # Abstract enumeration of snapshot paths maintained by the backend.
    @abstractmethod
    def list_backups(self) -> list[str]:
        raise NotImplementedError

    # Abstract restore operation; implementations must validate before replacing live data.
    @abstractmethod
    def restore_backup(self, path: str | None = None) -> None:
        raise NotImplementedError
