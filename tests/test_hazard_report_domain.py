# FILE GUIDE: Offline tests for the HazardReport domain entity and its value objects.
# Input validation, encapsulation (defensive copies), status transitions and AI review rules.

"""Domain-model tests for HazardReport, Decision, audit and review entries."""
import unittest

from campus_safety.ai_manager.ai_assessment import AIAssessment
from campus_safety.domain.ai_review_entry import AIReviewEntry
from campus_safety.domain.decision import Decision
from campus_safety.domain.hazard_report import HazardReport
from campus_safety.domain.incident_audit_entry import IncidentAuditEntry
from campus_safety.domain.invalid_record import InvalidRecord

VALID = {
    "reporter_name": "Alex Tan", "reporter_contact": "alex01@sit.singaporetech.edu.sg",
    "location": "Block A", "impact_headcount": "10", "asset_info": "Fire door",
    "description": "The fire door does not close and blocks the corridor",
}


class InputValidationTests(unittest.TestCase):

    def test_valid_input_is_normalised(self) -> None:
        report = HazardReport.from_input(dict(VALID, location="  Block A  "))
        self.assertEqual(report.location, "Block A")
        self.assertEqual(report.get("impact_headcount"), 10)

    def test_phone_number_contact_is_accepted(self) -> None:
        HazardReport.from_input(dict(VALID, reporter_contact="81234567"))

    def test_invalid_inputs_are_rejected(self) -> None:
        cases = {
            "name with digits": {"reporter_name": "Alex 99"},
            "non-SIT email": {"reporter_contact": "alex@gmail.com"},
            "short phone": {"reporter_contact": "9123"},
            "empty location": {"location": "  "},
            "headcount zero": {"impact_headcount": 0},
            "headcount too large": {"impact_headcount": 1001},
            "headcount text": {"impact_headcount": "many"},
            "short asset": {"asset_info": "ab"},
            "short description": {"description": "too short"},
        }
        for label, change in cases.items():
            with self.subTest(label), self.assertRaises(InvalidRecord):
                HazardReport.from_input(dict(VALID, **change))


class EncapsulationTests(unittest.TestCase):

    def test_get_returns_copies_of_nested_data(self) -> None:
        report = HazardReport.from_storage({"incident_id": "INCIDENT-001", "tags": ["a"]})
        report.get("tags").append("hacked")
        self.assertEqual(report.get("tags"), ["a"])

    def test_constructor_copies_caller_dictionary(self) -> None:
        fields = {"incident_id": "INCIDENT-001", "tags": ["a"]}
        report = HazardReport(fields)
        fields["tags"].append("hacked")
        self.assertEqual(report.get("tags"), ["a"])

    def test_runtime_image_path_is_never_serialised(self) -> None:
        report = HazardReport.from_input(dict(VALID, image_patch="uploads/a.png"))
        report.set_runtime_image_path("C:/secret/absolute/a.png")
        stored = report.as_dict()
        self.assertNotIn("visual_evidence_path", stored)
        self.assertEqual(stored["image_path"], "uploads/a.png")

    def test_decision_breakdown_is_read_only(self) -> None:
        decision = Decision("High", 7, "Act", "Reason", "Queue", {"severity": 4})
        with self.assertRaises(TypeError):
            decision.score_breakdown["severity"] = 99


class StatusTransitionTests(unittest.TestCase):

    def setUp(self) -> None:
        self.report = HazardReport.from_input(VALID)
        self.report.assign_identity("INCIDENT-001")

    def test_assign_identity_only_once(self) -> None:
        with self.assertRaises(InvalidRecord):
            self.report.assign_identity("INCIDENT-002")

    def test_change_status_appends_history(self) -> None:
        self.assertTrue(self.report.change_status("In Progress", "Assigned"))
        self.assertTrue(self.report.change_status("Resolved", "Fixed"))
        self.assertEqual([e.new_status for e in self.report.status_history()],
                         ["Pending Review", "In Progress", "Resolved"])

    def test_same_status_is_a_no_op(self) -> None:
        self.assertFalse(self.report.change_status("Pending Review"))
        self.assertEqual(len(self.report.status_history()), 1)

    def test_invalid_status_and_blank_reason_rejected(self) -> None:
        with self.assertRaises(InvalidRecord):
            self.report.change_status("Finished")
        with self.assertRaises(InvalidRecord):
            self.report.change_status("Resolved", "   ")

    def test_audit_entry_requires_timezone(self) -> None:
        with self.assertRaises(InvalidRecord):
            IncidentAuditEntry("INCIDENT-001", None, "Pending Review", "2026-01-01T10:00:00", "x")

    def test_history_from_another_incident_is_rejected(self) -> None:
        fields = self.report.as_dict()
        fields["incident_id"] = "INCIDENT-999"
        with self.assertRaises(InvalidRecord):
            HazardReport.from_storage(fields)


class AIReviewTests(unittest.TestCase):

    def setUp(self) -> None:
        self.report = HazardReport.from_input(VALID)
        self.report.attach_assessment(
            AIAssessment("Blocked exit", "Structural", "High", "Severe", "Keep corridor clear"))
        self.report.assign_identity("INCIDENT-001")

    def test_review_is_appended_and_ai_fields_unchanged(self) -> None:
        self.report.add_ai_review("Officer Lim", "Accepted", "Matches inspection")
        self.assertEqual(self.report.ai_review_history()[0].reviewer, "Officer Lim")
        self.assertEqual(self.report.get("severity"), "High")
        self.assertEqual(self.report.get("assessment_source"), "Gemini AI")

    def test_review_requires_saved_assessment(self) -> None:
        unassessed = HazardReport.from_input(VALID)
        unassessed.assign_identity("INCIDENT-002")
        with self.assertRaises(InvalidRecord):
            unassessed.add_ai_review("Officer Lim", "Accepted", "ok")

    def test_invalid_review_values_rejected(self) -> None:
        with self.assertRaises(InvalidRecord):
            self.report.add_ai_review("Officer Lim", "Maybe", "unsure")
        with self.assertRaises(InvalidRecord):
            self.report.add_ai_review("L", "Accepted", "name too short")

    def test_review_entry_rejects_unexpected_fields(self) -> None:
        with self.assertRaises(InvalidRecord):
            AIReviewEntry.from_mapping({"incident_id": "INCIDENT-001", "extra": 1})


if __name__ == "__main__":
    unittest.main()
