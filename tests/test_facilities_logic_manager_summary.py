"""Automated offline tests for LogicManager facilities summary aggregation."""

import unittest
from campus_safety.logic_manager.logic_manager import LogicManager


class TestLogicManagerFacilitiesSummary(unittest.TestCase):
    """Tests for LogicManager facilities summary aggregation."""

    def setUp(self) -> None:
        self.logic_mgr = LogicManager()
        self.sample_dict_records = [
            {
                "incident_id": "INCIDENT-001",
                "location": "Building E Level 2",
                "status": "Pending Review",
                "category": "Electrical",
                "severity": 4,
                "priority": "High"
            },
            {
                "incident_id": "INCIDENT-002",
                "location": "Building E Level 1",
                "status": "In Progress",
                "category": "Plumbing",
                "severity": 2,
                "priority": "Low"
            },
            {
                "incident_id": "INCIDENT-003",
                "location": "Library Block B",
                "status": "Pending Review",
                "category": "Infrastructure",
                "severity": 5,
                "priority": "Urgent"
            }
        ]

    def test_generate_facilities_summary_metrics(self) -> None:
        summary = self.logic_mgr.generate_facilities_summary(self.sample_dict_records)
        self.assertEqual(summary.total_active_hazards, 3)
        self.assertEqual(summary.pending_repair_count, 2)
        self.assertEqual(summary.in_progress_count, 1)
        self.assertEqual(summary.urgent_hazard_count, 2)
        self.assertEqual(summary.hazards_by_location["Building E Level 2"], 1)
        self.assertEqual(summary.hazards_by_category["Electrical"], 1)

    def test_empty_records_facilities_summary(self) -> None:
        summary = self.logic_mgr.generate_facilities_summary([])
        self.assertEqual(summary.total_active_hazards, 0)
        self.assertEqual(summary.pending_repair_count, 0)
        self.assertEqual(summary.maintenance_backlog_rate, 0.0)


if __name__ == "__main__":
    unittest.main()
