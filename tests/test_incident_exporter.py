"""Offline tests for incident CSV exports."""
from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from campus_safety.data_manager.incident_exporter import IncidentExporter
from campus_safety.domain.hazard_report import HazardReport


class IncidentExporterTests(unittest.TestCase):

    def test_csv_export_neutralizes_spreadsheet_formulas(self) -> None:
        values = [
            "=1+1", "+cmd", "-2", "@SUM(A1)", " =hidden",
            "\t=hidden", "\r=hidden", "\n=hidden", "ordinary text",
        ]
        reports = [
            HazardReport.from_storage({
                "incident_id": f"INCIDENT-{index:03}",
                "description": value,
            })
            for index, value in enumerate(values, start=1)
        ]

        with tempfile.TemporaryDirectory() as directory:
            path = IncidentExporter().export_csv(
                reports, Path(directory) / "incidents.csv"
            )
            with path.open(encoding="utf-8-sig", newline="") as stream:
                exported = [row["description"] for row in csv.DictReader(stream)]

        expected = ["'" + value if value != "ordinary text" else value
                    for value in values]
        self.assertEqual(exported, expected)


if __name__ == "__main__":
    unittest.main()
