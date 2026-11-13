# FILE GUIDE: SQLite persistence adapter with parameterised SQL, transactions and backup/restore.
# Status and its audit history are stored together in each record payload for consistency.
# Comments explain responsibilities and design; executable statements are unchanged.

"""SQLite-backed incident repository with transactional CRUD and online backups.

One class per Python file. Audit entries are stored in each incident's JSON
payload so status and history change in the *same* SQLite transaction.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sqlite3
import uuid
from campus_safety.data_manager.data_store_error import DataStoreError
from campus_safety.domain.hazard_report import HazardReport
from campus_safety.data_manager.incident_repository import IncidentRepository
from campus_safety.domain.invalid_record import InvalidRecord


# Database-backed IncidentRepository with transactional CRUD and metadata counter.
# Records and status-history changes stay together in the same transactional payload.
class SQLiteIncidentRepository(IncidentRepository):
    """A drop-in IncidentRepository with SQLite persistence and full CRUD."""

    # Create incidents/metadata tables when absent, then validate stored rows and ID counter.
    # This rejects corrupted databases rather than silently treating them as empty.
    def __init__(self, path: str | Path | None = None, max_backups: int = 30) -> None:
        if path is None:
            root = Path(__file__).resolve().parents[2]
            path = os.getenv("SQLITE_DB_PATH") or str(
                Path(os.getenv("HAZARD_DATA_DIR") or root) / "hazardreports.sqlite3"
            )
        self._memory_uri: str | None = None
        if str(path) == ":memory:":
            self._path = Path(":memory:")
            self._memory_uri = (
                f"file:campus_safety_{uuid.uuid4().hex}?mode=memory&cache=shared"
            )
        else:
            self._path = Path(path).resolve()
        self._memory_anchor: sqlite3.Connection | None = None
        self._backup_dir = self._path.parent / "sqlite_backups"
        self._max_backups = max_backups
        try:
            if self._memory_uri is not None:
                self._memory_anchor = sqlite3.connect(
                    self._memory_uri, timeout=10.0, uri=True
                )
            else:
                self._path.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connect()) as conn, conn:
                conn.execute("CREATE TABLE IF NOT EXISTS incidents ("
                             "incident_id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
                conn.execute("CREATE TABLE IF NOT EXISTS metadata ("
                             "key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                conn.execute("INSERT OR IGNORE INTO metadata(key, value) "
                             "VALUES ('last_issued', '0')")
                self._read_all(conn)  # reject corrupt records or invalid schemas
                self._last_issued(conn)
        except DataStoreError:
            self.close()
            raise
        except (sqlite3.Error, OSError, ValueError, InvalidRecord, UnicodeError) as exc:
            self.close()
            raise DataStoreError(f"Cannot initialise SQLite database: {exc}") from exc

    # Expose the effective SQLite path for migration and diagnostics.
    @property
    def database_path(self) -> Path:
        return self._path

    # Open a SQLite connection with a busy timeout to handle concurrent dashboard/CLI access.
    def _connect(self) -> sqlite3.Connection:
        if self._memory_uri is not None:
            conn = sqlite3.connect(self._memory_uri, timeout=10.0, uri=True)
        else:
            conn = sqlite3.connect(str(self._path), timeout=10.0)
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    # Release the keeper connection that preserves a shared in-memory database.
    def close(self) -> None:
        if self._memory_anchor is not None:
            self._memory_anchor.close()
            self._memory_anchor = None

    # Read the persistent metadata counter; invalid contents are treated as corruption.
    @staticmethod
    def _last_issued(conn: sqlite3.Connection) -> int:
        row = conn.execute("SELECT value FROM metadata WHERE key='last_issued'").fetchone()
        if row is None or not isinstance(row[0], str) or not row[0].isdigit():
            raise DataStoreError("Invalid SQLite incident ID counter")
        return int(row[0])

    # Reconstruct and validate all stored payloads while ensuring row ID matches report ID.
    @staticmethod
    def _read_all(conn: sqlite3.Connection) -> list[HazardReport]:
        result = []
        for ident, payload in conn.execute("SELECT incident_id, payload FROM incidents ORDER BY rowid"):
            result.append(SQLiteIncidentRepository._report_from_payload(ident, payload))
        return result

    # Reconstruct a validated report and verify its indexed ID matches the payload.
    @staticmethod
    def _report_from_payload(incident_id: str, payload: str) -> HazardReport:
        fields = json.loads(payload)
        if not isinstance(fields, dict):
            raise DataStoreError("SQLite incident payload must be an object")
        report = HazardReport.from_storage(fields)
        if not incident_id or report.incident_id != incident_id:
            raise DataStoreError("SQLite incident ID does not match stored payload")
        return report

    # Validate incident identity/audit history before JSON encoding the SQLite payload.
    @staticmethod
    def _payload(report: HazardReport) -> str:
        if not report.incident_id:
            raise DataStoreError("Incident ID is missing")
        report.status_history()  # validate audit entries before writing
        report.ai_review_history()  # validate AI reviews before writing
        return json.dumps(report.as_dict(), ensure_ascii=False)

    # Extract the numeric part of a formatted incident identifier for counter reconciliation.
    @staticmethod
    def _id_number(value: str) -> int:
        match = re.fullmatch(r"INCIDENT-(\d+)", value)
        return int(match.group(1)) if match else 0

    # Read all incidents using a short-lived SQLite connection.
    def load(self) -> list[HazardReport]:
        try:
            with closing(self._connect()) as conn:
                return self._read_all(conn)
        except (sqlite3.Error, OSError, ValueError, UnicodeError, InvalidRecord) as exc:
            raise DataStoreError(f"Cannot load SQLite incidents: {exc}") from exc

    # Fetch and validate one row through the indexed primary-key column.
    def get_by_id(self, incident_id: str) -> HazardReport | None:
        try:
            with closing(self._connect()) as conn:
                row = conn.execute(
                    "SELECT payload FROM incidents WHERE incident_id = ?",
                    (incident_id,),
                ).fetchone()
            return self._report_from_payload(incident_id, row[0]) if row else None
        except (sqlite3.Error, OSError, ValueError, UnicodeError, InvalidRecord) as exc:
            raise DataStoreError(f"Cannot load SQLite incident: {exc}") from exc

    # Perform a single immediate transaction to reserve an ID, insert the payload and update metadata.
    # Parameter placeholders prevent SQL injection and preserve special characters.
    def save(self, report: HazardReport) -> None:
        """CREATE: allocate a persistent ID and insert an incident atomically."""
        try:
            with closing(self._connect()) as conn, conn:
                # Reserve the write lock before generating the next ID to avoid concurrent collisions.
                conn.execute("BEGIN IMMEDIATE")
                highest = self._last_issued(conn)
                if not report.incident_id:
                    highest += 1
                    report.assign_identity(f"INCIDENT-{highest:03d}")
                highest = max(highest, self._id_number(report.incident_id))
                conn.execute("INSERT INTO incidents(incident_id, payload) VALUES (?, ?)",
                             (report.incident_id, self._payload(report)))
                conn.execute("UPDATE metadata SET value=? WHERE key='last_issued'", (str(highest),))
        except sqlite3.IntegrityError as exc:
            raise DataStoreError("Duplicate incident ID") from exc
        except (sqlite3.Error, OSError, ValueError, TypeError, InvalidRecord) as exc:
            raise DataStoreError(f"Cannot save SQLite incident: {exc}") from exc

    # Reuse abstract validation, then transactionally rewrite active rows and retain counter.
    def replace_all(self, reports: list[HazardReport], backup_label: str = "auto") -> None:
        """UPDATE/DELETE: synchronize changed rows in one transaction.

        DataManager's existing API continues to work; SQLite uses real SQL
        UPDATE/DELETE, while the report and audit history remain one payload.
        """
        # Lab 7: inherit shared validation, then extend it with SQLite's
        # transactional update/delete behaviour.
        super().replace_all(reports, backup_label)
        payloads: dict[str, str] = {}
        try:
            for report in reports:
                ident = report.incident_id
                if not ident or ident in payloads:
                    raise DataStoreError("Missing or repeated incident ID in bulk update")
                payloads[ident] = self._payload(report)
            with closing(self._connect()) as conn:
                previous = dict(conn.execute("SELECT incident_id, payload FROM incidents"))
            if previous == payloads:
                return  # no-op: no backup or database rewrite
            self.create_backup(backup_label)
            with closing(self._connect()) as conn, conn:
                conn.execute("BEGIN IMMEDIATE")
                # Fail closed on malformed existing data, rather than overwriting it.
                self._read_all(conn)
                if dict(conn.execute("SELECT incident_id, payload FROM incidents")) != previous:
                    raise DataStoreError("SQLite incidents changed concurrently; update cancelled")
                for ident in previous.keys() - payloads.keys():
                    conn.execute("DELETE FROM incidents WHERE incident_id=?", (ident,))
                for ident, payload in payloads.items():
                    if ident not in previous:
                        conn.execute("INSERT INTO incidents(incident_id, payload) VALUES (?, ?)",
                                     (ident, payload))
                    elif previous[ident] != payload:
                        conn.execute("UPDATE incidents SET payload=? WHERE incident_id=?",
                                     (payload, ident))
                highest = max((self._id_number(s) for s in payloads), default=0)
                conn.execute("UPDATE metadata SET value=? WHERE key='last_issued'",
                             (str(max(highest, self._last_issued(conn))),))
        except (sqlite3.Error, OSError, ValueError, TypeError, InvalidRecord) as exc:
            raise DataStoreError(f"Cannot update SQLite incidents: {exc}") from exc

    # Discover known SQLite backups in the repository-managed snapshot directory.
    def list_backups(self) -> list[str]:
        if self._memory_uri is not None:
            return []
        try:
            return [str(p) for p in sorted(
                self._backup_dir.glob("incidents_backup_*.sqlite3"), reverse=True
            )]
        except OSError:
            return []

    # Create a consistent SQLite snapshot using SQLite backup support rather than raw file copy.
    def create_backup(self, label: str = "") -> str | None:
        """Consistent online backup through the SQLite backup API."""
        if self._memory_uri is not None or not self._path.exists():
            return None
        tag = re.sub(r"[^A-Za-z0-9_-]", "", label)
        name = (f"incidents_backup_{datetime.now():%Y%m%d_%H%M%S_%f}"
                f"{'_' + tag if tag else ''}.sqlite3")
        dest = self._backup_dir / name
        temp = dest.with_suffix(".sqlite3.tmp")
        try:
            self._backup_dir.mkdir(parents=True, exist_ok=True)
            with closing(self._connect()) as source, closing(sqlite3.connect(temp)) as target:
                source.backup(target)
            os.replace(temp, dest)
            for old in self.list_backups()[self._max_backups:]:
                Path(old).unlink(missing_ok=True)
            return str(dest)
        except (sqlite3.Error, OSError) as exc:
            temp.unlink(missing_ok=True)
            raise DataStoreError(f"Cannot create SQLite backup: {exc}") from exc

    # Validate the selected backup before using a transaction-safe restore path.
    def restore_backup(self, path: str | None = None) -> None:
        if self._memory_uri is not None:
            raise DataStoreError("Cannot restore a file backup into an in-memory database")
        options = self.list_backups()
        source_path = Path(path) if path is not None else (Path(options[0]) if options else None)
        if source_path is None or not source_path.is_file():
            raise DataStoreError("No SQLite backup to restore")
        if source_path.resolve().parent != self._backup_dir.resolve() or source_path.suffix != ".sqlite3":
            raise DataStoreError("Backup must be a SQLite file within its backup directory")
        temp = self._path.with_suffix(".restore.tmp")
        try:
            with closing(sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True)) as source:
                if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise DataStoreError("SQLite backup failed integrity check")
                self._read_all(source)  # validate audit entries and IDs
                restored_counter = self._last_issued(source)
                with closing(self._connect()) as current:
                    existing_counter = self._last_issued(current)
                self.create_backup("before-restore")
                temp.unlink(missing_ok=True)
                with closing(sqlite3.connect(temp)) as target:
                    source.backup(target)
                with closing(sqlite3.connect(temp)) as target, target:
                    target.execute("UPDATE metadata SET value=? WHERE key='last_issued'",
                                   (str(max(restored_counter, existing_counter)),))
            os.replace(temp, self._path)
        except (sqlite3.Error, OSError, ValueError, InvalidRecord) as exc:
            raise DataStoreError(f"Cannot restore SQLite backup: {exc}") from exc
        finally:
            temp.unlink(missing_ok=True)

    # Import validated legacy reports and last-issued ID only into a suitable empty target.
    def import_records(self, reports: list[HazardReport], last_issued: int = 0) -> int:
        """One-time JSON import; never overwrite an already-used SQLite database."""
        if not isinstance(last_issued, int) or last_issued < 0:
            raise DataStoreError("Invalid migration incident ID counter")
        payloads = {}
        for report in reports:
            ident = report.incident_id
            if not ident or ident in payloads:
                raise DataStoreError("Migration requires unique nonempty incident IDs")
            payloads[ident] = self._payload(report)
        try:
            with closing(self._connect()) as conn, conn:
                conn.execute("BEGIN IMMEDIATE")
                if conn.execute("SELECT 1 FROM incidents LIMIT 1").fetchone() or self._last_issued(conn):
                    raise DataStoreError("SQLite target already contains incident data or prior IDs")
                for ident, payload in payloads.items():
                    conn.execute("INSERT INTO incidents (incident_id, payload) VALUES (?, ?)",
                                 (ident, payload))
                counter = max(last_issued, *(self._id_number(i) for i in payloads)) if payloads else last_issued
                conn.execute("UPDATE metadata SET value=? WHERE key='last_issued'", (str(counter),))
            return len(payloads)
        except (sqlite3.Error, OSError, ValueError, TypeError, InvalidRecord) as exc:
            raise DataStoreError(f"SQLite migration failed: {exc}") from exc
