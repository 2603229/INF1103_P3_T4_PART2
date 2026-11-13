"""Offline tests for the dashboard's threaded CSV export service."""
from __future__ import annotations

import csv
import io
import threading
import unittest
from unittest.mock import patch

from campus_safety.dashboard.background_export_service import BackgroundExportService
from campus_safety.domain.hazard_report import HazardReport
from campus_safety.domain.schema import SCHEMA_FIELDS


def read_csv(data: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))


class CsvContentTests(unittest.TestCase):

    def setUp(self) -> None:
        self.service = BackgroundExportService(max_workers=1)

    def tearDown(self) -> None:
        self.service.close()

    def export(self, rows) -> bytes:
        return self.service.submit_csv(rows).result(timeout=10)

    def test_schema_columns_come_first_then_extra_fields_sorted(self) -> None:
        data = self.export([{"incident_id": "INCIDENT-001", "zeta": 1, "alpha": 2}])
        header = next(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
        self.assertEqual(header[:len(SCHEMA_FIELDS)], list(SCHEMA_FIELDS))
        self.assertEqual(header[len(SCHEMA_FIELDS):], ["alpha", "zeta"])

    def test_file_starts_with_utf8_bom_for_excel(self) -> None:
        self.assertTrue(self.export([{"incident_id": "INCIDENT-001"}]).startswith(b"\xef\xbb\xbf"))

    def test_values_are_rendered_safely(self) -> None:
        row = read_csv(self.export([{
            "incident_id": "INCIDENT-001", "location": None, "priority_score": 7,
            "status_history": [{"new_status": "Pending Review"}], "is_duplicate": False,
        }]))[0]
        self.assertEqual(row["location"], "")
        self.assertEqual(row["priority_score"], "7")
        self.assertEqual(row["status_history"], '[{"new_status": "Pending Review"}]')
        self.assertEqual(row["is_duplicate"], "False")

    def test_spreadsheet_formulas_are_neutralised(self) -> None:
        rows = [{"incident_id": f"INCIDENT-00{i}", "description": text}
                for i, text in enumerate(["=1+1", "+cmd", "-2", "@SUM(A1)", " =hidden"], 1)]
        exported = [r["description"] for r in read_csv(self.export(rows))]
        self.assertTrue(all(value.startswith("'") for value in exported), exported)

    def test_hazard_report_objects_are_accepted(self) -> None:
        report = HazardReport.from_storage({"incident_id": "INCIDENT-009", "location": "Block C"})
        row = read_csv(self.export([report]))[0]
        self.assertEqual((row["incident_id"], row["location"]), ("INCIDENT-009", "Block C"))

    def test_empty_export_raises_error(self) -> None:
        with self.assertRaises(ValueError):
            self.export([])


class ThreadingTests(unittest.TestCase):

    def test_csv_is_built_on_a_worker_thread(self) -> None:
        names: list[str] = []
        original = BackgroundExportService._render_csv

        def spy(records):
            names.append(threading.current_thread().name)
            return original(records)

        service = BackgroundExportService()
        try:
            with patch.object(BackgroundExportService, "_render_csv", side_effect=spy):
                service.submit_csv([{"incident_id": "INCIDENT-001"}]).result(timeout=10)
        finally:
            service.close()
        self.assertEqual(len(names), 1)
        self.assertTrue(names[0].startswith("incident-csv"), names)
        self.assertNotEqual(names[0], threading.current_thread().name)

    def test_worker_uses_a_snapshot_taken_at_submit_time(self) -> None:
        release = threading.Event()
        original = BackgroundExportService._render_csv

        def slow(records):
            release.wait(timeout=10)  # hold the worker until the caller has changed its data
            return original(records)

        rows = [{"incident_id": "INCIDENT-001", "location": "Block A"}]
        service = BackgroundExportService()
        try:
            with patch.object(BackgroundExportService, "_render_csv", side_effect=slow):
                future = service.submit_csv(rows)
                rows[0]["location"] = "changed after submit"
                release.set()
                data = future.result(timeout=10)
        finally:
            service.close()
        self.assertEqual(read_csv(data)[0]["location"], "Block A")

    def test_close_stops_new_work(self) -> None:
        service = BackgroundExportService()
        service.close()
        with self.assertRaises(RuntimeError):
            service.submit_csv([{"incident_id": "INCIDENT-001"}])


if __name__ == "__main__":
    unittest.main()
