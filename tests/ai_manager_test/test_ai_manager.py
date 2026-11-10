# FILE GUIDE: Offline unit tests for AIManager orchestration.
# Verify provider delegation, validated results, exception propagation,
# and substitution between different AssessmentProvider implementations.

"""Offline tests for AIManager orchestration and provider substitution."""

import unittest

from campus_safety.ai_manager.ai_assessment import AIAssessment
from campus_safety.ai_manager.ai_manager import AIManager
from campus_safety.ai_manager.assessment_unavailable import AssessmentUnavailable
from campus_safety.domain.hazard_report import HazardReport

from tests.ai_manager_test.ai_constant_provider import ConstantProvider
from tests.ai_manager_test.ai_stub_provider import StubProvider

# Valid assessment fixture shared by multiple test cases.
GOOD = {
    "risk_summary": "Water near electrical socket",
    "category": "Electrical",
    "severity": "High",
    "operational_impact": "Moderate",
    "contextual_insights": "Keep people away from the outlet",
}

class AIManagerTests(unittest.TestCase):
    """Verify AIManager coordination using offline assessment providers.

    Tests successful delegation, rejection of invalid provider results,
    propagation of provider failures, and polymorphic provider substitution.
    """

    def setUp(self):
        """Create a valid hazard report and assessment for each test."""
        self.report = HazardReport({"location": "Punggol Campus"})
        self.assessment = AIAssessment.from_mapping(GOOD)

    # Test 1: Verify that AIManager delegates to its configured provider.
    def test_delegates_to_provider_and_returns_assessment(self):
        provider = StubProvider(self.assessment)

        result = AIManager(provider).assess(self.report)

        self.assertIs(result, self.assessment)
        self.assertEqual(provider.received_reports, [self.report])

    # Test 2: Reject raw dictionaries instead of validated AIAssessment objects.
    def test_rejects_unvalidated_provider_result(self):
        provider = StubProvider(dict(GOOD))

        with self.assertRaises(AssessmentUnavailable):
            AIManager(provider).assess(self.report)

    # Test 3: Ensure provider exceptions are propagated to the caller.
    def test_propagates_provider_failure(self):
        provider = StubProvider(AssessmentUnavailable("Simulated outage"))

        with self.assertRaises(AssessmentUnavailable):
            AIManager(provider).assess(self.report)

    # Test 4: Verify that another concrete provider works with AIManager.
    def test_accepts_another_provider_implementation(self):
        provider = ConstantProvider()

        result = AIManager(provider).assess(self.report)

        self.assertIsInstance(result, AIAssessment)
        self.assertEqual(result.severity, "Medium")
        self.assertEqual(result.risk_summary, "Loose cable")

if __name__ == "__main__":
    unittest.main()