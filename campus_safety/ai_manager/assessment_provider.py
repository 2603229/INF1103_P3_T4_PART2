# FILE GUIDE: Abstract AI provider interface used by AIManager.
# A concrete provider must implement assess(report); the interface itself makes no network calls.
# Comments explain responsibilities and design; executable statements are unchanged.

"""Abstract AI provider interface."""
from __future__ import annotations
from abc import ABC, abstractmethod
from campus_safety.ai_manager.ai_assessment import AIAssessment
from campus_safety.domain.hazard_report import HazardReport


# ABC contract for an assessment implementation; subclasses override assess().
# This is the interface supporting dependency injection and test isolation.
class AssessmentProvider(ABC):
    """Interchangeable AI engines; production always uses a real API provider."""

    # Required operation: return a validated AIAssessment for a HazardReport.
    @abstractmethod
    def assess(self, report: HazardReport) -> AIAssessment:
        raise NotImplementedError
