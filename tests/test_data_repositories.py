# FILE GUIDE: Offline persistence tests run identically against JSON and SQLite.
# The same test methods exercise both IncidentRepository implementations (LSP),
# covering CRUD, persistence across runs, audit trail, AI review, backups and corruption.

"""Cross-backend DataManager / repository tests (JSON and SQLite)."""
from __future__ import annotations

import csv
import gc
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from campus_safety.ai_manager.ai_assessment import AIAssessment
from campus_safety.data_manager.data_manager import DataManager
from campus_safety.data_manager.data_store_error import DataStoreError
from campus_safety.data_manager.incident_repository import IncidentRepository
from campus_safety.data_manager.json_incident_repository import JsonIncidentRepository
from campus_safety.data_manager.repository_factory import create_repository
from campus_safety.data_manager.sqlite_incident_repository import SQLiteIncidentRepository
from campus_safety.domain.hazard_report import HazardReport
from campus_safety.domain.invalid_record import InvalidRecord

ASSESSMENT = AIAssessment("Exposed wiring", "Electrical", "High", "Moderate", "Cordon off area")


def new_report(location: str = "Building E Level 2") -> HazardReport:
    report = HazardReport.from_input({
        "reporter_name": "Alex Tan", "reporter_contact": "91234567",
        "location": location, "impact_headcount": 3, "asset_info": "Power socket",
        "description": "Sparks are coming from the wall socket near the desk",
    })
    report.attach_assessment(ASSESSMENT)
    return report


class RepositoryContract:
    """Mixin: tests every IncidentRepository must pass. Subclasses supply the backend."""

    def make_repository(self, path: Path) -> IncidentRepository:
        raise NotImplementedError

    filename = ""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / self.filename
        self.data = DataManager(self.make_repository(self.path))

    def tearDown(self) -> None:
        gc.collect()  # release SQLite handles before Windows deletes the folder
        self._tmp.cleanup()

    # --- Create / Read --------------------------------------------------
    def test_empty_database_loads_no_records(self) -> None:
        self.assertEqual(self.data.load(), [])

    def test_save_assigns_sequential_ids_and_creation_audit(self) -> None:
        first, second = new_report(), new_report("Library")
        self.data.save(first)
        self.data.save(second)
        self.assertEqual([first.incident_id, second.incident_id], ["INCIDENT-001", "INCIDENT-002"])
        history = self.data.status_history("INCIDENT-001")
        self.assertEqual(len(history), 1)
        self.assertIsNone(history[0].previous_status)
        self.assertEqual(history[0].new_status, "Pending Review")

    def test_records_persist_across_new_repository_instances(self) -> None:
        self.data.save(new_report())
        reopened = DataManager(self.make_repository(self.path))  # simulates a restart
        stored = reopened.get_by_id("INCIDENT-001")
        self.assertEqual(stored.get("category"), "Electrical")
        self.assertEqual(stored.location, "Building E Level 2")

    def test_get_by_id_missing_returns_none(self) -> None:
        self.assertIsNone(self.data.get_by_id("INCIDENT-999"))

    def test_duplicate_incident_id_is_rejected(self) -> None:
        self.data.save(new_report())
        clash = HazardReport.from_storage({"incident_id": "INCIDENT-001"})
        with self.assertRaises(DataStoreError):
            self.data.save(clash)

    # --- Update / Audit Trail ------------------------------------------
    def test_status_update_records_audit_trail(self) -> None:
        self.data.save(new_report())
        self.assertTrue(self.data.update_status("INCIDENT-001", "In Progress", "Technician assigned"))
        reopened = DataManager(self.make_repository(self.path))
        history = reopened.status_history("INCIDENT-001")
        self.assertEqual([(h.previous_status, h.new_status) for h in history],
                         [(None, "Pending Review"), ("Pending Review", "In Progress")])
        self.assertEqual(history[-1].reason, "Technician assigned")
        self.assertEqual(reopened.get_by_id("INCIDENT-001").status, "In Progress")

    def test_unchanged_status_adds_no_history(self) -> None:
        self.data.save(new_report())
        self.assertTrue(self.data.update_status("INCIDENT-001", "Pending Review"))
        self.assertEqual(len(self.data.status_history("INCIDENT-001")), 1)

    def test_invalid_status_is_rejected(self) -> None:
        self.data.save(new_report())
        with self.assertRaises(InvalidRecord):
            self.data.update_status("INCIDENT-001", "Done")

    def test_update_unknown_incident_returns_false(self) -> None:
        self.assertFalse(self.data.update_status("INCIDENT-404", "Resolved"))

    def test_ai_review_is_persisted_without_changing_ai_fields(self) -> None:
        self.data.save(new_report())
        self.assertTrue(self.data.record_ai_review("INCIDENT-001", "Officer Lim",
                                                   "Flagged as Incorrect", "Looks like plumbing"))
        reopened = DataManager(self.make_repository(self.path))
        reviews = reopened.ai_review_history("INCIDENT-001")
        self.assertEqual(reviews[0].decision, "Flagged as Incorrect")
        self.assertEqual(reopened.get_by_id("INCIDENT-001").get("category"), "Electrical")

    # --- Delete -----------------------------------------------------------
    def test_delete_removes_record_and_never_reuses_id(self) -> None:
        self.data.save(new_report())
        self.data.save(new_report("Library"))
        self.assertTrue(self.data.delete("INCIDENT-002"))
        self.assertFalse(self.data.delete("INCIDENT-002"))
        third = new_report("Sports Hall")
        self.data.save(third)
        self.assertEqual(third.incident_id, "INCIDENT-003")
        self.assertEqual([r.incident_id for r in self.data.load()], ["INCIDENT-001", "INCIDENT-003"])

    # --- Backup / restore -------------------------------------------------
    def test_changes_create_backup_that_can_be_restored(self) -> None:
        self.data.save(new_report())
        self.data.delete("INCIDENT-001")  # backup taken before the delete
        self.assertEqual(self.data.load(), [])
        self.assertTrue(self.data.backups())
        self.data.restore(self.data.backups()[-1])  # oldest = state before delete
        self.assertEqual([r.incident_id for r in self.data.load()], ["INCIDENT-001"])

    def test_restore_outside_backup_folder_is_rejected(self) -> None:
        self.data.save(new_report())
        with self.assertRaises(DataStoreError):
            self.data.restore(str(self.path))

    # --- Query / export -----------------------------------------------------
    def test_search_and_query(self) -> None:
        self.data.save(new_report())
        self.data.save(new_report("Library"))
        self.assertEqual(len(self.data.search(location_query="library")), 1)
        self.assertEqual(len(self.data.query(lambda r: r.get("severity") == "High")), 2)

    def test_export_csv_and_txt(self) -> None:
        self.data.save(new_report())
        csv_path = self.data.export_csv(self.path.parent / "out" / "incidents.csv")
        txt_path = self.data.export_txt(self.path.parent / "out" / "incidents.txt")
        self.assertIn("INCIDENT-001", csv_path.read_text(encoding="utf-8-sig"))
        self.assertIn("INCIDENT-001", txt_path.read_text(encoding="utf-8"))

    def test_export_with_no_records_raises(self) -> None:
        with self.assertRaises(DataStoreError):
            self.data.export_csv(self.path.parent / "empty.csv")
        with self.assertRaises(DataStoreError):
            self.data.export_txt(self.path.parent / "empty.txt")

    def test_export_csv_sanitizes_formula_cells(self) -> None:
        self.data.save(HazardReport.from_storage({
            "incident_id": "INCIDENT-001",
            "description": "=1+1",
        }))
        csv_path = self.data.export_csv(self.path.parent / "formula.csv")
        with csv_path.open(encoding="utf-8-sig", newline="") as stream:
            row = next(csv.DictReader(stream))
        self.assertEqual(row["description"], "'=1+1")

    def test_export_to_non_directory_parent_raises(self) -> None:
        self.data.save(new_report())
        blocked_parent = self.path.parent / "not-a-directory"
        blocked_parent.write_text("blocker", encoding="utf-8")

        for extension, export in (
            ("csv", self.data.export_csv),
            ("txt", self.data.export_txt),
        ):
            with self.subTest(extension=extension):
                with self.assertRaises(DataStoreError):
                    export(blocked_parent / f"incidents.{extension}")


