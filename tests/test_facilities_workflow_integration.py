"""Automated offline integration tests for facilities workflow."""

import unittest
from campus_safety.data_manager.data_manager import DataManager
from campus_safety.logic_manager.logic_manager import LogicManager
from campus_safety.domain.hazard_report import HazardReport


class MockIncidentRepository:
    """In-memory mock repository for integration testing."""

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


class TestFacilitiesWorkflowIntegration(unittest.TestCase):
    """End-to-end integration test combining DataManager search and LogicManager summary generation."""

    def setUp(self) -> None:
        report1 = HazardReport.from_storage({
            "incident_id": "INCIDENT-001",
            "location": "Building E Level 2",
            "status": "Pending Review",
            "category": "Electrical",
            "severity": 4,
            "priority": "High"
        })
        report2 = HazardReport.from_storage({
            "incident_id": "INCIDENT-002",
            "location": "Building E Level 1",
            "status": "In Progress",
            "category": "Plumbing",
            "severity": 2,
            "priority": "Low"
        })
        repo = MockIncidentRepository([report1, report2])
        self.data_mgr = DataManager(repo)
        self.logic_mgr = LogicManager()

    def test_search_and_summarize_workflow(self) -> None:
        search_results = self.data_mgr.search(location_query="Building E")
        summary = self.logic_mgr.generate_facilities_summary(search_results)

        self.assertEqual(summary.total_active_hazards, 2)
        self.assertEqual(summary.pending_repair_count, 1)
        self.assertEqual(summary.in_progress_count, 1)
        self.assertEqual(summary.maintenance_backlog_rate, 50.0)


if __name__ == "__main__":
    unittest.main()
