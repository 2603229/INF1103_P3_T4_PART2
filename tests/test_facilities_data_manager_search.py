"""Automated offline tests for DataManager facilities search filtering."""

import unittest
from campus_safety.data_manager.data_manager import DataManager
from campus_safety.domain.hazard_report import HazardReport
from campus_safety.domain.invalid_record import InvalidRecord


class MockIncidentRepository:
    """In-memory mock repository to isolate DataManager testing."""

    def __init__(self, reports: list[HazardReport]) -> None:
        self._reports = reports

    def load(self) -> list[HazardReport]:
        return self._reports

    def save(self, report: HazardReport) -> None:
        self._reports.append(report)

    def replace_all(self, reports: list[HazardReport], backup_label: str = "auto") -> None:
        self._reports = reports

    def create_backup(self, label: str = "") -> str | None:
        return "mock_backup.json"

    def list_backups(self) -> list[str]:
        return []

    def restore_backup(self, path: str | None = None) -> None:
        pass


class TestFacilitiesDataManagerSearch(unittest.TestCase):
    """Tests for DataManager.search filtering logic."""

    def setUp(self) -> None:
        report1 = HazardReport.from_storage({
            "incident_id": "INCIDENT-001",
            "location": "Building E Level 2",
            "status": "Pending Review",
            "category": "Electrical",
            "severity": 4,
            "description": "Exposed wires near water fountain"
        })
        report2 = HazardReport.from_storage({
            "incident_id": "INCIDENT-002",
            "location": "Building E Level 1",
            "status": "In Progress",
            "category": "Plumbing",
            "severity": 2,
            "description": "Leaky tap in restroom"
        })
        report3 = HazardReport.from_storage({
            "incident_id": "INCIDENT-003",
            "location": "Library Block B",
            "status": "Pending Review",
            "category": "Infrastructure",
            "severity": 5,
            "description": "Cracked ceiling tile near entrance"
        })

        self.mock_repo = MockIncidentRepository([report1, report2, report3])
        self.data_mgr = DataManager(self.mock_repo)

    def test_search_by_location_keyword(self) -> None:
        results = self.data_mgr.search(location_query="building e")
        self.assertEqual(len(results), 2)
        self.assertTrue(all("Building E" in r["location"] for r in results))

    def test_search_by_status_filter(self) -> None:
        results = self.data_mgr.search(status_filter="Pending Review")
        self.assertEqual(len(results), 2)

    def test_search_rejects_invalid_status_filter(self) -> None:
        with self.assertRaises(InvalidRecord):
            self.data_mgr.search(status_filter="Unknown")

    def test_search_by_category_filter(self) -> None:
        results = self.data_mgr.search(category_filter="electrical")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["incident_id"], "INCIDENT-001")

    def test_search_by_severity_threshold(self) -> None:
        results = self.data_mgr.search(min_severity=4)
        self.assertEqual(len(results), 2)

    def test_search_rejects_out_of_range_severity_threshold(self) -> None:
        for min_severity in (0, 5):
            with self.subTest(min_severity=min_severity):
                with self.assertRaises(InvalidRecord):
                    self.data_mgr.search(min_severity=min_severity)

    def test_search_by_ai_severity_threshold(self) -> None:
        reports = [
            HazardReport.from_storage({
                "incident_id": f"INCIDENT-{severity.upper()}",
                "severity": severity,
            })
            for severity in ("Low", "Medium", "High", "Critical")
        ]
        data_mgr = DataManager(MockIncidentRepository(reports))

        results = data_mgr.search(min_severity=3)

        self.assertEqual(
            [report["severity"] for report in results],
            ["High", "Critical"],
        )

    def test_search_combined_filters(self) -> None:
        results = self.data_mgr.search(
            location_query="Building E",
            status_filter="In Progress",
            min_severity=2
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["incident_id"], "INCIDENT-002")

    def test_search_no_matches(self) -> None:
        results = self.data_mgr.search(location_query="Sports Complex")
        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()
