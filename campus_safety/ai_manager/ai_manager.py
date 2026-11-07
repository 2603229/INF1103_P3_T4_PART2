# FILE GUIDE: Small AI orchestration facade that delegates to the AssessmentProvider contract.
# Dependency injection makes Gemini interchangeable with offline test doubles (polymorphism).

"""AI Manager: provider-independent AI assessment service.

GeminiAssessor and AssessmentUnavailable are imported for compatibility.
"""
from __future__ import annotations
from campus_safety.ai_manager.assessment_provider import AssessmentProvider
from campus_safety.domain.hazard_report import HazardReport
from campus_safety.ai_manager.ai_assessment import AIAssessment
from campus_safety.ai_manager.gemini_assessor import GeminiAssessor
from campus_safety.ai_manager.assessment_unavailable import AssessmentUnavailable


# Depends on an AssessmentProvider abstraction, so test doubles can replace Gemini.
# Its only responsibility is coordinating an AI assessment request.
class AIManager:
    """Aggregates an AssessmentProvider; can be tested with another implementation."""

    # Store the provider abstraction; callers can substitute a test stub for Gemini.
    def __init__(self, provider: AssessmentProvider) -> None:
        self._provider: AssessmentProvider = provider

    # Delegate the report to the selected AssessmentProvider; return its validated assessment.
    def assess(self, report: HazardReport) -> AIAssessment:
        """Accept only validated assessment objects from a provider.

        The provider interface promises AIAssessment, but runtime validation
        guards the workflow against a misbehaving alternative implementation.
        An invalid result must never reach scoring or persistence.
        """
        assessment = self._provider.assess(report)
        if not isinstance(assessment, AIAssessment):
            raise AssessmentUnavailable("AI provider returned an unvalidated assessment")
        return assessment
