"""Deterministic assessment provider for offline contract tests."""
from campus_safety.ai_manager.ai_assessment import AIAssessment
from campus_safety.ai_manager.assessment_provider import AssessmentProvider

class ConstantProvider(AssessmentProvider):
    """Concrete provider for offline interface verification."""

    def assess(self, report):
        return AIAssessment.from_mapping({
            "risk_summary": "Loose cable",
            "category": "Electrical",
            "severity": "Medium",
            "operational_impact": "Minor",
            "contextual_insights": "Mark the area",
        })


