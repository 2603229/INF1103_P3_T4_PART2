"""Define the exception raised when AI assessment is unavailable."""

class AssessmentUnavailable(RuntimeError):
    """Indicate that a valid AI assessment could not be obtained.

    Raised when AI processing cannot produce a verified result,
    such as during API connection failures, missing credentials,
    invalid responses, or unsupported image evidence.

    The application workflow should handle this exception safely
    and prevent unassessed reports from being saved.
    """