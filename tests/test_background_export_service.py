"""Offline tests for the dashboard's threaded CSV export service."""
from __future__ import annotations

import csv
import io
import unittest

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


if __name__ == "__main__":
    unittest.main()
