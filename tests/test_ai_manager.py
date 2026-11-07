"""Offline tests for AIManager orchestration and provider substitution."""

import unittest

from campus_safety.ai_manager.ai_assessment import AIAssessment
from campus_safety.ai_manager.ai_manager import AIManager
from campus_safety.ai_manager.assessment_provider import AssessmentProvider
from campus_safety.ai_manager.assessment_unavailable import AssessmentUnavailable
from campus_safety.domain.hazard_report import HazardReport


GOOD = {
    "risk_summary": "Water near electrical socket",
    "category": "Electrical",
    "severity": "High",
    "operational_impact": "Moderate",
    "contextual_insights": "Keep people away from the outlet",
}


class StubProvider(AssessmentProvider):
    """A fake provider that never calls an external API."""

    def __init__(self, response):
        self.response = response
        self.received_reports = []

    def assess(self, report):
        self.received_reports.append(report)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class AIManagerTests(unittest.TestCase):
    def setUp(self):
        self.report = HazardReport({"location": "Punggol Campus"})
        self.assessment = AIAssessment.from_mapping(GOOD)

    def test_delegates_to_provider_and_returns_assessment(self):
        provider = StubProvider(self.assessment)
        result = AIManager(provider).assess(self.report)
        self.assertIs(result, self.assessment)
        self.assertEqual(provider.received_reports, [self.report])

    def test_rejects_unvalidated_provider_result(self):
        provider = StubProvider(dict(GOOD))
        with self.assertRaises(AssessmentUnavailable):
            AIManager(provider).assess(self.report)

    def test_propagates_provider_failure(self):
        provider = StubProvider(AssessmentUnavailable("Simulated outage"))
        with self.assertRaises(AssessmentUnavailable):
            AIManager(provider).assess(self.report)

    def test_accepts_another_provider_implementation(self):
        alternative = AIAssessment.from_mapping({**GOOD, "severity": "Critical"})
        provider = StubProvider(alternative)
        self.assertEqual(AIManager(provider).assess(self.report).severity, "Critical")


if __name__ == "__main__":
    unittest.main()
