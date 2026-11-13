"""Offline tests for the dashboard's presentation helpers (no Streamlit needed)."""
from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from campus_safety.dashboard import dashboard_extensions
from campus_safety.dashboard.dashboard_extensions import (
    count_by, demo_records_present, demo_storage_configured, filter_reports,
    format_sg_time, monthly_counts, overview_metrics, parse_report_time,
    resolve_evidence_image,
)

ROWS = [
    {"incident_id": "INCIDENT-001", "location": "Library Level 2", "status": "Pending Review",
     "final_priority": "High", "category": "Electrical", "priority_score": 8,
     "timestamp": "2026-11-01 09:00:00"},
    {"incident_id": "INCIDENT-002", "location": "Block A Lab 3", "status": "In Progress",
     "final_priority": "Normal", "category": "Plumbing", "priority_score": 3,
     "timestamp": "2026-11-05 14:30:00"},
    {"incident_id": "INCIDENT-003", "location": "Cafeteria", "status": "Resolved",
     "final_priority": "Critical", "category": "Structural", "priority_score": 12,
     "timestamp": "2026-10-20 08:15:00"},
    {"incident_id": "INCIDENT-004", "location": "Block B", "category": "HVAC",
     "priority_score": 5},  # legacy row: no status, priority or timestamp
]


def ids(rows):
    return [row["incident_id"] for row in rows]


class FilterReportsTests(unittest.TestCase):

    def test_no_filters_returns_every_row(self) -> None:
        self.assertEqual(len(filter_reports(ROWS)), 4)

    def test_search_is_case_insensitive_across_fields(self) -> None:
        self.assertEqual(ids(filter_reports(ROWS, search="LIBRARY")), ["INCIDENT-001"])
        self.assertEqual(ids(filter_reports(ROWS, search="plumb")), ["INCIDENT-002"])
        self.assertEqual(ids(filter_reports(ROWS, search="  incident-003 ")), ["INCIDENT-003"])

    def test_missing_status_counts_as_pending_review(self) -> None:
        result = filter_reports(ROWS, statuses=["Pending Review"], sort="Oldest first")
        self.assertEqual(set(ids(result)), {"INCIDENT-001", "INCIDENT-004"})

    def test_priority_and_category_filters_combine(self) -> None:
        self.assertEqual(ids(filter_reports(ROWS, priorities=["High", "Critical"],
                                            categories=["Structural"])), ["INCIDENT-003"])
        self.assertEqual(ids(filter_reports(ROWS, priorities=["Unassigned"])), ["INCIDENT-004"])

    def test_date_range_is_inclusive_and_skips_rows_without_dates(self) -> None:
        result = filter_reports(ROWS, date_start=date(2026, 11, 1), date_end=date(2026, 11, 5))
        self.assertEqual(set(ids(result)), {"INCIDENT-001", "INCIDENT-002"})

    def test_default_sort_is_highest_risk_first(self) -> None:
        self.assertEqual(ids(filter_reports(ROWS)),
                         ["INCIDENT-003", "INCIDENT-001", "INCIDENT-004", "INCIDENT-002"])

    def test_other_sort_orders(self) -> None:
        self.assertEqual(ids(filter_reports(ROWS, sort="Lowest risk first"))[0], "INCIDENT-002")
        self.assertEqual(ids(filter_reports(ROWS, sort="Newest first"))[0], "INCIDENT-002")
        self.assertEqual(ids(filter_reports(ROWS, sort="Location A–Z"))[:2],
                         ["INCIDENT-002", "INCIDENT-004"])

    def test_returns_copies_not_the_original_rows(self) -> None:
        result = filter_reports(ROWS, search="library")
        result[0]["location"] = "changed"
        self.assertEqual(ROWS[0]["location"], "Library Level 2")


