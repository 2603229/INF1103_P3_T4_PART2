# FILE GUIDE: JSON persistence adapter using atomic file replacement, stable incident IDs and safe backups.
# A corrupted file raises DataStoreError instead of being silently replaced by an empty database.
# Comments explain responsibilities and design; executable statements are unchanged.

"""JSON storage: safe writes, persistent IDs, CRUD backups."""
from __future__ import annotations
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
from campus_safety.data_manager.incident_repository import IncidentRepository
from campus_safety.domain.hazard_report import HazardReport
from campus_safety.data_manager.data_store_error import DataStoreError


# Legacy-compatible JSON storage with atomic writes, durable IDs and snapshots.
# It must reject malformed records rather than overwriting previous data.
class JsonIncidentRepository(IncidentRepository):
    """Concrete repository. Its parts (file, counter, backups) are managed by it."""

    # Resolve a configurable path rooted at Project Code; track counter and backup folders.
    # Persist IDs separately so deleting the latest incident never reuses its ID.
    def __init__(self, path: str | Path | None = None, max_backups: int = 30) -> None:
        if path is None:
            # Phase 1 resolved the default database relative to its source directory,
            # not to the process working directory. Preserve that behaviour.
            project_root = Path(__file__).resolve().parents[2]
            data_dir = Path(os.getenv("HAZARD_DATA_DIR") or project_root)
            path = os.getenv("INCIDENTS_DB") or str(data_dir / "hazardreportdb.json")
        self._path = Path(path).resolve()
        self._counter = self._path.parent / ".incident_id_counter"
        self._backup_dir = self._path.parent / "backups"
        self._max_backups = max_backups

    # Expose the effective JSON path for migration and troubleshooting.
    @property
    def database_path(self) -> Path:
        return self._path

    # Read and validate a list of record dictionaries. Missing file means no initial incidents.
    # Malformed files fail closed rather than silently resetting the database.
    @staticmethod
    def _read(path: Path) -> list[HazardReport]:
        if not path.exists():
            return []
        try:
            with path.open(encoding="utf-8") as stream:
                data = json.load(stream)
            if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
                raise ValueError("Expected a list of record objects")
            reports = [HazardReport.from_storage(item) for item in data]
            # Match SQLite's primary-key integrity rule. Duplicate IDs in a
            # JSON file are corruption, not two distinct stored incidents.
            ids = [report.incident_id for report in reports if report.incident_id]
            if len(ids) != len(set(ids)):
                raise ValueError("Duplicate incident ID in JSON database")
            return reports
        except (OSError, ValueError, UnicodeError) as exc:
            raise DataStoreError(f"Cannot read {path.name}: {exc}") from exc

    # Write into a temporary file before atomically replacing the original JSON file.
    # Cleanup of the temporary file avoids leaving partial output on errors.
    @staticmethod
    def _write(path: Path, reports: list[HazardReport]) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Validate both status history and optional AI review history before writing.
            for report in reports:
                report.status_history()
                report.ai_review_history()
            with temporary.open("w", encoding="utf-8") as stream:
                json.dump([r.as_dict() for r in reports], stream, ensure_ascii=False, indent=4)
            # An atomic rename avoids exposing a partially written JSON database.
            os.replace(temporary, path)
        except (OSError, TypeError, ValueError) as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise DataStoreError(f"Cannot write {path.name}: {exc}") from exc

    # Read and reconstruct all currently stored incidents.
    def load(self) -> list[HazardReport]:
        return self._read(self._path)

    # Choose a new ID above both persisted counter and IDs currently present.
    def _next_id(self, reports: list[HazardReport]) -> int:
        highest = 0
        for record in reports:
            match = re.fullmatch(r"INCIDENT-(\d+)", record.incident_id)
            if match:
                highest = max(highest, int(match.group(1)))
        if self._counter.exists():
            try:
                number = self._counter.read_text(encoding="utf-8").strip()
                if not number.isdigit():
                    raise ValueError("counter contains non-digits")
                highest = max(highest, int(number))
            except (OSError, ValueError) as exc:
                raise DataStoreError("Invalid persistent incident ID counter") from exc
        return highest + 1

    # Durably update the ID counter before assigning a new incident identifier.
    def _reserve_id(self, reports: list[HazardReport]) -> str:
        number = self._next_id(reports)
        temporary = self._counter.with_suffix(".tmp")
        try:
            self._counter.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(str(number), encoding="utf-8")
            os.replace(temporary, self._counter)
        except OSError as exc:
            raise DataStoreError("Cannot reserve next incident ID") from exc
        return f"INCIDENT-{number:03d}"

    # Reject duplicate IDs, reserve one for a new report, then persist the updated list.
    def save(self, report: HazardReport) -> None:
        records = self.load()  # Fail closed on corrupt DB.
        if report.incident_id and any(record.incident_id == report.incident_id for record in records):
            raise DataStoreError("Duplicate incident ID")
        if not report.incident_id:
            report.assign_identity(self._reserve_id(records))
        records.append(report)
        self._write(self._path, records)

    # Return available dated JSON snapshots in newest-first order.
    def list_backups(self) -> list[str]:
        try:
            return [str(p) for p in sorted(self._backup_dir.glob("incidents_backup_*.json"), reverse=True)]
        except OSError:
            return []

    # Copy the database before a destructive update and prune excess old snapshots.
    def create_backup(self, label: str = "") -> str | None:
        if not self._path.exists():
            return None
        tag = re.sub(r"[^A-Za-z0-9_-]", "", label)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"incidents_backup_{timestamp}{'_' + tag if tag else ''}.json"
        destination = self._backup_dir / filename
        try:
            self._backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self._path, destination)
            for old in self.list_backups()[self._max_backups:]:
                Path(old).unlink(missing_ok=True)
            return str(destination)
        except OSError as exc:
            raise DataStoreError("Cannot create database backup") from exc

    # Validate through the abstract parent, back up existing data, then atomically replace it.
    def replace_all(self, reports: list[HazardReport], backup_label: str = "auto") -> None:
        # Lab 7: override the abstract parent method, reusing its shared
        # collection/audit validation before performing JSON-specific writes.
        super().replace_all(reports, backup_label)
        # A modification to an existing database requires a successful backup.
        if self._path.exists():
            self.create_backup(backup_label)
        self._write(self._path, reports)

    # Only restore a file from the managed backup directory after validating its content.
    def restore_backup(self, path: str | None = None) -> None:
        choices = self.list_backups()
        selected = Path(path) if path is not None else (Path(choices[0]) if choices else None)
        if selected is None or not selected.is_file():
            raise DataStoreError("No backup to restore")
        if selected.resolve().parent != self._backup_dir.resolve():
            raise DataStoreError("Backup must be within the backup directory")
        reports = self._read(selected)  # Validate before changing current database.
        if self._path.exists():
            self.create_backup("before-restore")
        self._write(self._path, reports)
