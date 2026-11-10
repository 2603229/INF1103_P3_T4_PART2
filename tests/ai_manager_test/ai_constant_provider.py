
# FILE GUIDE: Deterministic AI assessment provider used for offline testing.
# Returns a fixed, validated assessment without making Gemini API calls.
# Helps verify the AssessmentProvider interface and polymorphism.

"""Deterministic assessment provider for offline contract tests."""

from __future__ import annotations

from campus_safety.ai_manager.ai_assessment import AIAssessment
from campus_safety.ai_manager.assessment_provider import AssessmentProvider
from campus_safety.domain.hazard_report import HazardReport


# Concrete test provider that implements the AssessmentProvider contract.
# Produces predictable results so tests do not depend on external AI services.
class ConstantProvider(AssessmentProvider):
    """Provide a fixed AI assessment for offline interface verification.

    Implements the same assess() interface as GeminiAssessor.
    Supports testing abstraction, inheritance and polymorphism
    without requiring API credentials or network access.
    """

    def assess(self, report: HazardReport) -> AIAssessment:
        """Return a predefined, validated AI assessment.

        Args:
            report: Hazard report supplied through the provider interface.
                The fixed test result does not depend on its contents.

        Returns:
            AIAssessment: A valid assessment containing five fixed fields.
        """
        return AIAssessment.from_mapping({
            "risk_summary": "Loose cable",
            "category": "Electrical",
            "severity": "Medium",
            "operational_impact": "Minor",
            "contextual_insights": "Mark the area",
        })