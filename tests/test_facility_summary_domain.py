"""Automated offline tests for FacilitySummaryReport domain value object."""

import unittest
from campus_safety.domain.facility_summary_report import FacilitySummaryReport


class TestFacilitySummaryReportDomain(unittest.TestCase):
    """Tests for the FacilitySummaryReport domain value object."""

    def test_backlog_rate_calculation(self) -> None:
        report = FacilitySummaryReport(
            total_active_hazards=10,
            pending_repair_count=4,
            in_progress_count=3,
            urgent_hazard_count=2,
            hazards_by_location={"Building E": 6, "Library": 4},
            hazards_by_category={"Electrical": 5, "Plumbing": 5}
        )
        self.assertEqual(report.maintenance_backlog_rate, 40.0)
        self.assertEqual(len(report.as_dict()), 7)

    def test_zero_hazards_backlog_rate(self) -> None:
        report = FacilitySummaryReport(
            total_active_hazards=0,
            pending_repair_count=0,
            in_progress_count=0,
            urgent_hazard_count=0,
            hazards_by_location={},
            hazards_by_category={}
        )
        self.assertEqual(report.maintenance_backlog_rate, 0.0)


if __name__ == "__main__":
    unittest.main()
