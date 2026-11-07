# FILE GUIDE: Automated unit tests for AI assessment validation.
# Tests verify valid fields, invalid values and schema enforcement.
# These tests run offline without connecting to the Gemini API.

"""Unit tests for the AIAssessment value object."""

import unittest

from campus_safety.ai_manager.ai_assessment import AIAssessment
from campus_safety.domain.invalid_record import InvalidRecord


# Valid example AI response matching the required five-field schema.
GOOD = {
    "risk_summary": "Water near electrical socket",
    "category": "Electrical",
    "severity": "High",
    "operational_impact": "Moderate",
    "contextual_insights": "Keep people away from the outlet",
}

class AIAssessmentValidationTests(unittest.TestCase):

    # Test 1: A valid assessment should be accepted.
    def test_valid_direct_construction(self):
        assessment = AIAssessment(**GOOD)

        self.assertEqual(assessment.as_dict(), GOOD)

    # Test 2: Reject categories outside the approved schema.
    def test_direct_construction_rejects_invalid_category(self):
        with self.assertRaises(InvalidRecord):
            AIAssessment(**{**GOOD, "category": "Unknown"})

    # Test 3: Reject unsupported severity values.
    def test_direct_construction_rejects_invalid_severity(self):
        with self.assertRaises(InvalidRecord):
            AIAssessment(**{**GOOD, "severity": "Extreme"})

    # Test 4: Reject unsupported operational impact values.
    def test_direct_construction_rejects_invalid_impact(self):
        with self.assertRaises(InvalidRecord):
            AIAssessment(
                **{**GOOD, "operational_impact": "Disastrous"}
            )

    # Test 5: Reject empty and non-string values.
    def test_direct_construction_rejects_blank_and_non_string(self):
        invalid_values = [
            ("risk_summary", "  "),
            ("contextual_insights", None),
        ]

        for field, value in invalid_values:
            with self.subTest(field=field, value=value):
                with self.assertRaises(InvalidRecord):
                    AIAssessment(**{**GOOD, field: value})

    # Test 6: Trim whitespace before storing field values.
    def test_direct_construction_trims_whitespace(self):
        padded = {
            key: f"  {value}  "
            for key, value in GOOD.items()
        }

        assessment = AIAssessment(**padded)

        self.assertEqual(assessment.as_dict(), GOOD)

    # Test 7: Reject AI responses containing unexpected fields.
    def test_from_mapping_rejects_extra_fields(self):
        invalid_data = {**GOOD, "confidence": "90%"}

        with self.assertRaises(InvalidRecord):
            AIAssessment.from_mapping(invalid_data)


if __name__ == "__main__":
    unittest.main()
