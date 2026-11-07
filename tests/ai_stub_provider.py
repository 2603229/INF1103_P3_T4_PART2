"""Offline stub implementation of the assessment-provider contract."""
from campus_safety.ai_manager.assessment_provider import AssessmentProvider

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


