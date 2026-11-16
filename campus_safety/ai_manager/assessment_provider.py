"""Abstract interface defining the AI assessment contract."""
from __future__ import annotations
from abc import ABC, abstractmethod
from campus_safety.ai_manager.ai_assessment import AIAssessment
from campus_safety.domain.hazard_report import HazardReport

class AssessmentProvider(ABC):
    """Define the common interface for AI assessment providers.

    Concrete implementations, such as GeminiAssessor, must implement
    the assess() method to process a HazardReport.

    AIManager depends on this abstraction rather than a specific
    provider, allowing different implementations to be substituted.

    This interface performs no API calls or assessment processing.
    """

    @abstractmethod
    def assess(self, report: HazardReport) -> AIAssessment:
        """Assess a hazard report and return a validated AI result.

        Args:
            report: Validated campus hazard report to be assessed.
        Returns:
            AIAssessment: Assessment containing the five required AI fields.
        """
        raise NotImplementedError