# FILE GUIDE: Configurable stub AI provider for offline unit testing.
# Simulates successful responses, invalid results and provider failures.
# Records received reports to verify AIManager delegates requests correctly.

"""Offline stub implementation of the assessment-provider contract."""

from __future__ import annotations

from typing import Any

from campus_safety.ai_manager.assessment_provider import AssessmentProvider
from campus_safety.domain.hazard_report import HazardReport

# Configurable test double implementing the AssessmentProvider contract.
# Allows AIManager behaviour to be tested without external API calls.
class StubProvider(AssessmentProvider):
    """Simulate AI provider responses and failures for offline testing.

    Implements the same assess() interface as GeminiAssessor.
    Records received reports to verify provider delegation.

    Can return valid or intentionally invalid responses, or raise
    configured exceptions to test AIManager error handling.
    """

    def __init__(self, response: Any) -> None:
        """Initialize the stub with a predefined response.

        Args:
            response: Value to return during assessment, or an
                Exception instance to raise when assess() is called.
        """
        self.response = response
        self.received_reports: list[HazardReport] = []

    def assess(self, report: HazardReport) -> Any:
        """Record the report and simulate the configured provider behaviour.

        Args:
            report: Hazard report received from AIManager.

        Returns:
            Any: The predefined response, which may intentionally
                be invalid to test AIManager validation.

        Raises:
            Exception: The configured exception, if one was supplied.
        """
        # Record the report to verify that delegation occurred.
        self.received_reports.append(report)

        # Simulate provider failures without making API requests.
        if isinstance(self.response, Exception):
            raise self.response

        # Return the configured response for validation by AIManager.
        return self.response