# FILE GUIDE: Offline unit tests for the AssessmentProvider abstract interface.
# Verify abstract class restrictions, concrete provider implementations,
# and inheritance of the shared AI assessment contract.

"""Tests for the AssessmentProvider abstract class and concrete providers."""

import unittest

from campus_safety.ai_manager.ai_assessment import AIAssessment
from campus_safety.ai_manager.assessment_provider import AssessmentProvider
from campus_safety.ai_manager.gemini_assessor import GeminiAssessor
from campus_safety.domain.hazard_report import HazardReport

from tests.ai_manager_test.ai_constant_provider import ConstantProvider

class AssessmentProviderTests(unittest.TestCase):
    """Verify that AssessmentProvider enforces its abstract interface.

    Tests that incomplete providers cannot be instantiated and
    concrete providers implement the required assess() method.
    All tests execute offline without making Gemini API requests.
    """

    # Test 1: Abstract interfaces cannot be instantiated directly.
    def test_abstract_provider_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            AssessmentProvider()

    # Test 2: A subclass must implement the abstract assess() method.
    def test_subclass_without_assess_cannot_be_instantiated(self):
        class IncompleteProvider(AssessmentProvider):
            pass

        with self.assertRaises(TypeError):
            IncompleteProvider()

    # Test 3: A concrete provider implements the contract and returns AIAssessment.
    def test_concrete_provider_implements_contract(self):
        provider = ConstantProvider()

        self.assertIsInstance(provider, AssessmentProvider)
        self.assertIsInstance(
            provider.assess(HazardReport({"location": "Campus"})),
            AIAssessment,
        )

    # Test 4: GeminiAssessor inherits the AssessmentProvider interface.
    def test_gemini_assessor_implements_provider_contract(self):
        self.assertTrue(
            issubclass(GeminiAssessor, AssessmentProvider)
        )

if __name__ == "__main__":
    unittest.main()