# FILE GUIDE: Offline tests for IOManager using injected read/write callables.
# Scripted answers replace the keyboard, so input validation loops and display
# formatting can be checked automatically (including inside Docker/CI).

"""IO Manager tests: menu, input validation, search criteria and summary display."""
import unittest

from campus_safety.domain.decision import Decision
from campus_safety.domain.facility_summary_report import FacilitySummaryReport
from campus_safety.domain.hazard_report import HazardReport
from campus_safety.io_manager.io_manager import IOManager
from campus_safety.io_manager.validators import InputValidator


class IOManagerCLITests(unittest.TestCase):

    def scripted(self, *answers: str) -> IOManager:
        """IOManager that reads the given answers and records what it prints in self.output."""
        remaining = iter(answers)
        self.output: list[str] = []
        return IOManager(read=lambda prompt: next(remaining), write=self.output.append)

    @property
    def text(self) -> str:
        return "\n".join(self.output)

    # --- Menu and confirmation ---------------------------------------------
    def test_menu_accepts_all_six_options(self) -> None:
        for choice in "123456":
            with self.subTest(choice=choice):
                self.assertEqual(self.scripted(choice).menu(), choice)

    def test_menu_rejects_invalid_then_accepts(self) -> None:
        manager = self.scripted("0", "7", "abc", "5")
        self.assertEqual(manager.menu(), "5")
        self.assertEqual(self.text.count("[Error]"), 3)

    def test_confirm_yes_no_and_retry(self) -> None:
        self.assertTrue(self.scripted("YES").confirm())
        manager = self.scripted("maybe", "n")
        self.assertFalse(manager.confirm())
        self.assertIn("[Error]", self.text)

    # --- User input and validators -----------------------------------------
    def test_get_user_input_retries_invalid_fields(self) -> None:
        manager = self.scripted(
            "Alex 99", "Alex Tan",                       # name: digits rejected
            "alex@gmail.com", "91234567",                # contact: non-SIT rejected
            "", "Block A Level 3",                       # location: empty rejected
            "0", "abc", "12",                            # headcount: out of range / text
            "Door", "Fire door",                         # asset: too short
            "Broken", "The fire door will not close at all",  # description: too short
            "n",                                         # attach image? no
        )
        report = manager.get_user_input()
        self.assertIsInstance(report, HazardReport)
        self.assertEqual(report.location, "Block A Level 3")
        self.assertEqual(report.get("impact_headcount"), 12)
        self.assertEqual(report.get("image_path"), "")
        self.assertEqual(self.text.count("[Error]"), 7)

    def test_validator_rules(self) -> None:
        self.assertTrue(InputValidator.validate_contact("abc123@sit.singaporetech.edu.sg"))
        self.assertFalse(InputValidator.validate_contact("71234567"))
        self.assertTrue(InputValidator.validate_headcount("1000"))
        self.assertFalse(InputValidator.validate_headcount("-1"))
        self.assertFalse(InputValidator.validate_description("   short   "))

    # --- Display -------------------------------------------------------------
    def test_priority_calculation_shows_breakdown(self) -> None:
        manager = self.scripted()
        report = HazardReport({"severity": "High", "operational_impact": "Severe",
                               "historical_frequency": 2})
        decision = Decision("High", 10, "Priority Maintenance", "r", "Priority Maintenance Queue",
                            {"severity": 4, "operational_impact": 4, "historical_frequency": 2})
        manager.priority_calculation(report, decision)
        self.assertIn("Priority Score: 10", self.text)
        self.assertIn("Final Priority: High", self.text)

    def test_view_all_reports_empty_and_filled(self) -> None:
        manager = self.scripted()
        manager.view_all_reports([])
        self.assertIn("No hazard reports found", self.text)
        manager.view_all_reports([HazardReport({"incident_id": "INCIDENT-001"})])
        self.assertIn("INCIDENT-001", self.text)

    def test_view_frequent_hazards(self) -> None:
        manager = self.scripted()
        manager.view_frequent_hazards([("Electrical", 3)])
        self.assertIn("1. Electrical", self.text)
        self.assertIn("3 reports", self.text)
        self.assertIn("██████████", self.text)

    # --- Search criteria -------------------------------------------------------
    def test_all_filters_skipped(self) -> None:
        criteria = self.scripted("", "", "", "").get_search_criteria()
        self.assertEqual(criteria, {"location_query": "", "status_filter": "",
                                    "category_filter": "", "min_severity": 1})

    def test_filters_chosen_by_number(self) -> None:
        criteria = self.scripted("library", "2", "1", "3").get_search_criteria()
        self.assertEqual(criteria, {"location_query": "library", "status_filter": "In Progress",
                                    "category_filter": "Electrical", "min_severity": 3})

    def test_invalid_choice_is_retried(self) -> None:
        manager = self.scripted("", "9", "x", "1", "", "")
        self.assertEqual(manager.get_search_criteria()["status_filter"], "Pending Review")
        self.assertEqual(self.text.count("[Error]"), 2)

    def test_search_results_display(self) -> None:
        manager = self.scripted()
        manager.view_search_results([])
        self.assertIn("No incidents match", self.text)
        manager.view_search_results([{"incident_id": "INCIDENT-004", "location": "Library"}])
        self.assertIn("Matching Incidents: 1", self.text)
        self.assertIn("INCIDENT-004 | Library", self.text)

    # --- Facilities summary display ------------------------------------------
    def test_summary_shows_metrics_sorted_by_count(self) -> None:
        summary = FacilitySummaryReport(4, 3, 1, 2, {"Library": 1, "Block A": 3},
                                        {"HVAC": 4})
        manager = self.scripted()
        manager.view_facilities_summary(summary)
        self.assertIn("Active Hazards: 4", self.text)
        self.assertIn("Maintenance Backlog Rate: 75.0%", self.text)
        self.assertLess(self.text.index("Block A: 3"), self.text.index("Library: 1"))

    def test_empty_summary_display(self) -> None:
        self.scripted().view_facilities_summary(FacilitySummaryReport(0, 0, 0, 0, {}, {}))
        self.assertIn("No active hazards", self.text)


if __name__ == "__main__":
    unittest.main()
