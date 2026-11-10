# FILE GUIDE: Small AI orchestration facade that delegates to the AssessmentProvider contract.
# Dependency injection makes Gemini interchangeable with offline test doubles (polymorphism).

"""AI Manager: provider-independent AI assessment service.

Coordinates assessments through the AssessmentProvider interface.
"""
from __future__ import annotations
from campus_safety.ai_manager.assessment_provider import AssessmentProvider
from campus_safety.domain.hazard_report import HazardReport
from campus_safety.ai_manager.ai_assessment import AIAssessment
from campus_safety.ai_manager.assessment_unavailable import AssessmentUnavailable

# Depends on an AssessmentProvider abstraction, so test doubles can replace Gemini.
# Its only responsibility is coordinating an AI assessment request.
class AIManager:
    """Coordinate AI assessments using an interchangeable provider.

    The provider is supplied externally through dependency injection.
    This allows GeminiAssessor or another AssessmentProvider
    implementation to be used without changing AIManager.
    """

    # Store the provider abstraction; callers can substitute a test stub for Gemini.
    def __init__(self, provider: AssessmentProvider) -> None:
        """Initialize AIManager with an assessment provider.

        Args:
            provider: An AssessmentProvider implementation responsible
                for generating AI assessments.
        """
        self._provider: AssessmentProvider = provider

    # Delegate the report to the selected AssessmentProvider; return its validated assessment.
    def assess(self, report: HazardReport) -> AIAssessment:
        """Request and validate an AI assessment for a hazard report.

        The provider handles the actual assessment process.
        AIManager ensures that only AIAssessment objects are returned.

        Args:
            report: Validated campus hazard report requiring assessment.

        Returns:
            AIAssessment: The validated assessment returned by the provider.

        Raises:
            AssessmentUnavailable: If the provider fails or returns
                an object that is not an AIAssessment.

        Invalid provider results must not reach the Logic Manager
        for scoring or the Data Manager for persistence.
        """
        assessment = self._provider.assess(report)

        # Reject an incorrect return type before it enters the workflow.
        if not isinstance(assessment, AIAssessment):
            raise AssessmentUnavailable("AI provider returned an unvalidated assessment")
        return assessment