class ChartDataTests(unittest.TestCase):

    def test_count_by_orders_by_frequency_and_labels_missing_values(self) -> None:
        rows = [{"category": "HVAC"}, {"category": "Electrical"}, {"category": "HVAC"}, {}]
        counts = count_by(rows, "category")
        self.assertEqual(counts, {"HVAC": 2, "Electrical": 1, "Unspecified": 1})
        self.assertEqual(next(iter(counts)), "HVAC")

    def test_monthly_counts_are_sorted_and_skip_bad_timestamps(self) -> None:
        rows = [{"timestamp": "2026-11-05 10:00:00"}, {"timestamp": "2026-10-01 10:00:00"},
                {"timestamp": "2026-11-20 10:00:00"}, {"timestamp": "not a date"}, {}]
        self.assertEqual(monthly_counts(rows), {"2026-10": 1, "2026-11": 2})

    def test_timestamps_are_shown_in_singapore_time(self) -> None:
        # 23:30 UTC on 31 Oct is already 1 Nov in Singapore (UTC+8)
        moment = parse_report_time("2026-10-31T23:30:00Z")
        self.assertEqual((moment.month, moment.day, moment.hour), (11, 1, 7))
        self.assertEqual(format_sg_time("2026-11-01 09:05:00"), "01 Nov 2026, 09:05 AM SGT")

    def test_unreadable_timestamp_is_handled(self) -> None:
        self.assertIsNone(parse_report_time("yesterday"))
        self.assertEqual(format_sg_time(None), "Unknown time")


class EvidenceImageTests(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.project = base / "project"
        (self.project / "uploads").mkdir(parents=True)
        (self.project / "uploads" / "leak.png").write_bytes(b"fake image bytes")
        (self.project / "uploads" / "notes.txt").write_text("not an image")
        self.outside = base / "secret.png"
        self.outside.write_bytes(b"outside the project")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_relative_upload_path_is_found(self) -> None:
        found = resolve_evidence_image("uploads/leak.png", [self.project])
        self.assertEqual(found, (self.project / "uploads" / "leak.png").resolve())

    def test_path_traversal_is_rejected(self) -> None:
        self.assertIsNone(resolve_evidence_image("../secret.png", [self.project]))
        self.assertIsNone(resolve_evidence_image("uploads/../../secret.png", [self.project]))

    def test_absolute_path_outside_allowed_roots_is_rejected(self) -> None:
        self.assertIsNone(resolve_evidence_image(str(self.outside), [self.project]))

    def test_second_allowed_root_is_searched(self) -> None:
        found = resolve_evidence_image("secret.png", [self.project, self.outside.parent])
        self.assertEqual(found, self.outside.resolve())

    def test_non_images_missing_files_and_bad_values_are_rejected(self) -> None:
        for value in ("uploads/notes.txt", "uploads/missing.png", "", None, 42):
            with self.subTest(value=value):
                self.assertIsNone(resolve_evidence_image(value, [self.project]))

    def test_oversized_image_is_rejected(self) -> None:
        with patch.object(dashboard_extensions, "MAX_EVIDENCE_BYTES", 4):
            self.assertIsNone(resolve_evidence_image("uploads/leak.png", [self.project]))


class SafeguardAndMetricTests(unittest.TestCase):

    def test_demo_records_are_detected(self) -> None:
        self.assertTrue(demo_records_present([{"incident_id": "A"}, {"demo_fixture": True}]))
        self.assertFalse(demo_records_present([{"demo_fixture": "yes"}, {}]))

    def test_old_demo_storage_paths_are_detected(self) -> None:
        self.assertTrue(demo_storage_configured("sqlite", {"SQLITE_DB_PATH": r"C:\x\demo_data\db.sqlite3"}))
        self.assertTrue(demo_storage_configured("json", {"INCIDENTS_DB": "/tmp/demo_incidents.json"}))
        self.assertTrue(demo_storage_configured("json", {"HAZARD_DATA_DIR": "/home/u/Demo_Data"}))

    def test_real_paths_are_not_flagged(self) -> None:
        self.assertFalse(demo_storage_configured("sqlite", {}))
        self.assertFalse(demo_storage_configured("sqlite", {"HAZARD_DATA_DIR": "/data"}))
        # 'demo' inside a normal name is fine; only the old bundle's markers count
        self.assertFalse(demo_storage_configured("json", {"INCIDENTS_DB": "/srv/demonstration.json"}))
        # the other backend's variable is ignored
        self.assertFalse(demo_storage_configured("sqlite", {"INCIDENTS_DB": "/x/demo_data/a.json"}))

    def test_overview_metrics(self) -> None:
        rows = [
            {"status": "Pending Review", "final_priority": "High", "assessment_source": "Gemini AI"},
            {"status": "In Progress", "final_priority": "Normal", "assessment_source": "Gemini AI",
             "ai_review_history": [{"decision": "Accepted"}]},
            {"status": "Resolved", "final_priority": "Critical"},
            {},
        ]
        self.assertEqual(overview_metrics(rows), {
            "total": 4, "active": 3, "high_priority": 1, "resolved": 1,
            "pending_review": 2, "awaiting_ai_review": 1,
        })


if __name__ == "__main__":
    unittest.main()