class JsonRepositoryTests(RepositoryContract, unittest.TestCase):
    filename = "incidents.json"

    def make_repository(self, path: Path) -> IncidentRepository:
        return JsonIncidentRepository(path)

    def test_corrupt_json_raises_and_is_not_overwritten(self) -> None:
        self.path.write_text("{ not valid json", encoding="utf-8")
        with self.assertRaises(DataStoreError):
            self.data.load()
        with self.assertRaises(DataStoreError):
            self.data.save(new_report())
        self.assertEqual(self.path.read_text(encoding="utf-8"), "{ not valid json")

    def test_wrong_json_shape_raises(self) -> None:
        self.path.write_text('{"incident_id": "INCIDENT-001"}', encoding="utf-8")
        with self.assertRaises(DataStoreError):
            self.data.load()

    def test_tampered_audit_history_is_rejected(self) -> None:
        self.data.save(new_report())
        text = self.path.read_text(encoding="utf-8").replace('"status": "Pending Review"',
                                                             '"status": "Resolved"', 1)
        self.path.write_text(text, encoding="utf-8")
        with self.assertRaises(DataStoreError):
            self.data.load()


class SQLiteRepositoryTests(RepositoryContract, unittest.TestCase):
    filename = "incidents.sqlite3"

    def make_repository(self, path: Path) -> IncidentRepository:
        return SQLiteIncidentRepository(path)

    def test_get_by_id_uses_direct_lookup(self) -> None:
        repository = SQLiteIncidentRepository(self.path.with_name("direct.sqlite3"))
        data = DataManager(repository)
        data.save(new_report())

        with patch.object(repository, "load", side_effect=AssertionError("full scan")):
            report = data.get_by_id("INCIDENT-001")

        self.assertIsNotNone(report)
        self.assertEqual(report.incident_id, "INCIDENT-001")

    def test_corrupt_sqlite_file_fails_at_startup(self) -> None:
        bad = self.path.with_name("corrupt.sqlite3")
        bad.write_bytes(b"this is not a database")
        with self.assertRaises(DataStoreError):
            SQLiteIncidentRepository(bad)

    def test_invalid_payload_row_is_rejected(self) -> None:
        self.data.save(new_report())
        connection = sqlite3.connect(self.path)
        with connection:
            connection.execute("UPDATE incidents SET payload='[1, 2]'")
        connection.close()
        with self.assertRaises(DataStoreError):
            self.data.load()

    def test_import_records_only_into_empty_database(self) -> None:
        source = DataManager(JsonIncidentRepository(self.path.with_name("legacy.json")))
        source.save(new_report())
        target = SQLiteIncidentRepository(self.path.with_name("migrated.sqlite3"))
        self.assertEqual(target.import_records(source.load(), last_issued=1), 1)
        with self.assertRaises(DataStoreError):
            target.import_records(source.load())


