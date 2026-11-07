"""Tests for the AssessmentProvider abstract class and concrete providers."""

import unittest

from campus_safety.ai_manager.ai_assessment import AIAssessment
from campus_safety.ai_manager.assessment_provider import AssessmentProvider
from campus_safety.ai_manager.gemini_assessor import GeminiAssessor
from campus_safety.domain.hazard_report import HazardReport


from tests.ai_constant_provider import ConstantProvider


class AssessmentProviderTests(unittest.TestCase):
    def test_abstract_provider_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            AssessmentProvider()

    def test_subclass_without_assess_cannot_be_instantiated(self):
        class IncompleteProvider(AssessmentProvider):
            pass

        with self.assertRaises(TypeError):
            IncompleteProvider()

    def test_concrete_provider_implements_contract(self):
        provider = ConstantProvider()
        self.assertIsInstance(provider, AssessmentProvider)
        self.assertIsInstance(
            provider.assess(HazardReport({"location": "Campus"})),
            AIAssessment,
        )

    def test_gemini_assessor_implements_provider_contract(self):
        self.assertTrue(issubclass(GeminiAssessor, AssessmentProvider))


if __name__ == "__main__":
    unittest.main()