class SQLiteMemoryRepositoryTests(unittest.TestCase):

    def setUp(self) -> None:
        self.repository = SQLiteIncidentRepository(":memory:")
        self.data = DataManager(self.repository)

    def tearDown(self) -> None:
            self.repository.close()

    def test_crud_and_audit_trail(self) -> None:
            first, second = new_report(), new_report("Library")
            self.data.save(first)
            self.data.save(second)
    
            self.assertEqual(first.incident_id, "INCIDENT-001")
            self.assertEqual(self.data.get_by_id(first.incident_id).location,
                             "Building E Level 2")
            self.assertTrue(self.data.update_status(
                first.incident_id, "In Progress", "Technician assigned"
            ))
            history = self.data.status_history(first.incident_id)
            self.assertEqual(
                [(entry.previous_status, entry.new_status) for entry in history],
                [(None, "Pending Review"), ("Pending Review", "In Progress")],
            )
            self.assertEqual(history[-1].reason, "Technician assigned")
    
            self.assertTrue(self.data.delete(second.incident_id))
            self.assertIsNone(self.data.get_by_id(second.incident_id))
            self.data.clear()
            self.assertEqual(self.data.load(), [])

    def test_multi_criteria_search_edge_cases(self) -> None:
            critical_electrical = new_report("Building E Level 2")
            critical_electrical.attach_assessment(
                AIAssessment("Exposed wires", "Electrical", "Critical", "Severe",
                             "Cordon off area")
            )
            medium_plumbing = new_report("Building E Level 1")
            medium_plumbing.attach_assessment(
                AIAssessment("Leaking tap", "Plumbing", "Medium", "Moderate",
                             "Repair the tap")
            )
            critical_outside = new_report("Library Block B")
            critical_outside.attach_assessment(
                AIAssessment("Falling debris", "Electrical", "Critical", "Severe",
                             "Restrict access")
            )
            reports = [critical_electrical, medium_plumbing, critical_outside]
            for report in reports:
                self.data.save(report)
                self.data.update_status(report.incident_id, "In Progress")
    
            matches = self.data.search(
                location_query="  BUILDING E  ",
                status_filter="In Progress",
                category_filter="eLeCtRiCaL",
                min_severity=4,
            )
            self.assertEqual([row["incident_id"] for row in matches], ["INCIDENT-001"])
            self.assertEqual(len(self.data.search(min_severity=1)), 3)
            self.assertEqual(
                [row["incident_id"] for row in self.data.search(min_severity=4)],
                ["INCIDENT-001", "INCIDENT-003"],
            )
            with self.assertRaises(InvalidRecord):
                self.data.search(status_filter="Unknown")

    def test_json_migration_into_memory_database(self) -> None:
            with tempfile.TemporaryDirectory() as directory:
                source = DataManager(
                    JsonIncidentRepository(Path(directory) / "legacy.json")
                )
                source.save(new_report())
                source.save(new_report("Library"))
    
                imported = self.repository.import_records(source.load(), last_issued=2)
    
            self.assertEqual(imported, 2)
            self.assertEqual(
                [report.incident_id for report in self.data.load()],
                ["INCIDENT-001", "INCIDENT-002"],
            )
            third = new_report("Atrium")
            self.data.save(third)
            self.assertEqual(third.incident_id, "INCIDENT-003")


class RepositoryFactoryTests(unittest.TestCase):

    def test_factory_returns_selected_backend(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsInstance(create_repository("json", Path(folder) / "a.json"),
                                  JsonIncidentRepository)
            self.assertIsInstance(create_repository(" SQLite ", Path(folder) / "a.sqlite3"),
                                  SQLiteIncidentRepository)
            gc.collect()

    def test_factory_rejects_unknown_backend(self) -> None:
        with self.assertRaises(ValueError):
            create_repository("excel")


if __name__ == "__main__":
    unittest.main()
